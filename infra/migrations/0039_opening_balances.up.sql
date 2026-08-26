-- =============================================================================
-- F1.7.2 — Soldurile initiale: colatii, inghetare, ireversibilitate, politici
--
-- Autoritate:  docs/specs/spec-b-accounting.md §8 (structura, validarea, postarea)
--              docs/decisions/039-valuta-si-perioade.md §11 (Acceptat)
--              docs/decisions/015-colatie-icu.md
--              CLAUDE.md R1, R2, R10, R15, C30, C31, C34
--
-- Sapte tabele: lotul si cele sase seturi de linii din §8.1. Tabelele le creeaza
-- migrarea Django; aici stau cele patru lucruri care nu se pot exprima in Django
-- si care sunt chiar regulile:
--
--   1. IREVERSIBILITATEA PERIOADEI DE START (ADR-039 §11). Odata ce un lot al
--      companiei e `posted`, orice alt lot al ei trebuie sa poarte ACEEASI
--      `as_of_date`. Nu „un singur lot": §8.3 cere corectia prin storno si lot
--      nou, iar lotul nou e legitim — la aceeasi data. Ce se inchide e mutarea
--      inceputului evidentei dupa ce s-au scris inregistrari in urma lui.
--   2. INGHETAREA LINIILOR. Din `validated` incolo, cele sase tabele refuza orice
--      scriere. Fara asta „validat" ar insemna „a fost corect la un moment dat",
--      ceea ce nu e o proprietate pe care sa se sprijine o postare.
--   3. IMUTABILITATEA LOTULUI POSTAT (R10). Un lot postat a produs o inregistrare
--      intr-un registru append-only; nu se mai editeaza in loc.
--   4. POLITICILE si granturile.
--
-- DE CE IN BAZA, pentru toate patru: importatorul 1C, migrarile de date si orice
-- INSERT direct NU trec prin serviciu — si exact acolo apar soldurile initiale.
-- Serviciul verifica si el, ca sa dea un cod stabil (C10) in loc de o eroare de
-- integritate; garantia sta aici.
--
-- CE NU E AICI, deliberat: niciun cod de cont. Contul tehnic de deschidere din
-- §8.3 e numit de apelant prin id (`counterpart_account_id`), iar continutul
-- planului de conturi este `OD-23`, deschisa (R15).
-- =============================================================================

-- --- colatii (C34, ADR-015) --------------------------------------------------
--
-- Numarul documentului sursa si codul de cumulativ payroll sunt CODURI: se
-- potrivesc si se ordoneaza, nu se sorteaza lingvistic. Restul coloanelor de
-- text de aici — `lot`, `document_type`, `rejected_reason` — raman pe colatia
-- implicita a bazei.

ALTER TABLE opening_balance_receivable ALTER COLUMN document_number TYPE text COLLATE "C";
ALTER TABLE opening_balance_payable    ALTER COLUMN document_number TYPE text COLLATE "C";
ALTER TABLE opening_balance_payroll_cumulative ALTER COLUMN code TYPE text COLLATE "C";

-- --- 1. perioada de start nu se mai muta (ADR-039 §11) -----------------------
--
-- Schema `rls` apartine lui `evidenta_rls`, iar owner-ul are doar USAGE pe ea
-- (`0003_access_predicates.sql`). Functiile se creeaza deci prin SET ROLE, la fel
-- ca in `0014`, `0032` si `0036`.

SET LOCAL ROLE evidenta_rls;

-- SECURITY DEFINER, si motivul nu e comoditate: sub FORCE ROW LEVEL SECURITY
-- pana si owner-ul e supus politicilor, deci un import rulat fara context de
-- tenant n-ar VEDEA lotul deja postat si garda ar trece degeaba. Un gardian care
-- se dezarmeaza singur exact in cazul pentru care exista nu e gardian.
CREATE OR REPLACE FUNCTION rls.opening_balance_start_is_fixed() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    fixed date;
BEGIN
    SELECT b.as_of_date INTO fixed
      FROM opening_balance_batch b
     WHERE b.company_id = NEW.company_id
       AND b.status = 'posted'
       AND b.id <> NEW.id
     LIMIT 1;

    IF FOUND AND fixed <> NEW.as_of_date THEN
        RAISE EXCEPTION 'company % posted its opening balances as of %; the start '
                        'period of a company is chosen once and does not move '
                        '(ADR-039 section 11)', NEW.company_id, fixed
            USING ERRCODE = 'raise_exception';
    END IF;
    RETURN NEW;
END;
$$;

RESET ROLE;

CREATE TRIGGER opening_balance_start_is_fixed
    BEFORE INSERT OR UPDATE ON opening_balance_batch
    FOR EACH ROW EXECUTE FUNCTION rls.opening_balance_start_is_fixed();

-- --- 2. lotul postat nu se mai editeaza (R10) --------------------------------

SET LOCAL ROLE evidenta_rls;

CREATE OR REPLACE FUNCTION rls.opening_balance_batch_immutable() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF OLD.status = 'posted' THEN
        RAISE EXCEPTION 'opening balance batch % is posted; it is corrected with a '
                        'reversal and a new batch, never edited in place '
                        '(Spec B section 8.3, R10)', OLD.id
            USING ERRCODE = 'raise_exception';
    END IF;
    RETURN NEW;
END;
$$;

RESET ROLE;

CREATE TRIGGER opening_balance_batch_immutable
    BEFORE UPDATE ON opening_balance_batch
    FOR EACH ROW EXECUTE FUNCTION rls.opening_balance_batch_immutable();

-- --- 3. liniile ingheata cand lotul iese din `draft` -------------------------
--
-- O singura functie, sase triggere. Toate cele sase tabele au coloana `batch_id`,
-- deci intrebarea e aceeasi peste tot, iar sase copii ale ei ar fi sase locuri in
-- care una singura ramane in urma.
--
-- `NEW` nu exista la DELETE si `OLD` nu exista la INSERT — in plpgsql, atingerea
-- celui neatribuit e eroare, nu NULL. De aceea ramura pe `TG_OP`.

SET LOCAL ROLE evidenta_rls;

CREATE OR REPLACE FUNCTION rls.opening_balance_line_frozen() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    target uuid;
    state  text;
BEGIN
    IF TG_OP = 'DELETE' THEN
        target := OLD.batch_id;
    ELSE
        target := NEW.batch_id;
    END IF;

    SELECT b.status INTO state FROM opening_balance_batch b WHERE b.id = target;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'opening balance row names batch %, which does not exist',
            target USING ERRCODE = 'foreign_key_violation';
    END IF;

    IF state <> 'draft' THEN
        RAISE EXCEPTION 'opening balance batch % is %; its rows are frozen so that '
                        'what posts is what was checked (Spec B section 8.2)',
                        target, state
            USING ERRCODE = 'raise_exception';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

RESET ROLE;

CREATE TRIGGER opening_balance_gl_frozen
    BEFORE INSERT OR UPDATE OR DELETE ON opening_balance_gl
    FOR EACH ROW EXECUTE FUNCTION rls.opening_balance_line_frozen();

CREATE TRIGGER opening_balance_receivable_frozen
    BEFORE INSERT OR UPDATE OR DELETE ON opening_balance_receivable
    FOR EACH ROW EXECUTE FUNCTION rls.opening_balance_line_frozen();

CREATE TRIGGER opening_balance_payable_frozen
    BEFORE INSERT OR UPDATE OR DELETE ON opening_balance_payable
    FOR EACH ROW EXECUTE FUNCTION rls.opening_balance_line_frozen();

CREATE TRIGGER opening_balance_inventory_frozen
    BEFORE INSERT OR UPDATE OR DELETE ON opening_balance_inventory
    FOR EACH ROW EXECUTE FUNCTION rls.opening_balance_line_frozen();

CREATE TRIGGER opening_balance_asset_frozen
    BEFORE INSERT OR UPDATE OR DELETE ON opening_balance_asset
    FOR EACH ROW EXECUTE FUNCTION rls.opening_balance_line_frozen();

CREATE TRIGGER opening_balance_payroll_frozen
    BEFORE INSERT OR UPDATE OR DELETE ON opening_balance_payroll_cumulative
    FOR EACH ROW EXECUTE FUNCTION rls.opening_balance_line_frozen();

-- --- 4. politici: sablonul la nivel de companie (spec-a §2.6, ADR-004) -------
--
-- `WITH CHECK` identic cu `USING`: fara el un rand s-ar putea scrie cu
-- company_id-ul altcuiva si ar deveni invizibil chiar in momentul commit-ului.
--
-- A patra clauza nu ingusteaza nimic azi — calea de request nu seteaza
-- `app.company_id`, doar decoratorul Celery o face — si e scrisa oricum, fiindca
-- adaugarea ei ulterioara ar fi o migrare peste o tabela citita intre timp.
-- Divergenta cu restul tabelelor company-scoped ramane `OD-57`.

ALTER TABLE opening_balance_batch ENABLE ROW LEVEL SECURITY;
ALTER TABLE opening_balance_batch FORCE  ROW LEVEL SECURITY;
CREATE POLICY opening_balance_batch_access ON opening_balance_batch
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

ALTER TABLE opening_balance_gl ENABLE ROW LEVEL SECURITY;
ALTER TABLE opening_balance_gl FORCE  ROW LEVEL SECURITY;
CREATE POLICY opening_balance_gl_access ON opening_balance_gl
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

ALTER TABLE opening_balance_receivable ENABLE ROW LEVEL SECURITY;
ALTER TABLE opening_balance_receivable FORCE  ROW LEVEL SECURITY;
CREATE POLICY opening_balance_receivable_access ON opening_balance_receivable
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

ALTER TABLE opening_balance_payable ENABLE ROW LEVEL SECURITY;
ALTER TABLE opening_balance_payable FORCE  ROW LEVEL SECURITY;
CREATE POLICY opening_balance_payable_access ON opening_balance_payable
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

ALTER TABLE opening_balance_inventory ENABLE ROW LEVEL SECURITY;
ALTER TABLE opening_balance_inventory FORCE  ROW LEVEL SECURITY;
CREATE POLICY opening_balance_inventory_access ON opening_balance_inventory
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

ALTER TABLE opening_balance_asset ENABLE ROW LEVEL SECURITY;
ALTER TABLE opening_balance_asset FORCE  ROW LEVEL SECURITY;
CREATE POLICY opening_balance_asset_access ON opening_balance_asset
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

ALTER TABLE opening_balance_payroll_cumulative ENABLE ROW LEVEL SECURITY;
ALTER TABLE opening_balance_payroll_cumulative FORCE  ROW LEVEL SECURITY;
CREATE POLICY opening_balance_payroll_access ON opening_balance_payroll_cumulative
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
-- Lotul: fara DELETE. Un lot gresit se RESPINGE, nu se sterge — `rejected` exista
-- exact ca sa ramana urma a ce s-a incercat si de ce s-a oprit. `0001_roles.sql`
-- acorda privilegii IMPLICITE pentru orice tabela creata de owner, deci fara
-- REVOKE singurul lucru care ar opri stergerea ar fi o omisiune (`OD-47`).
GRANT SELECT, INSERT, UPDATE ON opening_balance_batch TO evidenta_app;
REVOKE DELETE ON opening_balance_batch FROM evidenta_app;

-- Liniile: CU DELETE. Un lot in lucru se corecteaza stergand randuri, iar
-- triggerul de mai sus e cel care decide care stergere trece — dupa `validated`
-- niciuna. Privilegiul ramane, garda e in trigger.
GRANT SELECT, INSERT, UPDATE, DELETE ON opening_balance_gl                 TO evidenta_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON opening_balance_receivable         TO evidenta_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON opening_balance_payable            TO evidenta_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON opening_balance_inventory          TO evidenta_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON opening_balance_asset              TO evidenta_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON opening_balance_payroll_cumulative TO evidenta_app;

-- `evidenta_rls` are BYPASSRLS dar NICIUN privilegiu de tabela implicit — i se
-- acorda punctual, doar pe ce citesc functiile de mai sus. Fara randul asta,
-- triggerele ar esua cu „permission denied" la primul rand inserat.
GRANT SELECT ON opening_balance_batch TO evidenta_rls;

-- Functiile de trigger nu se apeleaza din aplicatie; nimeni nu are nevoie de
-- EXECUTE pe ele, si PUBLIC nu trebuie sa-l pastreze pe cel implicit.
--
-- SUB `SET LOCAL ROLE`, si asta nu e simetrie de stil. `evidenta_owner` este
-- NOINHERIT (`0001_roles.sql`), deci apartenenta la `evidenta_rls` nu-i da
-- privilegiile decat dupa `SET ROLE`. Un REVOKE emis de cine nu detine functia
-- nu esueaza — da un WARNING si nu revoca nimic. Masurat, nu presupus: fara
-- randurile de rol de mai jos, `proacl` ramane NULL, adica PUBLIC pastreaza
-- EXECUTE-ul implicit si REVOKE-ul e decor.
SET LOCAL ROLE evidenta_rls;

REVOKE ALL ON FUNCTION rls.opening_balance_start_is_fixed()  FROM PUBLIC;
REVOKE ALL ON FUNCTION rls.opening_balance_batch_immutable() FROM PUBLIC;
REVOKE ALL ON FUNCTION rls.opening_balance_line_frozen()     FROM PUBLIC;

RESET ROLE;
