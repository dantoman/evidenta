-- Inversa lui 0054_sales_documents.up.sql (ADR-012).

REVOKE ALL ON sales_document, proforma_document, customer_order FROM evidenta_app;

DROP POLICY IF EXISTS customer_order_access ON customer_order;
DROP POLICY IF EXISTS proforma_document_access ON proforma_document;
DROP POLICY IF EXISTS sales_document_access ON sales_document;

ALTER TABLE customer_order    NO FORCE ROW LEVEL SECURITY;
ALTER TABLE customer_order    DISABLE ROW LEVEL SECURITY;
ALTER TABLE proforma_document NO FORCE ROW LEVEL SECURITY;
ALTER TABLE proforma_document DISABLE ROW LEVEL SECURITY;
ALTER TABLE sales_document    NO FORCE ROW LEVEL SECURITY;
ALTER TABLE sales_document    DISABLE ROW LEVEL SECURITY;

DROP TRIGGER IF EXISTS customer_order_follows_its_document ON customer_order;
DROP TRIGGER IF EXISTS proforma_document_follows_its_document ON proforma_document;
DROP TRIGGER IF EXISTS sales_document_follows_its_document ON sales_document;

-- Functiile din schema `rls` se sterg SUB ROLUL CARE LE DETINE. `evidenta_owner`
-- e NOINHERIT, deci apartenenta la `evidenta_rls` nu ii da nimic fara SET ROLE,
-- iar DROP-ul ar muri cu „must be owner of function" (`OD-64`, ADR-043 §2).
SET LOCAL ROLE evidenta_rls;
DROP FUNCTION IF EXISTS rls.sales_content_follows_its_document();
RESET ROLE;
