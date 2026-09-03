-- =============================================================================
-- Plata salariilor: documentul de plata, liniile lui, IBAN-ul angajatului
--
-- Autoritate:  docs/decisions/065-schema-salarizarii.md §7, §8
--              docs/decisions/073-forma-postarii-documentelor-comerciale.md §5, §8
--              CLAUDE.md R9, R19, C30, C34; spec-a §2.6
--
-- Doua tabele company_scoped, pe tiparul lui 0066_payroll_run, si o coloana noua
-- pe `employee`. Ce e specific:
--
--   1. IBAN-UL E COD (C34, ADR-015): COLLATE "C" explicit. O lista de plata
--      ordonata dupa IBAN iese in ordinea bancii, nu in ordine lingvistica.
--
--   2. LINIA E INGHETATA la `posted`, prin trigger -- pe tiparul lui
--      `rls.payroll_line_frozen`. Ce s-a contabilizat e ce s-a platit; o linie
--      schimbata dupa postare ar face documentul sa spuna altceva decat registrul.
--
--   3. SUMA E STRICT POZITIVA (CHECK in migrarea Django). O persoana scoasa din
--      plata isi pierde linia cat documentul e ciorna; un zero ar fi „s-a platit
--      nimic", care nu e o plata.
-- =============================================================================

ALTER TABLE employee ALTER COLUMN bank_iban TYPE text COLLATE "C";

-- --- Linia urmeaza starea documentului ---------------------------------------
--
-- SECURITY DEFINER fiindca sub FORCE RLS pana si proprietarul e supus
-- politicilor, iar o cautare filtrata ar raspunde „nu exista" si ar lasa
-- scrierea sa treaca.

SET LOCAL ROLE evidenta_rls;

CREATE OR REPLACE FUNCTION rls.salary_payment_line_frozen() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    target uuid := COALESCE(NEW.payment_id, OLD.payment_id);
    state  text;
BEGIN
    SELECT p.status INTO state FROM salary_payment p WHERE p.id = target;

    -- Documentul insusi e sters in aceeasi tranzactie: liniile pleaca inaintea
    -- lui (ON DELETE CASCADE) si n-au ce urma.
    IF NOT FOUND THEN
        RETURN COALESCE(NEW, OLD);
    END IF;

    IF state <> 'draft' THEN
        RAISE EXCEPTION
            'salary payment % is %; its lines are frozen so that what the register '
            'shows is what was paid (% refused)', target, state, TG_OP
            USING ERRCODE = 'restrict_violation';
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$;

REVOKE ALL     ON FUNCTION rls.salary_payment_line_frozen() FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION rls.salary_payment_line_frozen() TO evidenta_owner;

RESET ROLE;

CREATE TRIGGER salary_payment_line_frozen
    BEFORE INSERT OR UPDATE OR DELETE ON salary_payment_line
    FOR EACH ROW EXECUTE FUNCTION rls.salary_payment_line_frozen();

-- --- Politici: sablonul company_scoped ---------------------------------------

ALTER TABLE salary_payment ENABLE ROW LEVEL SECURITY;
ALTER TABLE salary_payment FORCE  ROW LEVEL SECURITY;
CREATE POLICY salary_payment_access ON salary_payment
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

ALTER TABLE salary_payment_line ENABLE ROW LEVEL SECURITY;
ALTER TABLE salary_payment_line FORCE  ROW LEVEL SECURITY;
CREATE POLICY salary_payment_line_access ON salary_payment_line
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

-- --- Privilegii --------------------------------------------------------------
--
-- REVOKE explicit pe document: DELETE ramane retras (OD-47, OD-105). O plata
-- contabilizata nu se sterge; una ramasa ciorna se vede ca atare. Liniile
-- PASTREAZA DELETE: o persoana se scoate din plata cat e ciorna, iar triggerul
-- de mai sus e cel care opreste stergerea dupa postare.

GRANT  SELECT, INSERT, UPDATE, DELETE ON salary_payment_line TO evidenta_app;
GRANT  SELECT, INSERT, UPDATE         ON salary_payment      TO evidenta_app;
REVOKE DELETE                         ON salary_payment      FROM evidenta_app;

GRANT SELECT ON salary_payment TO evidenta_rls;
