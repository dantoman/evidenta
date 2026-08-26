-- Inversul lui 0040_operation_templates.up.sql (ADR-012). Tabelele le sterge
-- migrarea Django; aici se desface doar ce a adaugat SQL-ul manual.

REVOKE ALL ON operation_template_dimension FROM evidenta_app;
REVOKE ALL ON operation_template_line      FROM evidenta_app;
REVOKE ALL ON operation_template           FROM evidenta_app;

DROP POLICY IF EXISTS operation_template_dimension_access ON operation_template_dimension;
DROP POLICY IF EXISTS operation_template_line_access      ON operation_template_line;
DROP POLICY IF EXISTS operation_template_access           ON operation_template;

ALTER TABLE operation_template_dimension NO FORCE ROW LEVEL SECURITY;
ALTER TABLE operation_template_dimension DISABLE  ROW LEVEL SECURITY;
ALTER TABLE operation_template_line      NO FORCE ROW LEVEL SECURITY;
ALTER TABLE operation_template_line      DISABLE  ROW LEVEL SECURITY;
ALTER TABLE operation_template           NO FORCE ROW LEVEL SECURITY;
ALTER TABLE operation_template           DISABLE  ROW LEVEL SECURITY;

ALTER TABLE operation_template_dimension
    DROP CONSTRAINT IF EXISTS operation_template_dimension_same_company;
ALTER TABLE operation_template_line
    DROP CONSTRAINT IF EXISTS operation_template_line_identity_unique;
ALTER TABLE operation_template_line
    DROP CONSTRAINT IF EXISTS operation_template_line_same_company;
ALTER TABLE operation_template
    DROP CONSTRAINT IF EXISTS operation_template_identity_unique;
