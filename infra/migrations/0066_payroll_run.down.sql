-- Inversul lui 0066_payroll_run.up.sql. Tabelele sunt sterse de migrarea Django.
--
-- Functia din schema `rls` se sterge SUB `evidenta_rls`: owner-ul e NOINHERIT,
-- deci DROP-ul ca owner ar muri cu „must be owner of function" (ADR-043, OD-64).

DROP TRIGGER IF EXISTS payroll_line_frozen ON payroll_line;

SET LOCAL ROLE evidenta_rls;
DROP FUNCTION IF EXISTS rls.payroll_line_frozen();
RESET ROLE;

REVOKE ALL ON payroll_run  FROM evidenta_rls;
REVOKE ALL ON payroll_line FROM evidenta_app;
REVOKE ALL ON payroll_run  FROM evidenta_app;

DROP POLICY IF EXISTS payroll_line_access ON payroll_line;
DROP POLICY IF EXISTS payroll_run_access  ON payroll_run;

ALTER TABLE payroll_line NO FORCE ROW LEVEL SECURITY;
ALTER TABLE payroll_line DISABLE  ROW LEVEL SECURITY;
ALTER TABLE payroll_run  NO FORCE ROW LEVEL SECURITY;
ALTER TABLE payroll_run  DISABLE  ROW LEVEL SECURITY;
