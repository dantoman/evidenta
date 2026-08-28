-- Registrul formularelor cu regim special — art. 118² Cod fiscal.
--
-- Entitatea NU isi alege seria. Seria si diapazonul sunt atribuite de SFS, care
-- asigura sistemul unitar de inseriere; o entitate care imprima de sine statator
-- primeste o serie si un diapazon pentru toata perioada de activitate. De-aia
-- tabelele de mai jos descriu *alocari consumate*, nu un generator.
--
-- Numerele nu se materializeaza. Un diapazon poate fi mare, iar un rand pe numar
-- ar face tabela proportionala cu ce s-a alocat, nu cu ce s-a intamplat.
-- Alocarea poarta un cursor; un numar iese din diapazon exact o data, si acea
-- iesire e un rand. „Alocat" se deduce — in diapazon, la sau peste cursor —,
-- restul starilor se scriu, fiindcă anularea e stare evidentiata, nu absenta.

ALTER TABLE strict_form_allocation ALTER COLUMN form_type_code TYPE text COLLATE "C";
ALTER TABLE strict_form_allocation ALTER COLUMN series         TYPE text COLLATE "C";
ALTER TABLE strict_form_number     ALTER COLUMN state          TYPE text COLLATE "C";

ALTER TABLE strict_form_allocation ENABLE ROW LEVEL SECURITY;
ALTER TABLE strict_form_allocation FORCE  ROW LEVEL SECURITY;
ALTER TABLE strict_form_number     ENABLE ROW LEVEL SECURITY;
ALTER TABLE strict_form_number     FORCE  ROW LEVEL SECURITY;

CREATE POLICY strict_form_allocation_access ON strict_form_allocation
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

CREATE POLICY strict_form_number_access ON strict_form_number
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

-- Alocarea se modifica: cursorul avanseaza, iar retragerea e un UPDATE.
GRANT SELECT, INSERT, UPDATE ON strict_form_allocation TO evidenta_app;

-- Numarul, nu. Un numar iese din diapazon o singura data, si acea iesire nu se
-- rescrie: e exact intrebarea pe care o pune un control despre formularele
-- anulate. Masurat pe `entry_parameter_stamp` (ADR-047): un GRANT restrans nu
-- retrage nimic, tabela vine cu toate patru privilegiile din cele implicite.
GRANT SELECT, INSERT ON strict_form_number TO evidenta_app;
REVOKE UPDATE, DELETE ON strict_form_number FROM evidenta_app;

SET LOCAL ROLE evidenta_rls;

CREATE OR REPLACE FUNCTION rls.refuse_form_number_rewrite()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'strict_form_number is append-only (art. 118²): % refused on %',
        TG_OP, TG_TABLE_NAME
        USING ERRCODE = 'restrict_violation';
END;
$$;

REVOKE ALL ON FUNCTION rls.refuse_form_number_rewrite() FROM PUBLIC;

-- ADR-043 §4.1: `CREATE TRIGGER` verifica EXECUTE la creare si se emite ca
-- proprietar al tabelei — `evidenta_owner`, care e NOINHERIT.
GRANT EXECUTE ON FUNCTION rls.refuse_form_number_rewrite() TO evidenta_owner;

RESET ROLE;

CREATE TRIGGER strict_form_number_append_only
    BEFORE UPDATE OR DELETE ON strict_form_number
    FOR EACH ROW EXECUTE FUNCTION rls.refuse_form_number_rewrite();
