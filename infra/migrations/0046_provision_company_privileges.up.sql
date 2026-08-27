-- 0046 — privilegiile lui `rls.provision_company`, emise de proprietarul functiei
--
-- Context:     docs/decisions/043-privilegiile-functiilor-rls.md
--              infra/migrations/0041_rls_function_privileges.up.sql
--              backend/tests/schema_guard/test_function_privileges.py
--
-- `0045` a emis `REVOKE ALL ... FROM PUBLIC` si `GRANT EXECUTE ... TO evidenta_app`
-- DUPA `RESET ROLE`, adica sub `evidenta_owner`, care nu detine functia — functia
-- e a lui `evidenta_rls`. Un REVOKE emis de altcineva decat proprietarul e
-- avertisment, nu eroare: migrarea a trecut si n-a retras nimic. Rezultatul,
-- masurat de gardian: `provision_company` era executabila de PUBLIC, iar
-- `evidenta_app` o putea apela nu prin grantul ei, ci prin PUBLIC.
--
-- `0045` nu se editeaza — `C31`, fisier aplicat. Corectia e fisier nou, ca la
-- ledger si din acelasi motiv.

SET LOCAL ROLE evidenta_rls;

REVOKE ALL ON FUNCTION rls.provision_company(uuid, text, text, text, date, smallint) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION rls.provision_company(uuid, text, text, text, date, smallint)
    TO evidenta_app;

RESET ROLE;
