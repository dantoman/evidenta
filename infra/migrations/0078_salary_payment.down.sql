-- Inversul lui 0078_salary_payment.up.sql. Tabelele si coloana sunt sterse de
-- migrarea Django.
--
-- Functia din schema `rls` se sterge SUB `evidenta_rls`: owner-ul e NOINHERIT,
-- deci DROP-ul ca owner ar muri cu „must be owner of function" (ADR-043, OD-64).

DROP TRIGGER IF EXISTS salary_payment_line_frozen ON salary_payment_line;

DROP POLICY IF EXISTS salary_payment_line_access ON salary_payment_line;
DROP POLICY IF EXISTS salary_payment_access      ON salary_payment;

SET LOCAL ROLE evidenta_rls;
DROP FUNCTION IF EXISTS rls.salary_payment_line_frozen();
RESET ROLE;

REVOKE ALL ON salary_payment      FROM evidenta_rls;
REVOKE ALL ON salary_payment_line FROM evidenta_app;
REVOKE ALL ON salary_payment      FROM evidenta_app;

ALTER TABLE salary_payment_line NO FORCE ROW LEVEL SECURITY;
ALTER TABLE salary_payment_line DISABLE  ROW LEVEL SECURITY;
ALTER TABLE salary_payment      NO FORCE ROW LEVEL SECURITY;
ALTER TABLE salary_payment      DISABLE  ROW LEVEL SECURITY;
