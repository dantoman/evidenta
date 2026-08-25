-- Inversul lui 0027_fiscal.up.sql. Tabelele sunt sterse de migrarea Django;
-- aici se desface doar ce a adaugat SQL-ul manual.

ALTER TABLE fiscal_logic_version DROP CONSTRAINT IF EXISTS fiscal_logic_version_no_overlap;
ALTER TABLE fiscal_parameter     DROP CONSTRAINT IF EXISTS fiscal_parameter_no_overlap;

DROP POLICY IF EXISTS fiscal_logic_version_read    ON fiscal_logic_version;
DROP POLICY IF EXISTS fiscal_parameter_read        ON fiscal_parameter;
DROP POLICY IF EXISTS fiscal_parameter_source_read ON fiscal_parameter_source;

ALTER TABLE fiscal_logic_version    NO FORCE ROW LEVEL SECURITY;
ALTER TABLE fiscal_logic_version    DISABLE  ROW LEVEL SECURITY;
ALTER TABLE fiscal_parameter        NO FORCE ROW LEVEL SECURITY;
ALTER TABLE fiscal_parameter        DISABLE  ROW LEVEL SECURITY;
ALTER TABLE fiscal_parameter_source NO FORCE ROW LEVEL SECURITY;
ALTER TABLE fiscal_parameter_source DISABLE  ROW LEVEL SECURITY;
