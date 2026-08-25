-- =============================================================================
-- F0.1.2 — Schema `app` și funcțiile de context, fail-closed
--
-- Autoritate:  docs/decisions/004-company-context.md
--              docs/specs/spec-a-tenancy.md §2.3, §3.1
--
-- Rulează ca evidenta_owner. Idempotent.
--
-- Contextul absent produce EROARE, nu zero rânduri. Ambele satisfac invariantul 3,
-- dar eroarea e de preferat: o interogare care returnează zero rânduri arată ca un
-- rezultat legitim și trece prin teste.
--
-- Excepțiile de la regulă sunt deliberate și enumerate mai jos: firma și compania.
-- =============================================================================

\set ON_ERROR_STOP on

-- Două scheme, cu proprietari diferiți, și diferența contează:
--   app  — funcții de context, deținute de evidenta_owner. Citesc doar GUC-uri.
--   rls  — predicate de acces, deținute de evidenta_rls (BYPASSRLS). Citesc tabele.
-- Separarea face ca „ce rulează privilegiat" să fie o proprietate a schemei, nu o
-- notă de subsol: tot ce e în `rls` ocolește politicile, și nimic altceva nu o face.
CREATE SCHEMA IF NOT EXISTS app AUTHORIZATION evidenta_owner;
CREATE SCHEMA IF NOT EXISTS rls AUTHORIZATION evidenta_rls;

-- --- obligatorii: absența lor este refuz ------------------------------------

CREATE OR REPLACE FUNCTION app.current_tenant_id() RETURNS uuid
LANGUAGE plpgsql STABLE AS $fn$
DECLARE v text := current_setting('app.tenant_id', true);
BEGIN
    IF v IS NULL OR v = '' THEN
        RAISE EXCEPTION 'evidenta: lipseste contextul de tenant'
            USING ERRCODE = '42501';
    END IF;
    RETURN v::uuid;
END
$fn$;

CREATE OR REPLACE FUNCTION app.current_user_id() RETURNS uuid
LANGUAGE plpgsql STABLE AS $fn$
DECLARE v text := current_setting('app.user_id', true);
BEGIN
    IF v IS NULL OR v = '' THEN
        RAISE EXCEPTION 'evidenta: lipseste contextul de utilizator'
            USING ERRCODE = '42501';
    END IF;
    RETURN v::uuid;
END
$fn$;

CREATE OR REPLACE FUNCTION app.current_request_id() RETURNS text
LANGUAGE plpgsql STABLE AS $fn$
DECLARE v text := current_setting('app.request_id', true);
BEGIN
    IF v IS NULL OR v = '' THEN
        RAISE EXCEPTION 'evidenta: lipseste corelatorul de cerere'
            USING ERRCODE = '42501';
    END IF;
    RETURN v;
END
$fn$;

-- --- opționale: absența lor este legitimă -----------------------------------

-- Un membru al tenantului nu acționează prin firmă. NULL este starea normală.
CREATE OR REPLACE FUNCTION app.current_actor_firm_id() RETURNS uuid
LANGUAGE sql STABLE AS $fn$
    SELECT NULLIF(current_setting('app.actor_firm_id', true), '')::uuid;
$fn$;

-- ADR-004: app.company_id ÎNGUSTEAZĂ, nu acordă. NULL înseamnă „toate companiile
-- la care utilizatorul are drept", nu „toate companiile". Nu este mecanism de
-- securitate: izolarea între companiile aceluiași tenant se face prin
-- rls.has_company_access() din 0003.
CREATE OR REPLACE FUNCTION app.current_company_id() RETURNS uuid
LANGUAGE sql STABLE AS $fn$
    SELECT NULLIF(current_setting('app.company_id', true), '')::uuid;
$fn$;

-- --- privilegii -------------------------------------------------------------

REVOKE ALL ON SCHEMA app FROM PUBLIC;
GRANT USAGE ON SCHEMA app TO evidenta_app, evidenta_rls;

-- Granturile pe schema `rls` se dau în 0003, de către proprietarul ei.
-- evidenta_owner o creează, dar nu o deține — deci nu poate acorda pe ea.

REVOKE ALL ON FUNCTION app.current_tenant_id(), app.current_user_id(),
                       app.current_request_id(), app.current_actor_firm_id(),
                       app.current_company_id()
    FROM PUBLIC;

GRANT EXECUTE ON FUNCTION app.current_tenant_id(), app.current_user_id(),
                          app.current_request_id(), app.current_actor_firm_id(),
                          app.current_company_id()
    TO evidenta_app;

-- Predicatele din 0003 au nevoie de identitatea utilizatorului.
GRANT EXECUTE ON FUNCTION app.current_user_id(), app.current_actor_firm_id()
    TO evidenta_rls;
