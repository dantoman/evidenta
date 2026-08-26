-- Inversul lui 0037_vat_period.up.sql (ADR-012). Tabela o sterge migrarea
-- Django; aici se desface doar ce a adaugat SQL-ul manual.

REVOKE ALL ON vat_period FROM evidenta_app;

DROP POLICY IF EXISTS vat_period_access ON vat_period;

ALTER TABLE vat_period NO FORCE ROW LEVEL SECURITY;
ALTER TABLE vat_period DISABLE  ROW LEVEL SECURITY;

DROP TRIGGER IF EXISTS vat_period_final_is_terminal ON vat_period;
DROP FUNCTION IF EXISTS vat_period_final_is_terminal();

ALTER TABLE vat_period DROP CONSTRAINT IF EXISTS vat_period_monthly_is_one_month;
ALTER TABLE vat_period DROP CONSTRAINT IF EXISTS vat_period_ends_a_month;
ALTER TABLE vat_period DROP CONSTRAINT IF EXISTS vat_period_starts_a_month;
ALTER TABLE vat_period DROP CONSTRAINT IF EXISTS vat_period_no_overlap;
