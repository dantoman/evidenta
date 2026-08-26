-- Inversul corectat al lui 0036_ledger.up.sql — ADR-043, `OD-64`.
--
-- Inlocuieste `0036_ledger.down.sql`, care NU rulează: functiile din schema `rls` sunt
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
-- ATINGE REGISTRUL. Declaratia de reversibilitate a migrarii care il refera este
-- „reversibil, cu invers testat" — nu fiindca registrul ar fi neimportant, ci
-- fiindca acest fisier desface DOAR structura: politici, triggere, functii,
-- colatie. Nu sterge nicio inregistrare si nicio linie. Tabelele insele sunt
-- sterse de migrarea Django, nu de aici.

DROP TRIGGER IF EXISTS journal_entry_needs_open_period  ON journal_entry;
DROP TRIGGER IF EXISTS journal_line_stays_immutable     ON journal_line;
DROP TRIGGER IF EXISTS journal_entry_stays_immutable    ON journal_entry;
DROP TRIGGER IF EXISTS journal_entry_balance_at_commit  ON journal_entry;
DROP TRIGGER IF EXISTS journal_line_maintains_totals    ON journal_line;

DROP POLICY IF EXISTS company_dimension_access ON company_dimension;
DROP POLICY IF EXISTS journal_line_access      ON journal_line;
DROP POLICY IF EXISTS journal_entry_access     ON journal_entry;

ALTER TABLE company_dimension NO FORCE ROW LEVEL SECURITY;
ALTER TABLE company_dimension DISABLE  ROW LEVEL SECURITY;
ALTER TABLE journal_line      NO FORCE ROW LEVEL SECURITY;
ALTER TABLE journal_line      DISABLE  ROW LEVEL SECURITY;
ALTER TABLE journal_entry     NO FORCE ROW LEVEL SECURITY;
ALTER TABLE journal_entry     DISABLE  ROW LEVEL SECURITY;

REVOKE ALL ON journal_entry, journal_line, company_dimension FROM evidenta_app;
REVOKE ALL ON journal_entry, journal_line FROM evidenta_rls;
REVOKE ALL ON period FROM evidenta_rls;

ALTER TABLE journal_entry ALTER COLUMN entry_number TYPE text;

SET LOCAL ROLE evidenta_rls;
DROP FUNCTION IF EXISTS rls.journal_entry_period_open();
DROP FUNCTION IF EXISTS rls.journal_line_immutable();
DROP FUNCTION IF EXISTS rls.journal_entry_immutable();
DROP FUNCTION IF EXISTS rls.journal_entry_balanced();
DROP FUNCTION IF EXISTS rls.journal_entry_totals();
RESET ROLE;
