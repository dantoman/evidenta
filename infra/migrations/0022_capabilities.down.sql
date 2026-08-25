-- Inversa lui 0022_capabilities.up.sql (ADR-012).

REVOKE ALL ON capability_activation FROM evidenta_app;
DROP POLICY IF EXISTS capability_activation_access ON capability_activation;
ALTER TABLE capability_activation NO FORCE ROW LEVEL SECURITY;
ALTER TABLE capability_activation DISABLE ROW LEVEL SECURITY;
ALTER TABLE capability_activation DROP CONSTRAINT IF EXISTS capability_activation_no_overlap;
