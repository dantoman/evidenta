-- Inversa lui 0019_roles.up.sql (ADR-012: reverse_sql nu e opțional).

REVOKE ALL ON role, role_permission FROM evidenta_app;
REVOKE ALL ON permission FROM evidenta_app;

DROP POLICY IF EXISTS role_permission_access ON role_permission;
DROP POLICY IF EXISTS role_access ON role;
DROP POLICY IF EXISTS permission_platform_write ON permission;
DROP POLICY IF EXISTS permission_read ON permission;

ALTER TABLE role_permission NO FORCE ROW LEVEL SECURITY;
ALTER TABLE role_permission DISABLE ROW LEVEL SECURITY;
ALTER TABLE role NO FORCE ROW LEVEL SECURITY;
ALTER TABLE role DISABLE ROW LEVEL SECURITY;
ALTER TABLE permission NO FORCE ROW LEVEL SECURITY;
ALTER TABLE permission DISABLE ROW LEVEL SECURITY;

DROP TRIGGER IF EXISTS role_permission_protect_system ON role_permission;
DROP TRIGGER IF EXISTS role_protect_system ON role;
DROP FUNCTION IF EXISTS app.protect_system_role();

ALTER TABLE role_permission DROP CONSTRAINT IF EXISTS role_permission_permission_same_scope;
ALTER TABLE role_permission DROP CONSTRAINT IF EXISTS role_permission_role_same_tenant_and_level;
ALTER TABLE company_access DROP CONSTRAINT IF EXISTS company_access_role_same_tenant;
ALTER TABLE membership DROP CONSTRAINT IF EXISTS membership_role_same_tenant;

ALTER TABLE permission DROP CONSTRAINT IF EXISTS permission_key_scope_unique;
ALTER TABLE role DROP CONSTRAINT IF EXISTS role_tenant_id_level_unique;
ALTER TABLE role DROP CONSTRAINT IF EXISTS role_tenant_id_unique;

ALTER TABLE role       ALTER COLUMN key TYPE text;
ALTER TABLE permission ALTER COLUMN key TYPE text;
