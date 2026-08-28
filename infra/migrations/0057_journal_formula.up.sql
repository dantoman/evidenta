-- =============================================================================
-- Formula ca unitate de postare, si cele trei versiuni pe antet — ADR-048
--
-- Autoritate:  docs/decisions/048-formula-si-sloturile-tipizate.md
--              docs/decisions/036-forma-postarii.md §5, docs/decisions/029
--              CLAUDE.md R10, R11, R21, R22, C34
--
-- Trei lucruri pe care Django nu le poate spune:
--
--   1. IMUTABILITATEA (R10) formulelor unei inregistrari postate, si a celor
--      trei stampile de pe antet. `0036` a fixat lista coloanelor pe care
--      triggerul antetului le refuza; fisierul acela e append-only (C31), deci
--      coloanele noi primesc triggerul lor.
--   2. LEGATURA formule ↔ linii, la COMMIT: daca o inregistrare are formule,
--      suma lor e egala cu totalul debitor al liniilor. Doua tabele scrise de un
--      singur writer intr-o singura tranzactie nu diverg; asta e pentru caile
--      care nu trec prin writer — importul, o migrare de date.
--   3. Politica, granturile si colatiile.
-- =============================================================================

-- --- colatii (C34): chei, nu denumiri -----------------------------------------

ALTER TABLE journal_entry ALTER COLUMN rule_ref TYPE text COLLATE "C";

ALTER TABLE journal_formula ALTER COLUMN vat_rate_key     TYPE text COLLATE "C";
ALTER TABLE journal_formula ALTER COLUMN slot_1_dimension TYPE text COLLATE "C";
ALTER TABLE journal_formula ALTER COLUMN slot_2_dimension TYPE text COLLATE "C";
ALTER TABLE journal_formula ALTER COLUMN slot_3_dimension TYPE text COLLATE "C";
ALTER TABLE journal_formula ALTER COLUMN slot_4_dimension TYPE text COLLATE "C";

-- --- stampilele antetului nu se rescriu dupa postare (R10) -------------------

SET LOCAL ROLE evidenta_rls;

CREATE OR REPLACE FUNCTION rls.journal_entry_stamps_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status = 'posted' AND (
           NEW.rule_ref              IS DISTINCT FROM OLD.rule_ref
        OR NEW.chart_template_id     IS DISTINCT FROM OLD.chart_template_id
        OR NEW.fiscal_effective_date IS DISTINCT FROM OLD.fiscal_effective_date
    ) THEN
        RAISE EXCEPTION 'journal_entry % is posted; what it stood on is immutable (R10, ADR-048)',
            OLD.id
            USING ERRCODE = 'raise_exception';
    END IF;
    RETURN NEW;
END;
$$;

REVOKE ALL ON FUNCTION rls.journal_entry_stamps_immutable() FROM PUBLIC;
-- ADR-043 §4.1: CREATE TRIGGER verifica EXECUTE la creare, ca `evidenta_owner`.
GRANT EXECUTE ON FUNCTION rls.journal_entry_stamps_immutable() TO evidenta_owner;

RESET ROLE;

CREATE TRIGGER journal_entry_stamps_stay_immutable
    BEFORE UPDATE ON journal_entry
    FOR EACH ROW EXECUTE FUNCTION rls.journal_entry_stamps_immutable();

-- --- formulele unei inregistrari postate nu se modifica si nu se sterg ------

SET LOCAL ROLE evidenta_rls;

CREATE OR REPLACE FUNCTION rls.journal_formula_immutable() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    entry_status text;
BEGIN
    SELECT status INTO entry_status FROM journal_entry
     WHERE id = COALESCE(NEW.journal_entry_id, OLD.journal_entry_id);
    IF entry_status = 'posted' THEN
        RAISE EXCEPTION 'journal_formula belongs to a posted entry and is immutable (R10)'
            USING ERRCODE = 'raise_exception';
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$;

REVOKE ALL ON FUNCTION rls.journal_formula_immutable() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION rls.journal_formula_immutable() TO evidenta_owner;

RESET ROLE;

CREATE TRIGGER journal_formula_stays_immutable
    BEFORE UPDATE OR DELETE ON journal_formula
    FOR EACH ROW EXECUTE FUNCTION rls.journal_formula_immutable();

-- --- formulele si liniile spun aceeasi suma, verificat la COMMIT -------------
--
-- Acelasi tipar ca `journal_entry_balanced` din 0036, cu aceeasi lectie:
-- RECITESTE randul, nu te uita la NEW — un constraint trigger amanat ruleaza
-- pentru fiecare eveniment din coada, cu NEW inghetat la momentul lui.
--
-- O inregistrare fara formule trece: nota manuala si soldurile initiale scriu
-- doar linii, iar absenta formulelor e o forma legitima (ADR-048 §4). Una CU
-- formule a caror suma nu e totalul debitor e o inregistrare pe care fisa
-- contului si balanta ar citi-o diferit — exact ce constrangerea refuza.

SET LOCAL ROLE evidenta_rls;

CREATE OR REPLACE FUNCTION rls.journal_entry_formulas_balanced() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    row_status   text;
    row_debit    numeric(20,4);
    formula_sum  numeric(20,4);
BEGIN
    SELECT status, total_debit INTO row_status, row_debit
      FROM journal_entry WHERE id = NEW.id;

    IF NOT FOUND OR row_status <> 'posted' THEN
        RETURN NULL;
    END IF;

    SELECT sum(amount) INTO formula_sum FROM journal_formula
     WHERE journal_entry_id = NEW.id;

    IF formula_sum IS NOT NULL AND formula_sum <> row_debit THEN
        RAISE EXCEPTION 'journal_entry % formulas sum to % but its lines debit % (ADR-048)',
            NEW.id, formula_sum, row_debit
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NULL;
END;
$$;

REVOKE ALL ON FUNCTION rls.journal_entry_formulas_balanced() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION rls.journal_entry_formulas_balanced() TO evidenta_owner;

RESET ROLE;

CREATE CONSTRAINT TRIGGER journal_entry_formulas_at_commit
    AFTER INSERT OR UPDATE ON journal_entry
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION rls.journal_entry_formulas_balanced();

-- --- politica: sablonul complet din ADR-004, ca la `journal_line` ------------

ALTER TABLE journal_formula ENABLE ROW LEVEL SECURITY;
ALTER TABLE journal_formula FORCE  ROW LEVEL SECURITY;
CREATE POLICY journal_formula_access ON journal_formula
    FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id)
                AND rls.has_company_access(company_id)
                AND (app.current_company_id() IS NULL
                     OR company_id = app.current_company_id()))
    WITH CHECK (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id)
                AND rls.has_company_access(company_id)
                AND (app.current_company_id() IS NULL
                     OR company_id = app.current_company_id()));

-- --- granturi ----------------------------------------------------------------
--
-- Fara UPDATE si fara DELETE: o formula nu are nicio tranzitie de stare — spre
-- deosebire de antet, unde `draft -> posted` e un UPDATE. REVOKE explicit,
-- fiindca un GRANT restrans nu retrage nimic (masurat la 0043).
GRANT SELECT, INSERT ON journal_formula TO evidenta_app;
REVOKE UPDATE, DELETE ON journal_formula FROM evidenta_app;

-- Functia de la COMMIT citeste formulele ca `evidenta_rls`, care nu are niciun
-- privilegiu de tabela implicit (masurat la 0036).
GRANT SELECT ON journal_formula TO evidenta_rls;
