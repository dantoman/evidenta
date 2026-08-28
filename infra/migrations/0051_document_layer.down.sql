-- Inversa lui 0051_document_layer.up.sql (ADR-012).

REVOKE ALL ON document_line, reversal_document FROM evidenta_app;
REVOKE SELECT ON document FROM evidenta_rls;

DROP TRIGGER IF EXISTS reversal_document_follows_its_document ON reversal_document;
DROP TRIGGER IF EXISTS document_line_follows_its_document ON document_line;
DROP TRIGGER IF EXISTS document_stays_frozen ON document;

-- Functiile din schema `rls` se sterg SUB ROLUL CARE LE DETINE. `evidenta_owner`
-- e NOINHERIT, deci apartenenta la `evidenta_rls` nu ii da nimic fara SET ROLE,
-- iar DROP-ul ar muri cu „must be owner of function" (`OD-64`, ADR-043 §2).
SET LOCAL ROLE evidenta_rls;
DROP FUNCTION IF EXISTS rls.follows_its_document();
DROP FUNCTION IF EXISTS rls.document_stays_frozen();
RESET ROLE;

DROP POLICY IF EXISTS reversal_document_access ON reversal_document;
DROP POLICY IF EXISTS document_line_access ON document_line;

ALTER TABLE reversal_document NO FORCE ROW LEVEL SECURITY;
ALTER TABLE reversal_document DISABLE ROW LEVEL SECURITY;
ALTER TABLE document_line     NO FORCE ROW LEVEL SECURITY;
ALTER TABLE document_line     DISABLE ROW LEVEL SECURITY;

ALTER TABLE document_line ALTER COLUMN vat_rate_key    TYPE text;
ALTER TABLE document_line ALTER COLUMN vat_regime_code TYPE text;
ALTER TABLE document_line ALTER COLUMN unit_code       TYPE text;
ALTER TABLE document      ALTER COLUMN external_number TYPE text;
