-- =============================================================================
-- Trezoreria: incasarea si plata
--
-- Autoritate:  docs/decisions/073-forma-postarii-documentelor-comerciale.md §5
--              docs/decisions/004-company-context.md
--              docs/specs/spec-a-tenancy.md §2.6
--              CLAUDE.md R1, R2, C30
--
-- Primele doua tipuri de document din produs care NU poarta pozitii. Suma sta pe
-- randul de aici, nu pe linii: o incasare de 3.000 lei e un numar, nu o lista.
--
-- Ce nu e pe tabela, deliberat: ce factura se stinge. Postarea n-are nevoie —
-- debit trezorerie, credit creante, oricare creanta (§5) — iar legarea e
-- decontarea, cu handlerul ei si sesiunea ei. O coloana nula aici ar fi o
-- legatura pe jumatate pe care rapoartele ar incepe s-o citeasca.
-- =============================================================================

SET LOCAL ROLE evidenta_rls;

-- Aceeasi regula ca la celelalte extensii de document — continutul urmeaza
-- starea documentului parinte — cu functie proprie, din acelasi motiv de
-- reversibilitate: o functie partajata intre migrari face ca derularea celei
-- care o creeaza sa depinda de ordinea celorlalte (`C31` face fisierele
-- append-only, deci copiile sunt istorie, nu cod intretinut).
CREATE OR REPLACE FUNCTION rls.treasury_content_follows_its_document() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    target uuid := COALESCE(NEW.document_id, OLD.document_id);
    doc_state text;
BEGIN
    SELECT state INTO doc_state FROM document WHERE id = target;

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

REVOKE ALL ON FUNCTION rls.treasury_content_follows_its_document() FROM PUBLIC;

-- ADR-043 §4.1: `CREATE TRIGGER` verifica EXECUTE la CREARE si se emite ca
-- proprietar al tabelei — `evidenta_owner`, care e NOINHERIT.
GRANT EXECUTE ON FUNCTION rls.treasury_content_follows_its_document() TO evidenta_owner;

RESET ROLE;

CREATE TRIGGER treasury_document_follows_its_document
    BEFORE INSERT OR UPDATE OR DELETE ON treasury_document
    FOR EACH ROW EXECUTE FUNCTION rls.treasury_content_follows_its_document();

ALTER TABLE treasury_document ENABLE ROW LEVEL SECURITY;
ALTER TABLE treasury_document FORCE  ROW LEVEL SECURITY;
CREATE POLICY treasury_document_access ON treasury_document
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

GRANT SELECT, INSERT, UPDATE, DELETE ON treasury_document TO evidenta_app;
