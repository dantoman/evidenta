-- Inversa lui 0075_platform_staff.up.sql (ADR-012).
--
-- Tabela o sterge migrarea Django care a creat-o; aici se desfac doar politicile si
-- privilegiile, in ordinea inversa acordarii.

REVOKE ALL ON platform_staff FROM evidenta_refdata;
REVOKE ALL ON platform_staff FROM evidenta_app;

DROP POLICY IF EXISTS platform_staff_refdata_write ON platform_staff;
DROP POLICY IF EXISTS platform_staff_self          ON platform_staff;

ALTER TABLE platform_staff NO FORCE ROW LEVEL SECURITY;
ALTER TABLE platform_staff DISABLE  ROW LEVEL SECURITY;
