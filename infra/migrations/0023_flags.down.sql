-- Inversa lui 0023_flags.up.sql (ADR-012).

REVOKE ALL ON feature_flag FROM evidenta_rls;
REVOKE ALL ON tenant_release_ring, feature_flag_override FROM evidenta_app;
REVOKE ALL ON feature_flag, release_ring FROM evidenta_app;

DROP TRIGGER IF EXISTS feature_flag_override_no_compliance ON feature_flag_override;
DROP FUNCTION IF EXISTS rls.refuse_compliance_flag_override();

DROP POLICY IF EXISTS feature_flag_override_access ON feature_flag_override;
DROP POLICY IF EXISTS tenant_release_ring_access ON tenant_release_ring;
DROP POLICY IF EXISTS release_ring_read ON release_ring;
DROP POLICY IF EXISTS feature_flag_read ON feature_flag;

ALTER TABLE feature_flag_override NO FORCE ROW LEVEL SECURITY;
ALTER TABLE feature_flag_override DISABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_release_ring   NO FORCE ROW LEVEL SECURITY;
ALTER TABLE tenant_release_ring   DISABLE ROW LEVEL SECURITY;
ALTER TABLE release_ring          NO FORCE ROW LEVEL SECURITY;
ALTER TABLE release_ring          DISABLE ROW LEVEL SECURITY;
ALTER TABLE feature_flag          NO FORCE ROW LEVEL SECURITY;
ALTER TABLE feature_flag          DISABLE ROW LEVEL SECURITY;

ALTER TABLE tenant_release_ring ALTER COLUMN ring_code TYPE text;
ALTER TABLE release_ring ALTER COLUMN code TYPE text;
