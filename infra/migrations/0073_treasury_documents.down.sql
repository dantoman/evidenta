-- Inversa lui 0073_treasury_documents.up.sql (ADR-012).

REVOKE ALL ON treasury_document FROM evidenta_app;

DROP POLICY IF EXISTS treasury_document_access ON treasury_document;

ALTER TABLE treasury_document NO FORCE ROW LEVEL SECURITY;
ALTER TABLE treasury_document DISABLE ROW LEVEL SECURITY;

DROP TRIGGER IF EXISTS treasury_document_follows_its_document ON treasury_document;

-- Sub rolul care detine functia; `evidenta_owner` e NOINHERIT (ADR-043 §2).
SET LOCAL ROLE evidenta_rls;
DROP FUNCTION IF EXISTS rls.treasury_content_follows_its_document();
RESET ROLE;
