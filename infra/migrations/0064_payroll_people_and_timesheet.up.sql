-- =============================================================================
-- Salarizare, regimul general: persoana, contractul, actul aditional, pontajul
--
-- Autoritate:  docs/decisions/065-schema-salarizarii.md §4, §5
--              docs/decisions/067-contractul-e-cap-de-serie.md
--              docs/decisions/068-anexa-citita-categoria-e-a-raportului.md §3
--              docs/decisions/071-tipurile-de-raport-ca-tabela.md
--              docs/specs/spec-a-tenancy.md §2.6; CLAUDE.md R1, R2, C34
--
-- Toate cinci sunt company_scoped: angajatorul legal e COMPANIA, nu tenantul.
-- O persoana care lucreaza la doua companii ale aceluiasi tenant are doua
-- raporturi de munca, cu doua retineri si doua declaratii — iar scutirile se
-- acorda la un singur loc de munca (HG 697/2014 pct. 9), ceea ce e o proprietate
-- a raportului, nu a persoanei.
--
-- Colatiile, C34 / ADR-015: IDNP, numerele de document, numerele de contract si
-- de ordin, codul categoriei CAS si litera clauzei sunt CODURI — `COLLATE "C"`.
-- Numele si denumirea functiei sunt DENUMIRI si raman pe colatia bazei. Fara
-- despartirea asta, orice raport ordonat dupa IDNP iese sortat lingvistic, tacit.
-- =============================================================================

-- --- Coduri: ordonare pe octeti ---------------------------------------------

ALTER TABLE employee ALTER COLUMN idnp                     TYPE text COLLATE "C";
ALTER TABLE employee ALTER COLUMN identity_document_number TYPE text COLLATE "C";
ALTER TABLE employee ALTER COLUMN identity_document_type   TYPE text COLLATE "C";
ALTER TABLE employee ALTER COLUMN social_insurance_code    TYPE text COLLATE "C";

ALTER TABLE employment_contract ALTER COLUMN contract_number          TYPE text COLLATE "C";
ALTER TABLE employment_contract ALTER COLUMN hire_order_number        TYPE text COLLATE "C";
ALTER TABLE employment_contract ALTER COLUMN termination_order_number TYPE text COLLATE "C";
ALTER TABLE employment_contract ALTER COLUMN cas_payer_point          TYPE text COLLATE "C";

ALTER TABLE employment_contract_amendment ALTER COLUMN amendment_number TYPE text COLLATE "C";
ALTER TABLE employment_contract_amendment ALTER COLUMN order_number     TYPE text COLLATE "C";
ALTER TABLE employment_contract_amendment ALTER COLUMN changed_clause   TYPE text COLLATE "C";

-- --- Politici: sablonul company_scoped (spec-a §2.6) -------------------------

ALTER TABLE employee ENABLE ROW LEVEL SECURITY;
ALTER TABLE employee FORCE  ROW LEVEL SECURITY;
CREATE POLICY employee_access ON employee
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

ALTER TABLE employment_contract ENABLE ROW LEVEL SECURITY;
ALTER TABLE employment_contract FORCE  ROW LEVEL SECURITY;
CREATE POLICY employment_contract_access ON employment_contract
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

ALTER TABLE employment_contract_amendment ENABLE ROW LEVEL SECURITY;
ALTER TABLE employment_contract_amendment FORCE  ROW LEVEL SECURITY;
CREATE POLICY employment_contract_amendment_access ON employment_contract_amendment
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

ALTER TABLE timesheet ENABLE ROW LEVEL SECURITY;
ALTER TABLE timesheet FORCE  ROW LEVEL SECURITY;
CREATE POLICY timesheet_access ON timesheet
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

ALTER TABLE timesheet_day ENABLE ROW LEVEL SECURITY;
ALTER TABLE timesheet_day FORCE  ROW LEVEL SECURITY;
CREATE POLICY timesheet_day_access ON timesheet_day
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

-- --- O luna inchisa nu se mai rescrie ----------------------------------------
--
-- Pontajul e intrarea calculului: o zi schimbata dupa ce luna a fost inchisa
-- schimba un rezultat deja raportat. Nu e `R10` — pontajul nu e ledger —, dar e
-- aceeasi forma, si e mai ieftin sa fie impus in baza decat verificat de fiecare
-- apelant. SECURITY DEFINER fiindca sub FORCE RLS pana si proprietarul e supus
-- politicilor, iar o cautare filtrata ar raspunde „nu exista" si ar lasa
-- scrierea sa treaca.

SET LOCAL ROLE evidenta_rls;

CREATE OR REPLACE FUNCTION rls.timesheet_day_follows_its_month() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    target uuid := COALESCE(NEW.timesheet_id, OLD.timesheet_id);
    sheet_status text;
BEGIN
    SELECT status INTO sheet_status FROM timesheet WHERE id = target;

    -- Luna insasi e stearsa in aceeasi tranzactie: zilele pleaca inaintea ei si
    -- nu au ce urma.
    IF NOT FOUND THEN
        RETURN COALESCE(NEW, OLD);
    END IF;

    IF sheet_status <> 'open' THEN
        RAISE EXCEPTION
            'timesheet % is % — its days are frozen (% refused)',
            target, sheet_status, TG_OP
            USING ERRCODE = 'restrict_violation';
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$;

REVOKE ALL     ON FUNCTION rls.timesheet_day_follows_its_month() FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION rls.timesheet_day_follows_its_month() TO evidenta_owner;

RESET ROLE;

CREATE TRIGGER timesheet_day_follows_its_month
    BEFORE INSERT OR UPDATE OR DELETE ON timesheet_day
    FOR EACH ROW EXECUTE FUNCTION rls.timesheet_day_follows_its_month();

-- --- Privilegii --------------------------------------------------------------

GRANT SELECT, INSERT, UPDATE, DELETE
    ON employee, employment_contract, employment_contract_amendment,
       timesheet, timesheet_day
    TO evidenta_app;

-- Triggerul de mai sus e SECURITY DEFINER, deci ruleaza ca `evidenta_rls` — iar
-- rolul acela nu are nimic pe tabelele noi. Fara linia asta, orice scriere de zi
-- moare cu „permission denied for table timesheet", DIN INTERIORUL triggerului,
-- adica cu un mesaj care arata a defect de permisiuni al aplicatiei. Masurat, nu
-- presupus: prima rulare a suitei a cazut exact asa.
GRANT SELECT ON timesheet TO evidenta_rls;
