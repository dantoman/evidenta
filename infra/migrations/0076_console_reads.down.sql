-- Inversa lui 0076_console_reads.up.sql (ADR-012).
--
-- Functiile sunt ale lui evidenta_rls, deci se sterg sub rolul lui (lectia OD-64 / ADR-043:
-- `DROP` ca owner-ul de tabele moare cu „must be owner of function"). Granturile pe tabele care
-- existau dinainte (tenant, company, membership, "user") NU se retrag: le folosesc predicatele.

SET LOCAL ROLE evidenta_rls;

DROP FUNCTION IF EXISTS rls.console_flag_overrides();
DROP FUNCTION IF EXISTS rls.console_release_rings();
DROP FUNCTION IF EXISTS rls.console_capabilities();
DROP FUNCTION IF EXISTS rls.console_privileged_log(text, text, integer);
DROP FUNCTION IF EXISTS rls.console_user_by_email(text);
DROP FUNCTION IF EXISTS rls.console_staff();
DROP FUNCTION IF EXISTS rls.console_tenants();
DROP FUNCTION IF EXISTS rls.console_caller_role();

RESET ROLE;

REVOKE ALL ON platform_staff                                FROM evidenta_rls;
REVOKE ALL ON privileged_access_log                         FROM evidenta_rls;
REVOKE ALL ON capability_activation                         FROM evidenta_rls;
REVOKE ALL ON tenant_release_ring, feature_flag_override    FROM evidenta_rls;
