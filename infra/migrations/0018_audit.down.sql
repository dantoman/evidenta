-- Inversa lui 0018_audit.up.sql (ADR-012).

REVOKE ALL ON audit_event FROM evidenta_app;
REVOKE ALL ON SEQUENCE audit_event_id_seq FROM evidenta_app;

DROP POLICY IF EXISTS audit_event_append ON audit_event;
DROP POLICY IF EXISTS audit_event_read ON audit_event;

ALTER TABLE audit_event NO FORCE ROW LEVEL SECURITY;
ALTER TABLE audit_event DISABLE ROW LEVEL SECURITY;
