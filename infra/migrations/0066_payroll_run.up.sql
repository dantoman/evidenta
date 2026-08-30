-- =============================================================================
-- Rularea lunara de salarii si liniile ei
--
-- Autoritate:  docs/decisions/065-schema-salarizarii.md §2, §2.2, §6, §8
--              docs/decisions/061-cumulativele-de-salarii.md
--              docs/decisions/044-data-de-rezolutie.md §6
--              CLAUDE.md R17, R18, C30, C34; spec-a §2.6
--
-- Doua tabele company_scoped. Ce e specific fata de restul modulului:
--
--   1. LINIA E INGHETATA la `approved`, prin trigger — pe tiparul lui
--      `rls.opening_balance_line_frozen`. Ce se aproba e ce s-a calculat; o linie
--      schimbata dupa aprobare schimba o declaratie deja construita din ea.
--
--   2. SUMA POATE FI NULA, si e proiectare, nu gol. O cota a carei margine n-a
--      fost stabilita NU se rezolva la nicio data (OD-92) — deci rezultatul onest
--      e o linie care exista, n-are suma si spune de ce. Nu zero: „o cota care
--      lipseste nu e o cota de zero\". CHECK-ul din migrarea Django face perechea
--      exclusiva; aprobarea refuza cat timp exista linii nerezolvate.
--
--   3. TOATE SUMELE SUNT POZITIVE (ADR-061). Semnul il poarta natura liniei, nu
--      numarul.
-- =============================================================================

ALTER TABLE payroll_line ALTER COLUMN component_key  TYPE text COLLATE "C";
ALTER TABLE payroll_line ALTER COLUMN parameter_key  TYPE text COLLATE "C";

-- --- Linia urmeaza starea rularii --------------------------------------------
--
-- SECURITY DEFINER fiindca sub FORCE RLS pana si proprietarul e supus
-- politicilor, iar o cautare filtrata ar raspunde „nu exista" si ar lasa
-- scrierea sa treaca.

SET LOCAL ROLE evidenta_rls;

CREATE OR REPLACE FUNCTION rls.payroll_line_frozen() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    target uuid := COALESCE(NEW.run_id, OLD.run_id);
    state  text;
BEGIN
    SELECT r.status INTO state FROM payroll_run r WHERE r.id = target;

    -- Rularea insasi e stearsa in aceeasi tranzactie: liniile pleaca inaintea ei
    -- (ON DELETE CASCADE) si n-au ce urma.
    IF NOT FOUND THEN
        RETURN COALESCE(NEW, OLD);
    END IF;

    IF state <> 'draft' THEN
        RAISE EXCEPTION
            'payroll run % is %; its lines are frozen so that what is declared is '
            'what was calculated (% refused)', target, state, TG_OP
            USING ERRCODE = 'restrict_violation';
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$;

REVOKE ALL     ON FUNCTION rls.payroll_line_frozen() FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION rls.payroll_line_frozen() TO evidenta_owner;

RESET ROLE;

CREATE TRIGGER payroll_line_frozen
    BEFORE INSERT OR UPDATE OR DELETE ON payroll_line
    FOR EACH ROW EXECUTE FUNCTION rls.payroll_line_frozen();

-- --- Politici: sablonul company_scoped ---------------------------------------

ALTER TABLE payroll_run ENABLE ROW LEVEL SECURITY;
ALTER TABLE payroll_run FORCE  ROW LEVEL SECURITY;
CREATE POLICY payroll_run_access ON payroll_run
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

ALTER TABLE payroll_line ENABLE ROW LEVEL SECURITY;
ALTER TABLE payroll_line FORCE  ROW LEVEL SECURITY;
CREATE POLICY payroll_line_access ON payroll_line
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
-- REVOKE explicit pe rulare: DELETE ramane retras. O luna calculata nu se sterge,
-- se recalculeaza cat e `draft` — iar dupa aprobare nici atat. Privilegiile
-- implicite din 0001_roles.sql l-ar fi acordat tacut (OD-47, OD-105): a doua oara
-- in acelasi modul cand un GRANT care enumera mai putin nu retrage nimic.
--
-- Liniile PASTREAZA DELETE: recalcularea unei rulari `draft` sterge si rescrie
-- liniile, iar triggerul de mai sus e cel care opreste stergerea dupa aprobare.
-- Doua mecanisme cu roluri diferite, si asta e deliberat: privilegiul spune „nu
-- se sterge niciodata", triggerul spune „nu se mai schimba de acum".

GRANT  SELECT, INSERT, UPDATE, DELETE ON payroll_line TO evidenta_app;
GRANT  SELECT, INSERT, UPDATE         ON payroll_run  TO evidenta_app;
REVOKE DELETE                         ON payroll_run  FROM evidenta_app;

GRANT SELECT ON payroll_run TO evidenta_rls;
