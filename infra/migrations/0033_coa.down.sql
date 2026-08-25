-- Inversul lui 0033_coa.up.sql (ADR-012). Tabelele le sterge migrarea Django;
-- aici se desface doar ce a adaugat SQL-ul manual.

REVOKE ALL ON company_chart, company_account FROM evidenta_app;
REVOKE ALL ON coa_template, coa_template_account FROM evidenta_app;
GRANT INSERT, UPDATE, DELETE ON coa_template, coa_template_account TO evidenta_app;

DROP POLICY IF EXISTS company_account_access      ON company_account;
DROP POLICY IF EXISTS company_chart_access        ON company_chart;
DROP POLICY IF EXISTS coa_template_account_read   ON coa_template_account;
DROP POLICY IF EXISTS coa_template_read           ON coa_template;

ALTER TABLE company_account      NO FORCE ROW LEVEL SECURITY;
ALTER TABLE company_account      DISABLE  ROW LEVEL SECURITY;
ALTER TABLE company_chart        NO FORCE ROW LEVEL SECURITY;
ALTER TABLE company_chart        DISABLE  ROW LEVEL SECURITY;
ALTER TABLE coa_template_account NO FORCE ROW LEVEL SECURITY;
ALTER TABLE coa_template_account DISABLE  ROW LEVEL SECURITY;
ALTER TABLE coa_template         NO FORCE ROW LEVEL SECURITY;
ALTER TABLE coa_template         DISABLE  ROW LEVEL SECURITY;

ALTER TABLE coa_template DROP CONSTRAINT IF EXISTS coa_template_no_overlap;

ALTER TABLE company_account      ALTER COLUMN account_code TYPE text;
ALTER TABLE coa_template_account ALTER COLUMN parent_code  TYPE text;
ALTER TABLE coa_template_account ALTER COLUMN account_code TYPE text;
ALTER TABLE coa_template         ALTER COLUMN code         TYPE text;
