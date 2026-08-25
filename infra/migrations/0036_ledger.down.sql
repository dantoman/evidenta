-- Inversul lui 0036_ledger.up.sql (ADR-012). Tabelele le sterge migrarea Django;
-- aici se desface doar ce a adaugat SQL-ul manual.

REVOKE ALL ON journal_entry, journal_line, company_dimension FROM evidenta_app;
REVOKE ALL ON journal_entry, journal_line FROM evidenta_rls;
REVOKE ALL ON period FROM evidenta_rls;

DROP POLICY IF EXISTS company_dimension_access ON company_dimension;
DROP POLICY IF EXISTS journal_line_access      ON journal_line;
DROP POLICY IF EXISTS journal_entry_access     ON journal_entry;

ALTER TABLE company_dimension NO FORCE ROW LEVEL SECURITY;
ALTER TABLE company_dimension DISABLE  ROW LEVEL SECURITY;
ALTER TABLE journal_line      NO FORCE ROW LEVEL SECURITY;
ALTER TABLE journal_line      DISABLE  ROW LEVEL SECURITY;
ALTER TABLE journal_entry     NO FORCE ROW LEVEL SECURITY;
ALTER TABLE journal_entry     DISABLE  ROW LEVEL SECURITY;

DROP TRIGGER IF EXISTS journal_entry_needs_open_period  ON journal_entry;
DROP TRIGGER IF EXISTS journal_line_stays_immutable     ON journal_line;
DROP TRIGGER IF EXISTS journal_entry_stays_immutable    ON journal_entry;
DROP TRIGGER IF EXISTS journal_entry_balance_at_commit  ON journal_entry;
DROP TRIGGER IF EXISTS journal_line_maintains_totals    ON journal_line;

DROP FUNCTION IF EXISTS rls.journal_entry_period_open();
DROP FUNCTION IF EXISTS rls.journal_line_immutable();
DROP FUNCTION IF EXISTS rls.journal_entry_immutable();
DROP FUNCTION IF EXISTS rls.journal_entry_balanced();
DROP FUNCTION IF EXISTS rls.journal_entry_totals();

ALTER TABLE journal_entry ALTER COLUMN entry_number TYPE text;
