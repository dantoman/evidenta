-- Ordinea: trigger, apoi functie. Invers ar cere CASCADE, care e interzis —
-- CASCADE nu se opreste la ce a creat migrarea asta si poate sterge tacit un
-- obiect atasat intre timp de altcineva de aceeasi functie.
DROP TRIGGER IF EXISTS fiscal_confidence_event_append_only ON fiscal_parameter_confidence_event;

-- Functia e detinuta de `evidenta_rls`, iar `evidenta_owner` e NOINHERIT: un DROP
-- emis ca owner cade cu „must be owner of function". Aceeasi cauza ca la cele opt
-- inverse corectate prin `OD-64` — si prinsa aici de gardianul scris pentru ele,
-- inainte ca fisierul sa fie referit de o migrare aplicata.
SET LOCAL ROLE evidenta_rls;
DROP FUNCTION IF EXISTS rls.refuse_confidence_event_rewrite();
RESET ROLE;
DROP POLICY IF EXISTS fiscal_parameter_confidence_event_read ON fiscal_parameter_confidence_event;
ALTER TABLE fiscal_parameter_confidence_event NO FORCE ROW LEVEL SECURITY;
ALTER TABLE fiscal_parameter_confidence_event DISABLE ROW LEVEL SECURITY;
