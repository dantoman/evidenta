-- =============================================================================
-- OD-67 — Rolul de încărcare a datelor de referință
--
-- Autoritate:  docs/decisions/049-rolul-de-date-de-referinta.md (ADR-049)
--              docs/specs/spec-a-tenancy.md §2.2, §6
--
-- Rulează ca superuser, o singură dată per cluster. Este idempotent.
--
--   psql -v refdata_password="$REFDATA_PW" -f 0004_refdata_role.sql
--
-- Al patrulea rol. Nu e al patrulea „din comoditate": tabelele globale de
-- referință — parametri fiscali, versiuni de logică, cursuri BNM, planul de
-- conturi, registrul de contrapărți — sunt scrise de un proces care rulează în
-- producție, dar nu la fiecare cerere. Rolul aplicației nu are voie să le scrie
-- (un tenant nu declară cotele pentru toți), iar rolul de migrare are alt ciclu
-- de viață și deține schema: un încărcător rulat ca owner poate face ALTER TABLE
-- din greșeală. Un rol cu ciclul de viață al încărcării, care nu deține nimic și
-- nu ocolește nicio politică, este singurul care spune exact ce face.
--
-- Ce primește: CONNECT, USAGE pe schema publică. Nimic altceva aici.
-- Privilegiile pe tabele se acordă punctual, în migrația fiecărei tabele de
-- referință, alături de politica `TO evidenta_refdata` — și sunt enumerate în
-- `infra/rls/exceptions.toml` prin `writer_role`, ca gardianul de model să poată
-- refuza orice tabelă pe care rolul o poate scrie fără s-o declare.
--
-- Ce NU primește, deliberat: privilegii implicite (`ALTER DEFAULT PRIVILEGES`).
-- Rolul aplicației le are fiindcă fiecare tabelă business îi aparține la runtime;
-- acesta nu atinge nicio tabelă business, deci fiecare GRANT către el este o
-- decizie scrisă, ca la `evidenta_rls`.
-- =============================================================================

\set ON_ERROR_STOP on

DO $roles$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'evidenta_refdata') THEN
        CREATE ROLE evidenta_refdata NOINHERIT LOGIN;
    END IF;
END
$roles$;

ALTER ROLE evidenta_refdata PASSWORD :'refdata_password';

-- Atributele se impun explicit, ca o rulare peste o bază veche să le corecteze.
ALTER ROLE evidenta_refdata NOBYPASSRLS NOSUPERUSER NOCREATEROLE NOCREATEDB NOINHERIT LOGIN;

DO $dbgrant$
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO evidenta_refdata', current_database());
END
$dbgrant$;

GRANT USAGE ON SCHEMA public TO evidenta_refdata;

-- --- verificări care fac diferența între un rol îngust și un al doilea owner --
DO $checks$
BEGIN
    IF (SELECT rolbypassrls FROM pg_roles WHERE rolname = 'evidenta_refdata') THEN
        RAISE EXCEPTION 'evidenta_refdata nu are voie cu BYPASSRLS';
    END IF;

    IF (SELECT rolsuper FROM pg_roles WHERE rolname = 'evidenta_refdata') THEN
        RAISE EXCEPTION 'evidenta_refdata nu are voie sa fie superuser';
    END IF;

    IF pg_has_role('evidenta_refdata', 'evidenta_rls', 'USAGE') THEN
        RAISE EXCEPTION 'evidenta_refdata nu are voie sa fie membru al lui evidenta_rls';
    END IF;

    IF pg_has_role('evidenta_refdata', 'evidenta_owner', 'USAGE') THEN
        RAISE EXCEPTION 'evidenta_refdata nu are voie sa fie membru al lui evidenta_owner';
    END IF;

    IF has_schema_privilege('evidenta_refdata', 'public', 'CREATE') THEN
        RAISE EXCEPTION 'evidenta_refdata nu are voie sa creeze obiecte: nu detine schema';
    END IF;
END
$checks$;
