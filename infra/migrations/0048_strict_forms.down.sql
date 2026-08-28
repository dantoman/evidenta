-- Inversul lui 0048. Ordinea e trigger → politici → functie; fara CASCADE
-- (ADR-043 §5).

DROP TRIGGER IF EXISTS strict_form_number_append_only ON strict_form_number;

DROP POLICY IF EXISTS strict_form_number_access     ON strict_form_number;
DROP POLICY IF EXISTS strict_form_allocation_access ON strict_form_allocation;

REVOKE ALL ON strict_form_number     FROM evidenta_app;
REVOKE ALL ON strict_form_allocation FROM evidenta_app;

SET LOCAL ROLE evidenta_rls;
DROP FUNCTION IF EXISTS rls.refuse_form_number_rewrite();
RESET ROLE;
