-- Ordinea: trigger, apoi functie. Functia e a lui `evidenta_rls`, deci DROP-ul se
-- emite sub el (OD-64, ADR-043).
DROP TRIGGER IF EXISTS unit_of_measure_precision_frozen ON unit_of_measure;

SET LOCAL ROLE evidenta_rls;
DROP FUNCTION IF EXISTS rls.refuse_unit_precision_change();
RESET ROLE;
