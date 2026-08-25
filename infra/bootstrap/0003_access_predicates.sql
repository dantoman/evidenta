-- =============================================================================
-- F0.1.3 — Predicatele de acces
--
-- Autoritate:  docs/decisions/003-rls-tenancy-tables.md
--              docs/specs/spec-a-tenancy.md §2.4
--
-- Rulează ca evidenta_owner. Idempotent.
--
-- ACESTA ESTE SINGURUL LOC DIN SISTEM UNDE O GREȘEALĂ DESCHIDE TOATE DATELE
-- TUTUROR TENANȚILOR. Are teste proprii, separate de suitele de izolare.
--
-- Trei lucruri care par detalii și nu sunt:
--
-- 1. SECURITY DEFINER + deținute de evidenta_rls (BYPASSRLS). Nu de owner:
--    sub FORCE ROW LEVEL SECURITY nici owner-ul nu ocolește politicile, deci
--    recursiunea ar reveni.
-- 2. search_path fixat în definiție. Fără el, o funcție SECURITY DEFINER deținută
--    de un rol cu BYPASSRLS este vector de escaladare de privilegii.
-- 3. Predicatele trăiesc în schema `rls`, deținută de evidenta_rls, nu în `app`.
--    Owner-ul face SET ROLE și creează acolo. Alternativele nu funcționează:
--    a crea în `app` și a transfera proprietatea cere ca noul proprietar să aibă
--    CREATE pe `app` — adică exact privilegiul permanent pe care separarea îl evită.
-- 4. LANGUAGE plpgsql, nu sql. PL/pgSQL amână rezolvarea numelor de tabele până la
--    prima execuție, deci funcțiile se pot crea înainte ca tabelele de tenancy să
--    existe (F0.3) — iar până atunci eșuează la execuție, ceea ce este exact
--    comportamentul fail-closed dorit. Compromis acceptat: o funcție SQL ar putea
--    fi inline-uită de planner, plpgsql nu. Conversia este o migrare de o linie,
--    de făcut DUPĂ măsurătoare, nu înainte (spec-a §2.8).
-- =============================================================================

\set ON_ERROR_STOP on

SET ROLE evidenta_rls;

REVOKE ALL   ON SCHEMA rls FROM PUBLIC;
-- evidenta_app le apelează la runtime; evidenta_owner trebuie să le poată REFERI
-- când creează politicile, altfel `CREATE POLICY ... USING (rls.has_tenant_access(...))`
-- eșuează cu „permission denied for schema rls".
GRANT  USAGE ON SCHEMA rls TO evidenta_app, evidenta_owner;


-- --- cele două căi de acces din V2 §4.2 -------------------------------------
-- calea 1: membru activ al tenantului
-- calea 2: engagement activ al firmei în numele căreia acționează utilizatorul
CREATE OR REPLACE FUNCTION rls.has_tenant_access(p_tenant_id uuid) RETURNS boolean
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public, app, rls, pg_temp AS $fn$
DECLARE
    v_user_id uuid := app.current_user_id();
    v_firm_id uuid := app.current_actor_firm_id();
    v_ok      boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM membership m
        WHERE m.tenant_id = p_tenant_id
          AND m.user_id   = v_user_id
          AND m.status    = 'active'
    ) INTO v_ok;

    IF v_ok OR v_firm_id IS NULL THEN
        RETURN v_ok;
    END IF;

    -- Apartenența la firmă se verifică, nu se presupune: altfel oricine poate
    -- pretinde că acționează pentru orice firmă doar setând o variabilă de sesiune.
    SELECT EXISTS (
        SELECT 1
        FROM engagement e
        JOIN firm f        ON f.id = e.firm_id
        JOIN membership fm ON fm.tenant_id = f.tenant_id
                          AND fm.user_id  = v_user_id
                          AND fm.status   = 'active'
        WHERE e.client_tenant_id = p_tenant_id
          AND e.firm_id          = v_firm_id
          AND e.status           = 'active'
          AND e.valid_from      <= current_date
          AND (e.valid_to IS NULL OR e.valid_to >= current_date)
    ) INTO v_ok;

    RETURN v_ok;
END
$fn$;

-- Valabilitatea se evaluează la current_date: un engagement expirat nu mai dă
-- acces fără să fie nevoie de un job care să-i schimbe starea. Starea `expired`
-- există pentru interfață și rapoarte, nu ca mecanism de securitate.

CREATE OR REPLACE FUNCTION rls.has_company_access(p_company_id uuid) RETURNS boolean
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public, app, rls, pg_temp AS $fn$
DECLARE v_ok boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM company_access ca
        WHERE ca.company_id = p_company_id
          AND ca.user_id    = app.current_user_id()
          AND ca.revoked_at IS NULL
          AND ca.valid_from <= current_date
          AND (ca.valid_to IS NULL OR ca.valid_to >= current_date)
    ) INTO v_ok;
    RETURN v_ok;
END
$fn$;

-- Engagementul leagă doi tenanți. Ambele părți îl văd; niciunul nu este
-- „contextul" lui. Vezi ADR-003.
CREATE OR REPLACE FUNCTION rls.can_see_engagement(p_client_tenant_id uuid, p_firm_id uuid)
RETURNS boolean
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public, app, rls, pg_temp AS $fn$
DECLARE
    v_user_id uuid := app.current_user_id();
    v_ok      boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM membership m
        WHERE m.tenant_id = p_client_tenant_id
          AND m.user_id   = v_user_id
          AND m.status    = 'active'
    ) INTO v_ok;

    IF v_ok THEN
        RETURN true;
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM firm f
        JOIN membership fm ON fm.tenant_id = f.tenant_id
                          AND fm.user_id  = v_user_id
                          AND fm.status   = 'active'
        WHERE f.id = p_firm_id
    ) INTO v_ok;

    RETURN v_ok;
END
$fn$;

-- --- privilegii (încă sub SET ROLE: proprietarul funcțiilor le acordă) -------
REVOKE ALL ON FUNCTION rls.has_tenant_access(uuid), rls.has_company_access(uuid),
                       rls.can_see_engagement(uuid, uuid)
    FROM PUBLIC;

GRANT EXECUTE ON FUNCTION rls.has_tenant_access(uuid), rls.has_company_access(uuid),
                          rls.can_see_engagement(uuid, uuid)
    TO evidenta_app, evidenta_owner;

RESET ROLE;

-- --- verificări -------------------------------------------------------------
DO $checks$
DECLARE r record;
BEGIN
    FOR r IN
        SELECT p.proname, p.prosecdef, p.proconfig,
               pg_get_userbyid(p.proowner) AS owner
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'rls'
          AND p.proname IN ('has_tenant_access', 'has_company_access', 'can_see_engagement')
    LOOP
        IF NOT r.prosecdef THEN
            RAISE EXCEPTION 'rls.% trebuie sa fie SECURITY DEFINER', r.proname;
        END IF;
        IF r.owner <> 'evidenta_rls' THEN
            RAISE EXCEPTION 'rls.% trebuie detinuta de evidenta_rls, nu de %', r.proname, r.owner;
        END IF;
        IF r.proconfig IS NULL
           OR NOT EXISTS (SELECT 1 FROM unnest(r.proconfig) c WHERE c LIKE 'search_path=%') THEN
            RAISE EXCEPTION 'rls.% trebuie sa aiba search_path fixat', r.proname;
        END IF;
    END LOOP;
END
$checks$;
