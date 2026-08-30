-- Inversul lui 0063_employment_relationship_type.up.sql. Tabela e stearsa de
-- migrarea Django; aici se desface doar ce a adaugat SQL-ul manual.

REVOKE SELECT ON employment_relationship_type FROM evidenta_rls;
REVOKE SELECT ON employment_relationship_type FROM evidenta_app;

DROP POLICY IF EXISTS employment_relationship_type_write ON employment_relationship_type;
DROP POLICY IF EXISTS employment_relationship_type_read  ON employment_relationship_type;

ALTER TABLE employment_relationship_type NO FORCE ROW LEVEL SECURITY;
ALTER TABLE employment_relationship_type DISABLE  ROW LEVEL SECURITY;
