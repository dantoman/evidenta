-- Inversul lui 0046, cu consecinta scrisa pe fata: **derularea inapoi redeschide
-- functia catre PUBLIC**, fiindca aceea era starea lasata de `0045`. Un invers
-- care ar lasa-o retrasa ar fi mai sigur si ar minti despre ce a facut.
--
-- Reversibil, cu invers testat. Emis tot sub `evidenta_rls`: un GRANT de la
-- altcineva decat proprietarul ar fi acelasi no-op ca REVOKE-ul pe care il repara
-- `0046`.

SET LOCAL ROLE evidenta_rls;

GRANT EXECUTE ON FUNCTION rls.provision_company(uuid, text, text, text, date, smallint) TO PUBLIC;
REVOKE EXECUTE ON FUNCTION rls.provision_company(uuid, text, text, text, date, smallint)
    FROM evidenta_app;

RESET ROLE;
