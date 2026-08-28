-- =============================================================================
-- Tipurile concrete de vanzare: document de vanzare, proforma, comanda client
--
-- Autoritate:  docs/decisions/004-company-context.md
--              docs/specs/spec-a-tenancy.md §2.6
--              CLAUDE.md R1, R2
--
-- Tabele de tip, una-la-unu cu antetul din `document`. Antetul tine tot ce e
-- comun — numar, date, contraparte, valuta, stare, anulare — iar acestea tin
-- doar ce e al lor. Fara efect contabil: niciun cont, nicio corespondenta,
-- nicio dimensiune. Natura unei vanzari e livrare sau avans; ce inseamna asta in
-- registru decide motorul de postare, dupa reguli care inca nu exista.
--
-- Triggerul de inghetare e acelasi ca pe linii: continutul urmeaza starea
-- documentului parinte. Functia e proprie acestei migrari, ca derularea ei sa
-- nu depinda de ordinea in care sunt derulate celelalte.
-- =============================================================================

SET LOCAL ROLE evidenta_rls;

-- Aceeasi regula ca pe liniile de document — continutul urmeaza starea
-- documentului parinte — cu functie proprie, si motivul e reversibilitatea: o
-- functie partajata intre migrari face ca derularea celei care o creeaza sa
-- depinda de ordinea in care sunt derulate celelalte. Fisierele de migrare sunt
-- append-only (`C31`), deci aceste copii sunt istorie, nu cod intretinut.
--
-- SECURITY DEFINER fiindca sub FORCE RLS pana si proprietarul e supus
-- politicilor, iar o cautare filtrata ar raspunde „nu exista" si ar lasa
-- scrierea sa treaca.
CREATE OR REPLACE FUNCTION rls.sales_content_follows_its_document() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    target uuid := COALESCE(NEW.document_id, OLD.document_id);
    doc_state text;
BEGIN
    SELECT state INTO doc_state FROM document WHERE id = target;

    -- Documentul insusi e sters in aceeasi tranzactie (o ciorna abandonata):
    -- copiii pleaca inaintea lui si nu au ce urma.
    IF NOT FOUND THEN
        RETURN COALESCE(NEW, OLD);
    END IF;

    IF doc_state <> 'draft' THEN
        RAISE EXCEPTION
            'document % is % — its contents are frozen (% refused on %)',
            target, doc_state, TG_OP, TG_TABLE_NAME
            USING ERRCODE = 'restrict_violation';
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$;

REVOKE ALL ON FUNCTION rls.sales_content_follows_its_document() FROM PUBLIC;

-- ADR-043 §4.1: `CREATE TRIGGER` verifica EXECUTE la CREARE si se emite ca
-- proprietar al tabelei — `evidenta_owner`, care e NOINHERIT.
GRANT EXECUTE ON FUNCTION rls.sales_content_follows_its_document() TO evidenta_owner;

RESET ROLE;

CREATE TRIGGER sales_document_follows_its_document
    BEFORE INSERT OR UPDATE OR DELETE ON sales_document
    FOR EACH ROW EXECUTE FUNCTION rls.sales_content_follows_its_document();

CREATE TRIGGER proforma_document_follows_its_document
    BEFORE INSERT OR UPDATE OR DELETE ON proforma_document
    FOR EACH ROW EXECUTE FUNCTION rls.sales_content_follows_its_document();

CREATE TRIGGER customer_order_follows_its_document
    BEFORE INSERT OR UPDATE OR DELETE ON customer_order
    FOR EACH ROW EXECUTE FUNCTION rls.sales_content_follows_its_document();

ALTER TABLE sales_document ENABLE ROW LEVEL SECURITY;
ALTER TABLE sales_document FORCE  ROW LEVEL SECURITY;
CREATE POLICY sales_document_access ON sales_document
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

ALTER TABLE proforma_document ENABLE ROW LEVEL SECURITY;
ALTER TABLE proforma_document FORCE  ROW LEVEL SECURITY;
CREATE POLICY proforma_document_access ON proforma_document
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

ALTER TABLE customer_order ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer_order FORCE  ROW LEVEL SECURITY;
CREATE POLICY customer_order_access ON customer_order
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

GRANT SELECT, INSERT, UPDATE, DELETE
    ON sales_document, proforma_document, customer_order TO evidenta_app;
