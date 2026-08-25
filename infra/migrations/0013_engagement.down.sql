-- Inversa lui 0013_engagement.up.sql (ADR-012: reverse_sql nu e opțional).

REVOKE ALL ON engagement, firm FROM evidenta_rls;
REVOKE ALL ON firm, engagement, engagement_company_scope, engagement_module_scope
    FROM evidenta_app;

DROP POLICY IF EXISTS engagement_module_scope_parties ON engagement_module_scope;
DROP POLICY IF EXISTS engagement_company_scope_parties ON engagement_company_scope;
DROP POLICY IF EXISTS engagement_parties ON engagement;
DROP POLICY IF EXISTS firm_parties ON firm;

ALTER TABLE engagement_module_scope  NO FORCE ROW LEVEL SECURITY;
ALTER TABLE engagement_module_scope  DISABLE ROW LEVEL SECURITY;
ALTER TABLE engagement_company_scope NO FORCE ROW LEVEL SECURITY;
ALTER TABLE engagement_company_scope DISABLE ROW LEVEL SECURITY;
ALTER TABLE engagement NO FORCE ROW LEVEL SECURITY;
ALTER TABLE engagement DISABLE ROW LEVEL SECURITY;
ALTER TABLE firm NO FORCE ROW LEVEL SECURITY;
ALTER TABLE firm DISABLE ROW LEVEL SECURITY;

ALTER TABLE firm ALTER COLUMN idno TYPE text;
