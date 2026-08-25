-- Inversa lui 0015_module_scope_sync.up.sql (ADR-012).

REVOKE ALL ON engagement_module_scope FROM evidenta_rls;

DROP TRIGGER IF EXISTS engagement_status_scope_sync ON engagement;
DROP TRIGGER IF EXISTS engagement_module_scope_sync ON engagement_module_scope;

DROP FUNCTION IF EXISTS rls.sync_module_scope_liveness();
DROP FUNCTION IF EXISTS rls.sync_module_scope_from_engagement();
