-- Inversul lui 0043. Ordinea e trigger → politica → functie: o functie nu poate
-- pleca inaintea a ce depinde de ea. Fara CASCADE — daca un DROP cade pe o
-- dependenta, eroarea e informatie, nu obstacol de ocolit (ADR-043 §5).

DROP TRIGGER IF EXISTS entry_parameter_stamp_append_only ON entry_parameter_stamp;

DROP POLICY IF EXISTS entry_parameter_stamp_access ON entry_parameter_stamp;

REVOKE ALL ON entry_parameter_stamp FROM evidenta_app;

-- Sub rolul care detine functia: `evidenta_owner` e NOINHERIT, deci un DROP
-- emis de el moare cu „must be owner of function" — defectul pe care ADR-043 l-a
-- gasit in opt fisiere de invers care nu rulasera niciodata.
SET LOCAL ROLE evidenta_rls;
DROP FUNCTION IF EXISTS rls.refuse_parameter_stamp_rewrite();
RESET ROLE;
