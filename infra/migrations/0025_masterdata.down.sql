-- Inversa lui 0025_masterdata.up.sql (ADR-012).

REVOKE ALL ON partner, company_partner, unit_of_measure, unit_conversion,
    item, item_category FROM evidenta_app;
REVOKE ALL ON counterparty_registry FROM evidenta_app;
GRANT INSERT, UPDATE, DELETE ON counterparty_registry TO evidenta_app;

DROP POLICY IF EXISTS company_partner_access ON company_partner;
DROP POLICY IF EXISTS item_access ON item;
DROP POLICY IF EXISTS item_category_access ON item_category;
DROP POLICY IF EXISTS unit_conversion_access ON unit_conversion;
DROP POLICY IF EXISTS unit_of_measure_access ON unit_of_measure;
DROP POLICY IF EXISTS partner_access ON partner;
DROP POLICY IF EXISTS counterparty_registry_read ON counterparty_registry;

ALTER TABLE company_partner       NO FORCE ROW LEVEL SECURITY;
ALTER TABLE company_partner       DISABLE ROW LEVEL SECURITY;
ALTER TABLE item                  NO FORCE ROW LEVEL SECURITY;
ALTER TABLE item                  DISABLE ROW LEVEL SECURITY;
ALTER TABLE item_category         NO FORCE ROW LEVEL SECURITY;
ALTER TABLE item_category         DISABLE ROW LEVEL SECURITY;
ALTER TABLE unit_conversion       NO FORCE ROW LEVEL SECURITY;
ALTER TABLE unit_conversion       DISABLE ROW LEVEL SECURITY;
ALTER TABLE unit_of_measure       NO FORCE ROW LEVEL SECURITY;
ALTER TABLE unit_of_measure       DISABLE ROW LEVEL SECURITY;
ALTER TABLE partner               NO FORCE ROW LEVEL SECURITY;
ALTER TABLE partner               DISABLE ROW LEVEL SECURITY;
ALTER TABLE counterparty_registry NO FORCE ROW LEVEL SECURITY;
ALTER TABLE counterparty_registry DISABLE ROW LEVEL SECURITY;

ALTER TABLE company_partner ALTER COLUMN payable_account_code TYPE text;
ALTER TABLE company_partner ALTER COLUMN receivable_account_code TYPE text;
ALTER TABLE unit_of_measure ALTER COLUMN code TYPE text;
ALTER TABLE item_category ALTER COLUMN code TYPE text;
ALTER TABLE item ALTER COLUMN barcode TYPE text;
ALTER TABLE item ALTER COLUMN sku TYPE text;
ALTER TABLE partner ALTER COLUMN vat_code TYPE text;
ALTER TABLE partner ALTER COLUMN idnp TYPE text;
ALTER TABLE partner ALTER COLUMN idno TYPE text;
ALTER TABLE counterparty_registry ALTER COLUMN vat_code TYPE text;
ALTER TABLE counterparty_registry ALTER COLUMN idno TYPE text;
