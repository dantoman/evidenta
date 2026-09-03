-- Inversa lui 0079_revaluation.up.sql (ADR-012).

REVOKE ALL ON revaluation_item FROM evidenta_app;
DROP POLICY IF EXISTS revaluation_item_access ON revaluation_item;
ALTER TABLE revaluation_item NO FORCE ROW LEVEL SECURITY;
ALTER TABLE revaluation_item DISABLE ROW LEVEL SECURITY;

REVOKE ALL ON revaluation FROM evidenta_app;
DROP POLICY IF EXISTS revaluation_access ON revaluation;
ALTER TABLE revaluation NO FORCE ROW LEVEL SECURITY;
ALTER TABLE revaluation DISABLE ROW LEVEL SECURITY;
