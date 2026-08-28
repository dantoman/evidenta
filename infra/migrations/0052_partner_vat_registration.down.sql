-- Inversa lui 0052_partner_vat_registration.up.sql (ADR-012).

REVOKE ALL ON partner_vat_registration FROM evidenta_app;
DROP POLICY IF EXISTS partner_vat_registration_access ON partner_vat_registration;
ALTER TABLE partner_vat_registration NO FORCE ROW LEVEL SECURITY;
ALTER TABLE partner_vat_registration DISABLE ROW LEVEL SECURITY;
ALTER TABLE partner_vat_registration ALTER COLUMN vat_code TYPE text;
