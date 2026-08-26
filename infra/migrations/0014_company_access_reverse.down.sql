-- Inversul corectat al lui 0014_company_access.up.sql — ADR-043, `OD-64`.
--
-- Inlocuieste `0014_company_access.down.sql`, care NU rulează: functiile din schema `rls` sunt
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

REVOKE ALL ON company_access FROM evidenta_rls;
REVOKE ALL ON company_access FROM evidenta_app;

DROP POLICY IF EXISTS company_access_self ON company_access;

ALTER TABLE company_access NO FORCE ROW LEVEL SECURITY;
ALTER TABLE company_access DISABLE ROW LEVEL SECURITY;

SET LOCAL ROLE evidenta_rls;
DROP FUNCTION IF EXISTS rls.revoke_engagement_company_access(uuid);
RESET ROLE;
