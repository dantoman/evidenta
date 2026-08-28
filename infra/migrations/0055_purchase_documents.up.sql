-- =============================================================================
-- Tipurile concrete de cumparare: document de cumparare, comanda furnizor
--
-- Autoritate:  docs/decisions/004-company-context.md
--              docs/specs/spec-a-tenancy.md §2.6
--              CLAUDE.md R1, R2, R20, C34
--
-- Aceeasi structura ca la vanzare, in sens invers, cu o diferenta care nu e
-- cosmetica: numarul si data furnizorului sunt ALE LUI. Nu trec prin seria
-- noastra si nu se scriu in `document.series` / `document.number` — un registru
-- care si-ar atribui numere emise de altcineva e gresit intr-un fel care apare
-- abia la o verificare incrucisata.
--
-- Perechea (furnizor, numar, data) e cheia naturala pe care `R20` deduplica
-- acelasi document venit pe doua cai — import bancar si tastare, e-Factura si
-- PDF scanat. Furnizorul sta pe antet; jumatatea de aici e ce face perechea
-- adresabila.
-- =============================================================================

ALTER TABLE purchase_document
    ALTER COLUMN supplier_document_number TYPE text COLLATE "C";

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
CREATE OR REPLACE FUNCTION rls.purchase_content_follows_its_document() RETURNS trigger
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

REVOKE ALL ON FUNCTION rls.purchase_content_follows_its_document() FROM PUBLIC;

-- ADR-043 §4.1: `CREATE TRIGGER` verifica EXECUTE la CREARE si se emite ca
-- proprietar al tabelei — `evidenta_owner`, care e NOINHERIT.
GRANT EXECUTE ON FUNCTION rls.purchase_content_follows_its_document() TO evidenta_owner;

RESET ROLE;

CREATE TRIGGER purchase_document_follows_its_document
    BEFORE INSERT OR UPDATE OR DELETE ON purchase_document
    FOR EACH ROW EXECUTE FUNCTION rls.purchase_content_follows_its_document();

CREATE TRIGGER supplier_order_follows_its_document
    BEFORE INSERT OR UPDATE OR DELETE ON supplier_order
    FOR EACH ROW EXECUTE FUNCTION rls.purchase_content_follows_its_document();

ALTER TABLE purchase_document ENABLE ROW LEVEL SECURITY;
ALTER TABLE purchase_document FORCE  ROW LEVEL SECURITY;
CREATE POLICY purchase_document_access ON purchase_document
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

ALTER TABLE supplier_order ENABLE ROW LEVEL SECURITY;
ALTER TABLE supplier_order FORCE  ROW LEVEL SECURITY;
CREATE POLICY supplier_order_access ON supplier_order
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

GRANT SELECT, INSERT, UPDATE, DELETE ON purchase_document, supplier_order TO evidenta_app;
