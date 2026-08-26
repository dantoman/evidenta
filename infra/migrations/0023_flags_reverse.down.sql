-- Inversul corectat al lui 0023_flags.up.sql — ADR-043, `OD-64`.
--
-- Inlocuieste `0023_flags.down.sql`, care NU rulează: functiile din schema `rls` sunt
-- create sub `SET LOCAL ROLE evidenta_rls` si sterse ca owner, iar
-- `evidenta_owner` e `NOINHERIT` — deci apartenenta la rol nu-i da privilegiile
-- fara `SET ROLE`, si `DROP` cade cu „must be owner of function".
--
-- Fisierul vechi nu se editeaza: `C31` il face append-only din clipa in care a
-- fost aplicat, iar istoricul trebuie sa arate in continuare ce a rulat inainte.
-- Corectia este un fisier nou, si asta este el.
--
-- ORDINEA E PARTE DIN CONTRACT: triggere, apoi politici, apoi functii. Fiecare
-- `DROP` numit. **Fara `CASCADE`** — un `CASCADE` nu se opreste la ce a creat
-- migrarea asta: poate sterge obiecte atasate intre timp de alta migrare de
-- aceeasi functie, si o face tacut, raportand succes. Daca un `DROP` cade pe
-- dependenta, eroarea e informatie, nu obstacol.

REVOKE ALL ON feature_flag FROM evidenta_rls;
REVOKE ALL ON tenant_release_ring, feature_flag_override FROM evidenta_app;
REVOKE ALL ON feature_flag, release_ring FROM evidenta_app;

DROP TRIGGER IF EXISTS feature_flag_override_no_compliance ON feature_flag_override;

DROP POLICY IF EXISTS feature_flag_override_access ON feature_flag_override;
DROP POLICY IF EXISTS tenant_release_ring_access   ON tenant_release_ring;
DROP POLICY IF EXISTS release_ring_read            ON release_ring;
DROP POLICY IF EXISTS feature_flag_read            ON feature_flag;

ALTER TABLE feature_flag_override NO FORCE ROW LEVEL SECURITY;
ALTER TABLE feature_flag_override DISABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_release_ring   NO FORCE ROW LEVEL SECURITY;
ALTER TABLE tenant_release_ring   DISABLE ROW LEVEL SECURITY;
ALTER TABLE release_ring          NO FORCE ROW LEVEL SECURITY;
ALTER TABLE release_ring          DISABLE ROW LEVEL SECURITY;
ALTER TABLE feature_flag          NO FORCE ROW LEVEL SECURITY;
ALTER TABLE feature_flag          DISABLE ROW LEVEL SECURITY;

ALTER TABLE tenant_release_ring ALTER COLUMN ring_code TYPE text;
ALTER TABLE release_ring ALTER COLUMN code TYPE text;

SET LOCAL ROLE evidenta_rls;
DROP FUNCTION IF EXISTS rls.refuse_compliance_flag_override();
RESET ROLE;
