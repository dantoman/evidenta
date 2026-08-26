-- Inversul lui 0041_rls_function_privileges.up.sql (ADR-012).
--
-- Se ruleaza SUB ROLUL CARE DETINE FUNCTIILE — chiar lectia care a produs fisierul
-- de dus. `evidenta_owner` este NOINHERIT, deci apartenenta la `evidenta_rls` nu-i
-- da privilegiile fara `SET ROLE`, iar un REVOKE sau un GRANT emis de altcineva
-- decat proprietarul nu are efect.

SET LOCAL ROLE evidenta_rls;

REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA rls FROM evidenta_app;

-- Starea dinainte: PUBLIC avea EXECUTE pe tot, fiindca REVOKE-urile din migrarile
-- anterioare nu aveau efect.
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA rls TO PUBLIC;

RESET ROLE;
