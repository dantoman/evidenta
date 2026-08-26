-- Inversul corectat al lui 0015_module_scope_sync.up.sql — ADR-043, `OD-64`.
--
-- Inlocuieste `0015_module_scope_sync.down.sql`, care NU rulează: functiile din schema `rls` sunt
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

REVOKE ALL ON engagement_module_scope FROM evidenta_rls;

DROP TRIGGER IF EXISTS engagement_status_scope_sync ON engagement;
DROP TRIGGER IF EXISTS engagement_module_scope_sync ON engagement_module_scope;

SET LOCAL ROLE evidenta_rls;
DROP FUNCTION IF EXISTS rls.sync_module_scope_liveness();
DROP FUNCTION IF EXISTS rls.sync_module_scope_from_engagement();
RESET ROLE;
