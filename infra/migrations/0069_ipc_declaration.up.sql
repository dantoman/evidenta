-- =============================================================================
-- Darea de seama unificata IPC — antet versionat, totaluri, sectiune nominala
--
-- Autoritate:  Legea nr. 489/1999 art. 5 alin. (1) lit. a)
--              Codul fiscal art. 92 alin. (1)-(2), art. 188
--              Ordinul MF nr. 94/2020 (Forma IPC21) — formularul NEOBTINUT
--              docs/decisions/069-persoana-asigurata-nu-e-angajatul.md
--              spec-a §2.6; CLAUDE.md R1, R2, C34
--
-- Trei tabele company_scoped. Ce e specific:
--
--   1. VERSIONARE, nu suprascriere (art. 188). Corectarea se face prin dare de
--      seama CORECTATA. Randurile depuse nu se rescriu niciodata — de aceea
--      `evidenta_app` nu are DELETE pe antet, iar continutul unei declaratii
--      DEPUSE e inghetat prin trigger.
--
--   2. RANDURILE SUNT STOCATE, nu recalculate. Regenerarea unei perioade trecute
--      trebuie sa dea ce s-a depus atunci, nu ce ar da regulile de azi.
--
--   3. Coduri, deci `COLLATE "C"` (C34): codul fiscal, CUATM, CAEM, codul sursei
--      de venit, codul de tarif, IDNP, CPAS, codul categoriei asigurate.
-- =============================================================================

ALTER TABLE ipc_declaration  ALTER COLUMN fiscal_code            TYPE text COLLATE "C";
ALTER TABLE ipc_declaration  ALTER COLUMN cuatm_code             TYPE text COLLATE "C";
ALTER TABLE ipc_declaration  ALTER COLUMN caem_code              TYPE text COLLATE "C";
ALTER TABLE ipc_total_line   ALTER COLUMN income_source_code     TYPE text COLLATE "C";
ALTER TABLE ipc_total_line   ALTER COLUMN cas_tariff_code        TYPE text COLLATE "C";
ALTER TABLE ipc_nominal_line ALTER COLUMN idnp                   TYPE text COLLATE "C";
ALTER TABLE ipc_nominal_line ALTER COLUMN personal_insurance_code TYPE text COLLATE "C";
ALTER TABLE ipc_nominal_line ALTER COLUMN insured_category_code  TYPE text COLLATE "C";

-- --- Continutul urmeaza starea declaratiei ----------------------------------
--
-- O declaratie depusa e un artefact transmis: randurile ei nu se mai schimba, cu
-- niciun pret. Corectarea e o VERSIUNE NOUA (art. 188), nu o editare — iar
-- distinctia asta e chiar motivul pentru care versionarea s-a facut in prima zi.
--
-- SECURITY DEFINER fiindca sub FORCE RLS pana si proprietarul e supus
-- politicilor, iar o cautare filtrata ar raspunde „nu exista" si ar lasa
-- scrierea sa treaca.

SET LOCAL ROLE evidenta_rls;

CREATE OR REPLACE FUNCTION rls.ipc_content_follows_its_declaration() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    target uuid := COALESCE(NEW.declaration_id, OLD.declaration_id);
    state  text;
BEGIN
    SELECT d.status INTO state FROM ipc_declaration d WHERE d.id = target;

    -- Declaratia insasi e stearsa in aceeasi tranzactie (o ciorna abandonata):
    -- randurile pleaca inaintea ei si nu au ce urma.
    IF NOT FOUND THEN
        RETURN COALESCE(NEW, OLD);
    END IF;

    IF state <> 'draft' THEN
        RAISE EXCEPTION
            'IPC declaration % is %; its rows are frozen — a correction is a new '
            'version (art. 188), never an edit (% refused on %)',
            target, state, TG_OP, TG_TABLE_NAME
            USING ERRCODE = 'restrict_violation';
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$;

REVOKE ALL     ON FUNCTION rls.ipc_content_follows_its_declaration() FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION rls.ipc_content_follows_its_declaration() TO evidenta_owner;

RESET ROLE;

CREATE TRIGGER ipc_total_line_follows_its_declaration
    BEFORE INSERT OR UPDATE OR DELETE ON ipc_total_line
    FOR EACH ROW EXECUTE FUNCTION rls.ipc_content_follows_its_declaration();

CREATE TRIGGER ipc_nominal_line_follows_its_declaration
    BEFORE INSERT OR UPDATE OR DELETE ON ipc_nominal_line
    FOR EACH ROW EXECUTE FUNCTION rls.ipc_content_follows_its_declaration();

-- --- Politici: sablonul company_scoped ---------------------------------------

ALTER TABLE ipc_declaration ENABLE ROW LEVEL SECURITY;
ALTER TABLE ipc_declaration FORCE  ROW LEVEL SECURITY;
CREATE POLICY ipc_declaration_access ON ipc_declaration
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

ALTER TABLE ipc_total_line ENABLE ROW LEVEL SECURITY;
ALTER TABLE ipc_total_line FORCE  ROW LEVEL SECURITY;
CREATE POLICY ipc_total_line_access ON ipc_total_line
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

ALTER TABLE ipc_nominal_line ENABLE ROW LEVEL SECURITY;
ALTER TABLE ipc_nominal_line FORCE  ROW LEVEL SECURITY;
CREATE POLICY ipc_nominal_line_access ON ipc_nominal_line
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
-- REVOKE explicit, nu enumerare mai scurta: privilegiile implicite din
-- 0001_roles.sql acorda INSERT/UPDATE/DELETE pe orice tabela creata de owner, iar
-- un GRANT care omite ceva NU retrage nimic (OD-47, OD-105 — a treia oara).
--
-- Antetul nu se sterge NICIODATA: o dare de seama depusa e artefact, iar o ciorna
-- abandonata ramane ca sa se vada ce s-a incercat. Randurile pastreaza DELETE,
-- fiindca o ciorna se regenereaza — triggerul de mai sus e cel care le opreste
-- dupa depunere.

GRANT  SELECT, INSERT, UPDATE, DELETE ON ipc_total_line   TO evidenta_app;
GRANT  SELECT, INSERT, UPDATE, DELETE ON ipc_nominal_line TO evidenta_app;
GRANT  SELECT, INSERT, UPDATE         ON ipc_declaration  TO evidenta_app;
REVOKE DELETE                         ON ipc_declaration  FROM evidenta_app;

GRANT SELECT ON ipc_declaration TO evidenta_rls;
