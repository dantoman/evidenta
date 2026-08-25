-- Inversul lui 0035_periods.up.sql (ADR-012). Tabelele le sterge migrarea
-- Django; aici se desface doar ce a adaugat SQL-ul manual.

REVOKE ALL ON fiscal_year, period FROM evidenta_app;

DROP POLICY IF EXISTS period_access      ON period;
DROP POLICY IF EXISTS fiscal_year_access ON fiscal_year;

ALTER TABLE period      NO FORCE ROW LEVEL SECURITY;
ALTER TABLE period      DISABLE  ROW LEVEL SECURITY;
ALTER TABLE fiscal_year NO FORCE ROW LEVEL SECURITY;
ALTER TABLE fiscal_year DISABLE  ROW LEVEL SECURITY;

DROP TRIGGER IF EXISTS period_locked_is_terminal ON period;
DROP FUNCTION IF EXISTS period_locked_is_terminal();

ALTER TABLE period      DROP CONSTRAINT IF EXISTS period_is_one_calendar_month;
ALTER TABLE fiscal_year DROP CONSTRAINT IF EXISTS fiscal_year_at_most_twelve_months;
ALTER TABLE period      DROP CONSTRAINT IF EXISTS period_no_overlap;
ALTER TABLE fiscal_year DROP CONSTRAINT IF EXISTS fiscal_year_no_overlap;

ALTER TABLE fiscal_year ALTER COLUMN code TYPE text;
