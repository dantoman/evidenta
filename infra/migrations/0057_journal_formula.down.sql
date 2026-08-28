-- Inversul lui 0057. Ordinea: triggere → politica → functii (ADR-043 §5), fara
-- CASCADE. Functiile pleaca sub rolul care le detine: `evidenta_owner` e
-- NOINHERIT, iar un DROP emis de el moare cu „must be owner of function".

DROP TRIGGER IF EXISTS journal_entry_formulas_at_commit    ON journal_entry;
DROP TRIGGER IF EXISTS journal_formula_stays_immutable     ON journal_formula;
DROP TRIGGER IF EXISTS journal_entry_stamps_stay_immutable ON journal_entry;

DROP POLICY IF EXISTS journal_formula_access ON journal_formula;

REVOKE ALL ON journal_formula FROM evidenta_app;
REVOKE ALL ON journal_formula FROM evidenta_rls;

SET LOCAL ROLE evidenta_rls;
DROP FUNCTION IF EXISTS rls.journal_entry_formulas_balanced();
DROP FUNCTION IF EXISTS rls.journal_formula_immutable();
DROP FUNCTION IF EXISTS rls.journal_entry_stamps_immutable();
RESET ROLE;
