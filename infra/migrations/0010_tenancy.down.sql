-- Inversa lui 0010_tenancy.up.sql. `reverse_sql` nu este opțional (ADR-012):
-- o migrare de politică ireversibilă nu se poate derula înapoi împreună cu
-- tabela pe care o protejează, ceea ce anulează motivul pentru care sunt în
-- aceeași tranzacție.

REVOKE ALL ON tenant, company, company_vat_registration FROM evidenta_app;

DROP POLICY IF EXISTS company_vat_registration_access ON company_vat_registration;
DROP POLICY IF EXISTS company_access ON company;
DROP POLICY IF EXISTS tenant_access ON tenant;

ALTER TABLE company_vat_registration NO FORCE ROW LEVEL SECURITY;
ALTER TABLE company_vat_registration DISABLE ROW LEVEL SECURITY;
ALTER TABLE company NO FORCE ROW LEVEL SECURITY;
ALTER TABLE company DISABLE ROW LEVEL SECURITY;
ALTER TABLE tenant  NO FORCE ROW LEVEL SECURITY;
ALTER TABLE tenant  DISABLE ROW LEVEL SECURITY;

ALTER TABLE company_vat_registration
    DROP CONSTRAINT IF EXISTS company_vat_registration_no_overlap;
ALTER TABLE company_vat_registration ALTER COLUMN vat_code TYPE text;
ALTER TABLE company ALTER COLUMN idno TYPE text;
ALTER TABLE tenant DROP CONSTRAINT IF EXISTS tenant_subdomain_format;
ALTER TABLE tenant ALTER COLUMN subdomain TYPE text;
