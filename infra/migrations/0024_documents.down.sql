-- Inversa lui 0024_documents.up.sql (ADR-012).

REVOKE ALL ON document, numbering_template, numbering_counter FROM evidenta_app;
REVOKE ALL ON document_event FROM evidenta_app;
REVOKE ALL ON SEQUENCE document_event_id_seq FROM evidenta_app;

DROP POLICY IF EXISTS document_event_append ON document_event;
DROP POLICY IF EXISTS document_event_read ON document_event;
DROP POLICY IF EXISTS numbering_counter_access ON numbering_counter;
DROP POLICY IF EXISTS numbering_template_access ON numbering_template;
DROP POLICY IF EXISTS document_access ON document;

ALTER TABLE document_event     NO FORCE ROW LEVEL SECURITY;
ALTER TABLE document_event     DISABLE ROW LEVEL SECURITY;
ALTER TABLE numbering_counter  NO FORCE ROW LEVEL SECURITY;
ALTER TABLE numbering_counter  DISABLE ROW LEVEL SECURITY;
ALTER TABLE numbering_template NO FORCE ROW LEVEL SECURITY;
ALTER TABLE numbering_template DISABLE ROW LEVEL SECURITY;
ALTER TABLE document           NO FORCE ROW LEVEL SECURITY;
ALTER TABLE document           DISABLE ROW LEVEL SECURITY;

ALTER TABLE numbering_template ALTER COLUMN series TYPE text;
ALTER TABLE document ALTER COLUMN formatted_number TYPE text;
ALTER TABLE document ALTER COLUMN series TYPE text;
