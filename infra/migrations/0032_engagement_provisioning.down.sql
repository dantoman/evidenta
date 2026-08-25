REVOKE SELECT ON company FROM evidenta_rls;
REVOKE INSERT ON company_access FROM evidenta_rls;
DROP FUNCTION IF EXISTS rls.provision_engagement_company_access(uuid);
