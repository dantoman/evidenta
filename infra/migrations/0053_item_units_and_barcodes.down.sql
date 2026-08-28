-- Inversa lui 0053_item_units_and_barcodes.up.sql (ADR-012).

REVOKE ALL ON item_unit, item_barcode FROM evidenta_app;
DROP POLICY IF EXISTS item_barcode_access ON item_barcode;
DROP POLICY IF EXISTS item_unit_access ON item_unit;
ALTER TABLE item_barcode NO FORCE ROW LEVEL SECURITY;
ALTER TABLE item_barcode DISABLE ROW LEVEL SECURITY;
ALTER TABLE item_unit    NO FORCE ROW LEVEL SECURITY;
ALTER TABLE item_unit    DISABLE ROW LEVEL SECURITY;
ALTER TABLE item_barcode ALTER COLUMN barcode     TYPE text;
ALTER TABLE item         ALTER COLUMN tariff_code TYPE text;
