-- Ordinea: trigger, apoi functie, apoi politici. Functia e a lui `evidenta_rls`,
-- deci DROP-ul se emite sub el (OD-64, ADR-043).
DROP TRIGGER IF EXISTS privileged_access_log_append_only ON privileged_access_log;

SET LOCAL ROLE evidenta_rls;
DROP FUNCTION IF EXISTS rls.refuse_privileged_log_rewrite();
RESET ROLE;

REVOKE ALL ON privileged_access_log FROM evidenta_refdata;
DROP POLICY IF EXISTS privileged_access_log_refdata_insert ON privileged_access_log;
DROP POLICY IF EXISTS privileged_access_log_refdata_read ON privileged_access_log;
ALTER TABLE privileged_access_log NO FORCE ROW LEVEL SECURITY;
ALTER TABLE privileged_access_log DISABLE ROW LEVEL SECURITY;
-- Tabela o sterge Django, in aceeasi migrare inversa.
