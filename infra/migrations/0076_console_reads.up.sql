-- 0076 — functiile de citire ale consolei platformei (ADR-076 §4.3, ADR-092)
--
-- Context:     docs/decisions/076-planul-de-control-al-platformei.md §4.2–§4.3
--              docs/decisions/092-consola-citeste-metadate-si-administreaza-personalul.md
--              docs/specs/spec-a-tenancy.md §14 (consola), R7
--              infra/migrations/0028_auth_request_path.up.sql — forma copiata: functii inguste,
--                  SECURITY DEFINER, detinute de evidenta_rls, expuse una cate una
--
-- PROBLEMA. Consola are context de utilizator si NU are context de tenant (ADR-076 §4.2). Orice
-- politica de tenant ridica eroare sub el — asta e proprietatea dorita — dar paginile consolei
-- trebuie sa arate METADATE despre toate spatiile: subdomeniu, denumire, stare, cati membri, ce
-- capabilitati, ce ring, ce a rulat pe caile privilegiate. Sunt interogari cross-tenant prin
-- definitie, iar R7 le permite doar in read models si in caile enumerate in Spec A. Acestea sunt
-- caile enumerate: Spec A §14 le tine lista.
--
-- CE APARA FIECARE FUNCTIE, IN ORDINE. (1) `rls.console_caller_role()` refuza cand exista un
-- context de tenant — o functie de consola nu se apeleaza de pe gazda unui client, oricine ar fi
-- apelantul — si refuza cand apelantul n-are rand viu in `platform_staff`. Abia apoi citeste.
-- (2) Coloanele intoarse sunt cele din ADR-076 §4.3 si niciuna in plus: nicio suma, niciun
-- document, niciun nume de partener. Numarul de companii ale unui spatiu e metadata; continutul
-- lor nu e. (3) Filtrele sunt parametri tipizati, nu SQL.
--
-- DE CE NU RAND IN privileged_access_log. Sunt citiri de metadate ale platformei, nu operatiuni
-- asupra unui tenant — aceeasi clasa ca `rls.resolve_tenant_by_subdomain` si `rls.auth_*` (0016,
-- 0028), care nu logheaza. Scrierile consolei (P-4, P-12) logheaza, prin `privileged_run`.
--
-- Lectia lui 0028 / ADR-043: REVOKE si GRANT EXECUTE se dau CA PROPRIETAR al functiei, adica sub
-- `SET LOCAL ROLE evidenta_rls`, altfel sunt WARNING si nu fac nimic. Granturile pe tabele se dau
-- dupa RESET ROLE, ca proprietar al tabelelor.

SET LOCAL ROLE evidenta_rls;

-- --- paznicul: cine intreaba, si de unde -----------------------------------------------------
CREATE OR REPLACE FUNCTION rls.console_caller_role() RETURNS text
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public, app, rls, pg_temp AS $fn$
DECLARE
    v_role text;
BEGIN
    IF NULLIF(current_setting('app.tenant_id', true), '') IS NOT NULL THEN
        RAISE EXCEPTION 'evidenta: consola nu se citeste dintr-un context de tenant'
            USING ERRCODE = '42501';
    END IF;
    SELECT s.staff_role INTO v_role
      FROM platform_staff s
     WHERE s.user_id = app.current_user_id()
       AND s.revoked_at IS NULL;
    IF v_role IS NULL THEN
        RAISE EXCEPTION 'evidenta: apelantul nu este angajat al platformei'
            USING ERRCODE = '42501';
    END IF;
    RETURN v_role;
END
$fn$;

-- --- spatiile: randul din `tenant`, fara continut -------------------------------------------
CREATE OR REPLACE FUNCTION rls.console_tenants()
RETURNS TABLE (
    id uuid, subdomain text, legal_name text, legal_form text, idno text, status text,
    claimed_at timestamptz, suspended_at timestamptz, offboarding_started_at timestamptz,
    archived_at timestamptz, created_at timestamptz,
    company_count bigint, member_count bigint
)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public, app, rls, pg_temp AS $fn$
BEGIN
    PERFORM rls.console_caller_role();
    RETURN QUERY
    SELECT t.id, t.subdomain::text, t.legal_name, t.legal_form, t.idno, t.status,
           t.claimed_at, t.suspended_at, t.offboarding_started_at, t.archived_at, t.created_at,
           (SELECT count(*) FROM company c WHERE c.tenant_id = t.id),
           (SELECT count(*) FROM membership m WHERE m.tenant_id = t.id AND m.status = 'active')
      FROM tenant t
     ORDER BY t.created_at, t.subdomain;
END
$fn$;

-- --- angajatii platformei, cu istoric --------------------------------------------------------
CREATE OR REPLACE FUNCTION rls.console_staff()
RETURNS TABLE (
    user_id uuid, email text, full_name text, staff_role text,
    granted_by_email text, granted_at timestamptz, revoked_at timestamptz
)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public, app, rls, pg_temp AS $fn$
BEGIN
    PERFORM rls.console_caller_role();
    RETURN QUERY
    SELECT s.user_id, u.email::text, u.full_name, s.staff_role,
           g.email::text, s.granted_at, s.revoked_at
      FROM platform_staff s
      JOIN "user" u ON u.id = s.user_id
      JOIN "user" g ON g.id = s.granted_by_user_id
     ORDER BY s.revoked_at IS NOT NULL, s.granted_at;
END
$fn$;

-- Contul din spatele unei adrese, ca sa poata fi facut angajat. Doar conturi active si doar
-- identificatorul si numele: adresa a fost tastata de apelant, deci nu i se dezvaluie nimic
-- ce n-a stiut deja.
CREATE OR REPLACE FUNCTION rls.console_user_by_email(p_email text)
RETURNS TABLE (user_id uuid, full_name text)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public, app, rls, pg_temp AS $fn$
BEGIN
    PERFORM rls.console_caller_role();
    RETURN QUERY
    SELECT u.id, u.full_name
      FROM "user" u
     WHERE u.email = p_email::citext
       AND u.is_active;
END
$fn$;

-- --- jurnalul cailor privilegiate ------------------------------------------------------------
-- `platform_log`: rolul aplicatiei n-are niciun privilegiu pe tabela (spec-a §6.3) — pana azi
-- n-o citea nimeni prin aplicatie. Acum o citeste consola, prin aceasta functie si atat.
CREATE OR REPLACE FUNCTION rls.console_privileged_log(p_path text, p_subdomain text, p_limit integer)
RETURNS TABLE (
    id bigint, occurred_at timestamptz, path_code text, actor text, actor_user_id uuid,
    actor_email text, subject_tenant_id uuid, subject_subdomain text, tenant_count integer,
    request_id text, justification text, payload jsonb
)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public, app, rls, pg_temp AS $fn$
BEGIN
    PERFORM rls.console_caller_role();
    RETURN QUERY
    SELECT l.id, l.occurred_at, l.path_code::text, l.actor, l.actor_user_id,
           u.email::text, l.subject_tenant_id, t.subdomain::text, l.tenant_count,
           l.request_id, l.justification, l.payload
      FROM privileged_access_log l
      LEFT JOIN "user" u ON u.id = l.actor_user_id
      LEFT JOIN tenant t ON t.id = l.subject_tenant_id
     WHERE (p_path IS NULL OR l.path_code = p_path)
       AND (p_subdomain IS NULL OR t.subdomain = p_subdomain)
     ORDER BY l.occurred_at DESC, l.id DESC
     LIMIT LEAST(GREATEST(COALESCE(p_limit, 100), 1), 500);
END
$fn$;

-- --- capabilitati: activarile, cu spatiul si compania lor ------------------------------------
CREATE OR REPLACE FUNCTION rls.console_capabilities()
RETURNS TABLE (
    id uuid, subdomain text, legal_name text, company_id uuid, company_legal_name text,
    company_idno text, capability_key text, effective_from date, effective_to date,
    initialisation_state text, source text, activated_at timestamptz
)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public, app, rls, pg_temp AS $fn$
BEGIN
    PERFORM rls.console_caller_role();
    RETURN QUERY
    SELECT a.id, t.subdomain::text, t.legal_name, a.company_id, c.legal_name, c.idno::text,
           a.capability_key, a.effective_from, a.effective_to,
           a.initialisation_state, a.source, a.activated_at
      FROM capability_activation a
      JOIN tenant t ON t.id = a.tenant_id
      LEFT JOIN company c ON c.id = a.company_id
     ORDER BY t.subdomain, c.legal_name, a.capability_key, a.effective_from;
END
$fn$;

-- --- ringuri de lansare si suprascrieri de flaguri -------------------------------------------
CREATE OR REPLACE FUNCTION rls.console_release_rings()
RETURNS TABLE (subdomain text, legal_name text, ring_code text, assigned_at timestamptz, assigned_by_email text)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public, app, rls, pg_temp AS $fn$
BEGIN
    PERFORM rls.console_caller_role();
    RETURN QUERY
    SELECT t.subdomain::text, t.legal_name, r.ring_code::text, r.assigned_at, u.email::text
      FROM tenant_release_ring r
      JOIN tenant t ON t.id = r.tenant_id
      LEFT JOIN "user" u ON u.id = r.assigned_by_user_id
     ORDER BY t.subdomain;
END
$fn$;

CREATE OR REPLACE FUNCTION rls.console_flag_overrides()
RETURNS TABLE (
    id uuid, subdomain text, legal_name text, flag_key text, state boolean, reason text,
    expires_at timestamptz, created_at timestamptz, created_by_email text
)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public, app, rls, pg_temp AS $fn$
BEGIN
    PERFORM rls.console_caller_role();
    RETURN QUERY
    SELECT o.id, t.subdomain::text, t.legal_name, o.flag_key::text, o.state, o.reason,
           o.expires_at, o.created_at, u.email::text
      FROM feature_flag_override o
      JOIN tenant t ON t.id = o.tenant_id
      LEFT JOIN "user" u ON u.id = o.created_by_user_id
     ORDER BY t.subdomain, o.flag_key, o.created_at;
END
$fn$;

-- Ca proprietar al functiilor: PUBLIC pierde tot, rolul aplicatiei primeste EXECUTE una cate una.
-- `console_caller_role` ramane interna — o apeleaza celelalte, care ruleaza deja ca evidenta_rls.
REVOKE ALL ON FUNCTION rls.console_caller_role()                          FROM PUBLIC;
REVOKE ALL ON FUNCTION rls.console_tenants()                              FROM PUBLIC;
REVOKE ALL ON FUNCTION rls.console_staff()                                FROM PUBLIC;
REVOKE ALL ON FUNCTION rls.console_user_by_email(text)                    FROM PUBLIC;
REVOKE ALL ON FUNCTION rls.console_privileged_log(text, text, integer)    FROM PUBLIC;
REVOKE ALL ON FUNCTION rls.console_capabilities()                         FROM PUBLIC;
REVOKE ALL ON FUNCTION rls.console_release_rings()                        FROM PUBLIC;
REVOKE ALL ON FUNCTION rls.console_flag_overrides()                       FROM PUBLIC;

GRANT EXECUTE ON FUNCTION rls.console_tenants()                           TO evidenta_app;
GRANT EXECUTE ON FUNCTION rls.console_staff()                             TO evidenta_app;
GRANT EXECUTE ON FUNCTION rls.console_user_by_email(text)                 TO evidenta_app;
GRANT EXECUTE ON FUNCTION rls.console_privileged_log(text, text, integer) TO evidenta_app;
GRANT EXECUTE ON FUNCTION rls.console_capabilities()                      TO evidenta_app;
GRANT EXECUTE ON FUNCTION rls.console_release_rings()                     TO evidenta_app;
GRANT EXECUTE ON FUNCTION rls.console_flag_overrides()                    TO evidenta_app;

RESET ROLE;

-- BYPASSRLS spune „politicile nu se aplica"; GRANT spune „ai voie sa atingi tabela" (0028).
-- Idempotent pe cele deja acordate (tenant, company, membership, "user", feature_flag).
GRANT SELECT ON tenant, company, membership, "user"           TO evidenta_rls;
GRANT SELECT ON platform_staff                                TO evidenta_rls;
GRANT SELECT ON privileged_access_log                         TO evidenta_rls;
GRANT SELECT ON capability_activation                         TO evidenta_rls;
GRANT SELECT ON tenant_release_ring, feature_flag_override    TO evidenta_rls;
