-- =============================================================================
-- Stratul documentar: linii, storno, imutabilitate, colatii, politici
--
-- Autoritate:  docs/decisions/022-numerotare-sabloane.md
--              docs/decisions/004-company-context.md
--              docs/decisions/034-denumire-legala-si-interna.md
--              docs/specs/spec-a-tenancy.md §2.6
--              CLAUDE.md R1, R2, C34
--
-- Ce nu se poate exprima in Django si de aceea traieste aici:
--
--   1. IMUTABILITATEA DOCUMENTULUI VALIDAT. Cerinta e „se impune la nivel de
--      model, nu prin conventie in views" — iar un serviciu nu e nivelul de
--      model: importul in masa, migrarile de date si orice UPDATE din psql il
--      ocolesc, si exact acolo se editeaza tacit un document deja emis.
--   2. LINIILE URMEAZA DOCUMENTUL. O linie nu se scrie, nu se modifica si nu se
--      sterge pe un document iesit din ciorna. Regula e a documentului parinte,
--      deci nu poate fi un CHECK pe linie.
--   3. Colatiile: numerele si codurile sunt CODURI (C34).
-- =============================================================================

-- --- backfill: data contabila a documentelor existente ----------------------
--
-- Vezi nota din `0050_numbering_series.up.sql`: sub FORCE RLS proprietarul nu
-- vede randurile, deci acest UPDATE atinge zero randuri, iar `SET NOT NULL` care
-- il urmeaza scaneaza tabela fizic si esueaza zgomotos daca existau. Zgomotos e
-- raspunsul corect — o data contabila inventata pe un document real ar decide
-- tacit in ce perioada cade efectul lui.
UPDATE document SET accounting_date = document_date WHERE accounting_date IS NULL;

-- --- colatii (C34, ADR-015) --------------------------------------------------
--
-- `document_line.description` NU primeste "C": e o denumire, iar ordonarea ei e
-- lingvistica. Regula taie in ambele sensuri si gardianul de model o verifica in
-- ambele.
ALTER TABLE document           ALTER COLUMN external_number  TYPE text COLLATE "C";
ALTER TABLE document_line      ALTER COLUMN unit_code        TYPE text COLLATE "C";
ALTER TABLE document_line      ALTER COLUMN vat_regime_code  TYPE text COLLATE "C";
ALTER TABLE document_line      ALTER COLUMN vat_rate_key     TYPE text COLLATE "C";

-- --- imutabilitatea documentului validat ------------------------------------
--
-- Schema `rls` apartine lui `evidenta_rls`, iar owner-ul are doar USAGE pe ea
-- (`0003_access_predicates.sql`). Functiile se creeaza prin SET ROLE, ca in
-- `0036` si `0048`.
SET LOCAL ROLE evidenta_rls;

-- LISTA DE PERMISE, NU DE INTERZISE. Diferenta conteaza peste doi ani: cu o
-- lista de coloane interzise, o coloana adaugata mai tarziu ar fi ramas TACIT
-- modificabila pe un document validat, si nimeni n-ar fi observat. Comparand
-- randul intreg minus coloanele ciclului de viata, o coloana noua e inghetata
-- din oficiu, iar dezghetarea ei cere o editare vizibila aici.
CREATE OR REPLACE FUNCTION rls.document_stays_frozen() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    lifecycle text[] := ARRAY[
        'state', 'confirmed_by_user_id', 'confirmed_at', 'posted_at',
        'cancelled_by_user_id', 'cancelled_at', 'cancellation_reason', 'updated_at'
    ];
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.state <> 'draft' THEN
            RAISE EXCEPTION
                'document % is % and is not deleted; it is cancelled, with a reason',
                OLD.id, OLD.state
                USING ERRCODE = 'restrict_violation';
        END IF;
        RETURN OLD;
    END IF;

    IF OLD.state = 'draft' THEN
        RETURN NEW;
    END IF;

    -- Inapoi in ciorna nu se merge. Un document validat are numar alocat:
    -- dezvalidarea ori elibereaza un numar — ceea ce un registru n-are voie sa
    -- faca — ori arde unul tacut.
    IF NEW.state = 'draft' THEN
        RAISE EXCEPTION
            'document % is % and cannot return to draft; a correction is a reversal',
            OLD.id, OLD.state
            USING ERRCODE = 'restrict_violation';
    END IF;

    IF (to_jsonb(NEW) - lifecycle) IS DISTINCT FROM (to_jsonb(OLD) - lifecycle) THEN
        RAISE EXCEPTION
            'document % is % and is frozen; only the lifecycle columns change '
            'after validation', OLD.id, OLD.state
            USING ERRCODE = 'restrict_violation';
    END IF;

    RETURN NEW;
END;
$$;

REVOKE ALL ON FUNCTION rls.document_stays_frozen() FROM PUBLIC;

-- ADR-043 §4.1: `CREATE TRIGGER` verifica EXECUTE la CREARE si se emite ca
-- proprietar al tabelei — `evidenta_owner`, care e NOINHERIT si nu mosteneste
-- nimic de la `evidenta_rls`.
GRANT EXECUTE ON FUNCTION rls.document_stays_frozen() TO evidenta_owner;

-- Aceeasi regula, aplicata liniilor si tabelelor de tip: regula e a
-- documentului parinte, deci se citeste de acolo. SECURITY DEFINER fiindca sub
-- FORCE RLS pana si proprietarul e supus politicilor, iar o cautare filtrata ar
-- raspunde „nu exista" si ar lasa scrierea sa treaca.
CREATE OR REPLACE FUNCTION rls.follows_its_document() RETURNS trigger
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

REVOKE ALL ON FUNCTION rls.follows_its_document() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION rls.follows_its_document() TO evidenta_owner;

RESET ROLE;

CREATE TRIGGER document_stays_frozen
    BEFORE UPDATE OR DELETE ON document
    FOR EACH ROW EXECUTE FUNCTION rls.document_stays_frozen();

CREATE TRIGGER document_line_follows_its_document
    BEFORE INSERT OR UPDATE OR DELETE ON document_line
    FOR EACH ROW EXECUTE FUNCTION rls.follows_its_document();

CREATE TRIGGER reversal_document_follows_its_document
    BEFORE INSERT OR UPDATE OR DELETE ON reversal_document
    FOR EACH ROW EXECUTE FUNCTION rls.follows_its_document();

-- --- politici: sablonul complet din ADR-004, cu toate patru clauzele ---------
--
-- Inclusiv ingustarea pe `app.current_company_id()`. Pe tabele NOI nu exista
-- motiv sa se abata (`OD-57`): costul azi e zero — functia intoarce NULL cand
-- GUC-ul lipseste, deci clauza e adevarata — iar adaugarea ei mai tarziu pe
-- tabela de linii ar fi migrare pe a doua cea mai mare tabela din sistem.

ALTER TABLE document_line ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_line FORCE  ROW LEVEL SECURITY;
CREATE POLICY document_line_access ON document_line
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

ALTER TABLE reversal_document ENABLE ROW LEVEL SECURITY;
ALTER TABLE reversal_document FORCE  ROW LEVEL SECURITY;
CREATE POLICY reversal_document_access ON reversal_document
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

-- --- granturi ---------------------------------------------------------------
--
-- DELETE inclus, si nu din neglijenta: o ciorna se sterge cu totul, iar
-- `replace_lines` sterge liniile ca sa le rescrie. Ce impiedica stergerea unui
-- document validat este triggerul de mai sus, nu absenta grantului — fiindca
-- absenta lui ar fi impiedicat si stergerea ciornei.
GRANT SELECT, INSERT, UPDATE, DELETE ON document_line, reversal_document TO evidenta_app;

-- `evidenta_rls` are BYPASSRLS dar NICIUN privilegiu de tabela implicit — i se
-- acorda punctual, exact ce citesc predicatele si functiile SECURITY DEFINER
-- (`0001_roles.sql`). Fara asta, triggerul de mai sus moare cu „permission
-- denied for table document" chiar in tranzactia care insereaza prima linie —
-- masurat, nu presupus. Doar SELECT: functia citeste starea, nu o schimba.
--
-- Acelasi grant sustine si triggerele tabelelor de tip din `0054` si `0055`.
GRANT SELECT ON document TO evidenta_rls;
