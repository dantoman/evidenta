-- Inversa lui 0055_purchase_documents.up.sql (ADR-012).

REVOKE ALL ON purchase_document, supplier_order FROM evidenta_app;

DROP POLICY IF EXISTS supplier_order_access ON supplier_order;
DROP POLICY IF EXISTS purchase_document_access ON purchase_document;

ALTER TABLE supplier_order    NO FORCE ROW LEVEL SECURITY;
ALTER TABLE supplier_order    DISABLE ROW LEVEL SECURITY;
ALTER TABLE purchase_document NO FORCE ROW LEVEL SECURITY;
ALTER TABLE purchase_document DISABLE ROW LEVEL SECURITY;

DROP TRIGGER IF EXISTS supplier_order_follows_its_document ON supplier_order;
DROP TRIGGER IF EXISTS purchase_document_follows_its_document ON purchase_document;

-- Sub rolul care detine functia; `evidenta_owner` e NOINHERIT (ADR-043 §2).
SET LOCAL ROLE evidenta_rls;
DROP FUNCTION IF EXISTS rls.purchase_content_follows_its_document();
RESET ROLE;

ALTER TABLE purchase_document ALTER COLUMN supplier_document_number TYPE text;
