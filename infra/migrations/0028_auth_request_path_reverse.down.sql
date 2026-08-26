-- Inversul corectat al lui 0028_auth_request_path.up.sql — ADR-043, `OD-64`.
--
-- Inlocuieste `0028_auth_request_path.down.sql`, care NU rulează: functiile din schema `rls` sunt
-- create sub `SET LOCAL ROLE evidenta_rls` si sterse ca owner, iar
-- `evidenta_owner` e `NOINHERIT` — deci `DROP` cade cu „must be owner of function".
--
-- Fisierul vechi nu se editeaza: `C31` il face append-only din clipa in care a
-- fost aplicat. Corectia este un fisier nou, si asta este el.
--
-- ORDINEA E PARTE DIN CONTRACT: triggere, apoi politici, apoi functii. Fiecare
-- `DROP` numit. **Fara `CASCADE`** — un `CASCADE` nu se opreste la ce a creat
-- migrarea asta: poate sterge obiecte atasate intre timp de alta migrare de
-- aceeasi functie, tacut, raportand succes.
--
-- DE CE ESTE REVERSIBIL, si motivul NU e cel evident.
--
-- Migrarea de dus adauga `user_session.token_hash` si umple randurile existente
-- cu o santinela. Inversul sterge coloana, deci sterge fiecare amprenta de
-- token din sistem.
--
-- Argumentul tentant — „sterge doar datele pe care el le-a creat" — este ADEVARAT
-- AZI si se rupe tacut: din clipa in care productia scrie token-uri reale, inversul
-- sterge date pe care nu le-a creat el. Cine aplica peste un an rationamentul
-- „date auto-create" unei coloane care nu e efemera ajunge la concluzia gresita.
--
-- Motivul real este REGENERABILITATEA: o amprenta de token e efemera prin
-- natura ei. Nu se pierde informatie, se pierd sesiuni.
--
-- CONSECINTA OPERATIONALA, de stiut inainte de a rula asta in productie:
-- **toata lumea se delogheaza.** Nu e defect, e efectul; dar cine deruleaza
-- inapoi trebuie sa-l stie dinainte, nu dupa.

DROP INDEX IF EXISTS user_session_token_hash_key;

REVOKE ALL ON "user"          FROM evidenta_rls;
REVOKE ALL ON mfa_method      FROM evidenta_rls;
REVOKE ALL ON mfa_backup_code FROM evidenta_rls;
REVOKE ALL ON user_session    FROM evidenta_rls;

ALTER TABLE user_session DROP COLUMN IF EXISTS token_hash;

SET LOCAL ROLE evidenta_rls;
DROP FUNCTION IF EXISTS rls.resolve_session(text);
DROP FUNCTION IF EXISTS rls.auth_spend_backup_code(uuid);
DROP FUNCTION IF EXISTS rls.auth_backup_codes(uuid);
DROP FUNCTION IF EXISTS rls.auth_mfa_methods(uuid);
DROP FUNCTION IF EXISTS rls.auth_lookup_user(citext);
RESET ROLE;
