-- =============================================================================
-- F0.1.1 — Roluri de bază de date
--
-- Autoritate:  docs/decisions/003-rls-tenancy-tables.md
--              docs/specs/spec-a-tenancy.md §2.2
--
-- Rulează ca superuser, o singură dată per cluster. Este idempotent.
--
-- Parolele NU stau în acest fișier:
--   psql -v owner_password="$OWNER_PW" -v app_password="$APP_PW" -f 0001_roles.sql
--
-- Trei roluri, nu două. Al treilea există pentru că `FORCE ROW LEVEL SECURITY`
-- (obligatoriu prin R2) face ca nici proprietarul tabelei să nu mai ocolească
-- politicile — deci o funcție SECURITY DEFINER deținută de rolul de migrare ar
-- fi supusă chiar politicilor pe care încearcă să le rezolve.
-- =============================================================================

\set ON_ERROR_STOP on

-- --- rolul de migrare: deține obiectele, nu se folosește la runtime ----------
DO $roles$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'evidenta_owner') THEN
        CREATE ROLE evidenta_owner NOINHERIT LOGIN;
    END IF;

    -- rolul de aplicație: fără BYPASSRLS, fără ownership, fără CREATE
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'evidenta_app') THEN
        CREATE ROLE evidenta_app NOINHERIT LOGIN;
    END IF;

    -- rolul de rezolvare: deține EXCLUSIV predicatele de acces (0003)
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'evidenta_rls') THEN
        CREATE ROLE evidenta_rls NOINHERIT NOLOGIN BYPASSRLS;
    END IF;
END
$roles$;

ALTER ROLE evidenta_owner PASSWORD :'owner_password';
ALTER ROLE evidenta_app   PASSWORD :'app_password';

-- Atributele se impun explicit, ca o rulare peste o bază veche să le corecteze.
ALTER ROLE evidenta_owner NOBYPASSRLS NOSUPERUSER NOCREATEROLE;
ALTER ROLE evidenta_app   NOBYPASSRLS NOSUPERUSER NOCREATEROLE NOCREATEDB;
ALTER ROLE evidenta_rls   BYPASSRLS   NOSUPERUSER NOCREATEROLE NOLOGIN;

-- Owner-ul poate SET ROLE ca să creeze funcțiile din 0003.
-- BYPASSRLS nu se moștenește prin apartenență — se activează doar prin SET ROLE.
GRANT evidenta_rls TO evidenta_owner;

-- --- privilegii pe baza de date ---------------------------------------------
--
-- Owner-ul creează schemele `app` și `rls` în 0002, ceea ce cere CREATE pe bază.
-- GRANT nu acceptă expresii pentru numele bazei, deci SQL dinamic.
DO $dbgrant$
BEGIN
    EXECUTE format('GRANT CREATE, CONNECT ON DATABASE %I TO evidenta_owner',
                   current_database());
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO evidenta_app', current_database());
END
$dbgrant$;

-- --- extensii ---------------------------------------------------------------
--
-- Stau în acest fișier pentru că el este locul unde se face tot ce cere superuser
-- sau se face o singură dată per bază. (Owner-ul ar putea instala citext după
-- grantul de mai sus — extensia este „de încredere" — dar nu are motiv să o facă
-- de fiecare dată.)
--
-- citext: `user.email` și `tenant.subdomain` sunt insensibile la majuscule
-- (spec-a §1.1, §1.5). Comparația se face de tip, nu prin lower() presărat prin
-- interogări — care se uită exact acolo unde contează, la autentificare.
CREATE EXTENSION IF NOT EXISTS citext;

-- btree_gist: constrângerile de neîntrepătrundere pe interval (`EXCLUDE USING gist`)
-- au nevoie de operatorul `=` pe uuid într-un index gist. Fără ea, „o companie nu
-- poate avea două înregistrări TVA suprapuse" ar rămâne o verificare în serviciu —
-- adică una pe care importul în masă o ocolește.
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- --- schema public ----------------------------------------------------------
REVOKE ALL   ON SCHEMA public FROM PUBLIC;
GRANT  USAGE ON SCHEMA public TO evidenta_app, evidenta_rls;
GRANT  USAGE, CREATE ON SCHEMA public TO evidenta_owner;

-- --- privilegii implicite pentru obiectele create de owner ------------------
ALTER DEFAULT PRIVILEGES FOR ROLE evidenta_owner IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO evidenta_app;
ALTER DEFAULT PRIVILEGES FOR ROLE evidenta_owner IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO evidenta_app;

-- Deliberat: evidenta_rls NU primește privilegii implicite. Are BYPASSRLS, deci
-- fiecare GRANT către el este o decizie. Primește SELECT punctual, în F0.3, doar
-- pe tabelele citite de predicate: membership, company_access, engagement, firm.

-- --- verificări care fac diferența între RLS efectiv și RLS decorativ -------
DO $checks$
BEGIN
    IF (SELECT rolbypassrls FROM pg_roles WHERE rolname = 'evidenta_app') THEN
        RAISE EXCEPTION 'evidenta_app nu are voie cu BYPASSRLS';
    END IF;

    IF (SELECT rolsuper FROM pg_roles WHERE rolname = 'evidenta_app') THEN
        RAISE EXCEPTION 'evidenta_app nu are voie sa fie superuser';
    END IF;

    IF pg_has_role('evidenta_app', 'evidenta_rls', 'USAGE') THEN
        RAISE EXCEPTION 'evidenta_app nu are voie sa fie membru al lui evidenta_rls';
    END IF;

    IF NOT (SELECT rolbypassrls FROM pg_roles WHERE rolname = 'evidenta_rls') THEN
        RAISE EXCEPTION 'evidenta_rls trebuie sa aiba BYPASSRLS, altfel predicatele recurseaza';
    END IF;

    IF (SELECT rolcanlogin FROM pg_roles WHERE rolname = 'evidenta_rls') THEN
        RAISE EXCEPTION 'evidenta_rls nu are voie sa se autentifice';
    END IF;
END
$checks$;
