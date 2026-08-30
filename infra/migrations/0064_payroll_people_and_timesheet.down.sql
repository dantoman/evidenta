-- Inversul lui 0064_payroll_people_and_timesheet.up.sql. Tabelele sunt sterse de
-- migrarea Django; aici se desface doar ce a adaugat SQL-ul manual.
--
-- Functia din schema `rls` se sterge SUB `evidenta_rls`, nu ca owner: owner-ul e
-- NOINHERIT, deci apartenenta la `evidenta_rls` nu-i da nimic fara `SET ROLE`, iar
-- DROP-ul ar muri cu „must be owner of function" (ADR-043, OD-64).

DROP TRIGGER IF EXISTS timesheet_day_follows_its_month ON timesheet_day;

SET LOCAL ROLE evidenta_rls;
DROP FUNCTION IF EXISTS rls.timesheet_day_follows_its_month();
RESET ROLE;

DROP POLICY IF EXISTS timesheet_day_access                 ON timesheet_day;
DROP POLICY IF EXISTS timesheet_access                     ON timesheet;
DROP POLICY IF EXISTS employment_contract_amendment_access ON employment_contract_amendment;
DROP POLICY IF EXISTS employment_contract_access           ON employment_contract;
DROP POLICY IF EXISTS employee_access                      ON employee;

ALTER TABLE timesheet_day                 NO FORCE ROW LEVEL SECURITY;
ALTER TABLE timesheet_day                 DISABLE  ROW LEVEL SECURITY;
ALTER TABLE timesheet                     NO FORCE ROW LEVEL SECURITY;
ALTER TABLE timesheet                     DISABLE  ROW LEVEL SECURITY;
ALTER TABLE employment_contract_amendment NO FORCE ROW LEVEL SECURITY;
ALTER TABLE employment_contract_amendment DISABLE  ROW LEVEL SECURITY;
ALTER TABLE employment_contract           NO FORCE ROW LEVEL SECURITY;
ALTER TABLE employment_contract           DISABLE  ROW LEVEL SECURITY;
ALTER TABLE employee                      NO FORCE ROW LEVEL SECURITY;
ALTER TABLE employee                      DISABLE  ROW LEVEL SECURITY;
