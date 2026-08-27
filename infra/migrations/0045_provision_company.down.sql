-- Inversul lui 0045. Sterge functia si granturile pe care ea le-a cerut.
--
-- Reversibil, cu invers testat. `DROP FUNCTION` ruleaza sub rolul care detine
-- functia — `evidenta_rls` —, nu sub owner: `evidenta_owner` e NOINHERIT, deci un
-- DROP direct ar muri cu „must be owner of function" (OD-64, ADR-043).
--
-- Consecinta operationala: dupa derulare, nicio companie noua nu se mai poate
-- crea. Companiile existente raman neatinse.

SET LOCAL ROLE evidenta_rls;
DROP FUNCTION IF EXISTS rls.provision_company(uuid, text, text, text, date, smallint);
RESET ROLE;

REVOKE INSERT ON company FROM evidenta_rls;
REVOKE SELECT ON membership FROM evidenta_rls;
