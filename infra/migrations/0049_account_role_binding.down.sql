-- Inversul lui 0049. Fara functii si fara triggere de sters: politica si
-- granturile sunt tot ce a adaugat.

DROP POLICY IF EXISTS account_role_binding_access ON account_role_binding;
REVOKE ALL ON account_role_binding FROM evidenta_app;
