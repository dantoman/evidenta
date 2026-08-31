-- Inversa lui 0074_settlements.up.sql (ADR-012).

REVOKE ALL ON settlement FROM evidenta_app;

DROP POLICY IF EXISTS settlement_access ON settlement;

ALTER TABLE settlement NO FORCE ROW LEVEL SECURITY;
ALTER TABLE settlement DISABLE ROW LEVEL SECURITY;
