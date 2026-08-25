-- Inversa lui 0014_company_access.up.sql (ADR-012: reverse_sql nu e opțional).

REVOKE ALL ON company_access FROM evidenta_rls;
REVOKE ALL ON company_access FROM evidenta_app;
DROP FUNCTION IF EXISTS rls.revoke_engagement_company_access(uuid);

DROP POLICY IF EXISTS company_access_self ON company_access;

ALTER TABLE company_access NO FORCE ROW LEVEL SECURITY;
ALTER TABLE company_access DISABLE ROW LEVEL SECURITY;
