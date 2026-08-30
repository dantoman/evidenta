-- Inversul lui 0069_ipc_declaration.up.sql. Tabelele sunt sterse de migrarea
-- Django. Functia din schema `rls` se sterge SUB `evidenta_rls`: owner-ul e
-- NOINHERIT, deci DROP-ul ca owner ar muri cu „must be owner of function"
-- (ADR-043, OD-64).

DROP TRIGGER IF EXISTS ipc_nominal_line_follows_its_declaration ON ipc_nominal_line;
DROP TRIGGER IF EXISTS ipc_total_line_follows_its_declaration   ON ipc_total_line;

SET LOCAL ROLE evidenta_rls;
DROP FUNCTION IF EXISTS rls.ipc_content_follows_its_declaration();
RESET ROLE;

REVOKE ALL ON ipc_declaration  FROM evidenta_rls;
REVOKE ALL ON ipc_nominal_line FROM evidenta_app;
REVOKE ALL ON ipc_total_line   FROM evidenta_app;
REVOKE ALL ON ipc_declaration  FROM evidenta_app;

DROP POLICY IF EXISTS ipc_nominal_line_access ON ipc_nominal_line;
DROP POLICY IF EXISTS ipc_total_line_access   ON ipc_total_line;
DROP POLICY IF EXISTS ipc_declaration_access  ON ipc_declaration;

ALTER TABLE ipc_nominal_line NO FORCE ROW LEVEL SECURITY;
ALTER TABLE ipc_nominal_line DISABLE  ROW LEVEL SECURITY;
ALTER TABLE ipc_total_line   NO FORCE ROW LEVEL SECURITY;
ALTER TABLE ipc_total_line   DISABLE  ROW LEVEL SECURITY;
ALTER TABLE ipc_declaration  NO FORCE ROW LEVEL SECURITY;
ALTER TABLE ipc_declaration  DISABLE  ROW LEVEL SECURITY;
