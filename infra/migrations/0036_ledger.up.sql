-- =============================================================================
-- F1.2 — Registrul: colatii, politici, granturi, echilibru, imutabilitate
--
-- Autoritate:  docs/specs/spec-b-accounting.md §1.2, §1.3, §1.6, §6.3, §9
--              docs/decisions/006-reversal-two-dates.md
--              docs/decisions/029-dimensiuni-analitice.md
--              docs/decisions/032-cheia-de-partitionare.md
--              docs/decisions/039-valuta-si-perioade.md
--              CLAUDE.md R10, R11, R12, R21, R22, C34
--
-- Trei mecanisme care nu se pot exprima in Django si care sunt chiar invariantii:
--
--   1. ECHILIBRUL (R11). PostgreSQL n-are CHECK peste un agregat al altei tabele.
--      Deci: trigger pe `journal_line` care intretine totalurile pe inregistrare,
--      plus CONSTRAINT TRIGGER DEFERRABLE INITIALLY DEFERRED care verifica la
--      COMMIT. Amanarea e obligatorie — liniile se insereaza una cate una, iar
--      intre prima si ultima inregistrarea e dezechilibrata prin constructie.
--   2. IMUTABILITATEA (R10). Trigger care refuza UPDATE si DELETE pe o
--      inregistrare `posted`, cu o singura exceptie: tranzitia `draft -> posted`.
--   3. PERIOADA INCHISA (R12). Trigger BEFORE INSERT care citeste starea
--      perioadei. Prima bariera e motorul; asta e a doua, si exista fiindcă
--      importul 1C, migrarile de date si orice INSERT direct ocolesc motorul.
--
-- De ce nu doar in serviciu, pentru toate trei: importul in masa, migrarea 1C si
-- orice INSERT dintr-o migrare de date NU trec prin serviciu — si exact acolo
-- apar dezechilibrele.
-- =============================================================================

-- --- colatii (C34, ADR-015) --------------------------------------------------

ALTER TABLE journal_entry ALTER COLUMN entry_number TYPE text COLLATE "C";

-- --- echilibrul: totalurile intretinute pe inregistrare ----------------------
--
-- Costul e cunoscut si asumat: triggerul ruleaza pentru fiecare linie, iar la
-- importul 1C, cu sute de mii de linii, e cea mai scumpa operatiune din proces.
-- Mitigarea (dezactivarea in import, cu revalidare in bloc la final) este cale
-- privilegiata in sensul spec-a §6 si se trateaza ca atare — nu ca optimizare
-- locala. Nu e implementata aici.

-- Schema `rls` apartine lui `evidenta_rls`, iar owner-ul are doar USAGE pe ea
-- (`0003_access_predicates.sql`). Functiile se creeaza deci prin SET ROLE, la fel
-- ca in `0014` si `0032` — owner-ul o poate face fiindca e membru al rolului.
SET LOCAL ROLE evidenta_rls;

CREATE OR REPLACE FUNCTION rls.journal_entry_totals() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    target uuid := COALESCE(NEW.journal_entry_id, OLD.journal_entry_id);
BEGIN
    UPDATE journal_entry
       SET total_debit  = COALESCE((SELECT sum(debit)  FROM journal_line
                                     WHERE journal_entry_id = target), 0),
           total_credit = COALESCE((SELECT sum(credit) FROM journal_line
                                     WHERE journal_entry_id = target), 0)
     WHERE id = target;
    RETURN NULL;
END;
$$;

-- SECURITY DEFINER, si motivul nu e comoditate: sub FORCE ROW LEVEL SECURITY
-- pana si owner-ul e supus politicilor, deci o migrare de date rulata fara
-- context de tenant n-ar putea aseza totalurile. Functia ruleaza ca
-- `evidenta_rls`, care are BYPASSRLS si NOLOGIN; aplicatia primeste dreptul de a
-- insera linii, nu de a scrie totaluri direct.

RESET ROLE;

CREATE TRIGGER journal_line_maintains_totals
    AFTER INSERT OR UPDATE OR DELETE ON journal_line
    FOR EACH ROW EXECUTE FUNCTION rls.journal_entry_totals();

-- --- echilibrul: verificarea la COMMIT ---------------------------------------

SET LOCAL ROLE evidenta_rls;

-- RECITESTE RANDUL. Nu se uita la `NEW`, si asta e chiar lectia.
--
-- Un CONSTRAINT TRIGGER amanat nu ruleaza o data la commit: ruleaza pentru
-- FIECARE eveniment din coada, cu `NEW` inghetat la momentul lui. Liniile se
-- insereaza una cate una, deci coada contine si starea de dupa prima linie —
-- dezechilibrata prin constructie. Cu `NEW`, verificarea ar respinge la commit
-- exact inregistrarile corecte, iar amanarea n-ar rezolva nimic.
--
-- Recitirea din tabela intoarce, la momentul verificarii, starea FINALA. Toate
-- evenimentele din coada vad atunci acelasi rand, si raspunsul e acelasi.
--
-- Gasit rulandu-l, nu citindu-l: prima linie a primului test a picat cu
-- „out of balance: debit 100, credit 0".
CREATE OR REPLACE FUNCTION rls.journal_entry_balanced() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    row_status text;
    row_debit  numeric(20,4);
    row_credit numeric(20,4);
BEGIN
    SELECT status, total_debit, total_credit
      INTO row_status, row_debit, row_credit
      FROM journal_entry WHERE id = NEW.id;

    -- Sters in aceeasi tranzactie (o ciorna abandonata): nimic de verificat.
    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    -- O inregistrare in lucru poate fi goala; una postata nu.
    IF row_status = 'draft' AND row_debit = 0 AND row_credit = 0 THEN
        RETURN NULL;
    END IF;

    IF row_debit <> row_credit THEN
        RAISE EXCEPTION 'journal_entry % is out of balance: debit %, credit %',
            NEW.id, row_debit, row_credit
            USING ERRCODE = 'check_violation';
    END IF;

    IF row_debit = 0 THEN
        RAISE EXCEPTION 'journal_entry % has no amount', NEW.id
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NULL;
END;
$$;

RESET ROLE;

CREATE CONSTRAINT TRIGGER journal_entry_balance_at_commit
    AFTER INSERT OR UPDATE ON journal_entry
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION rls.journal_entry_balanced();

-- --- imutabilitatea inregistrarii postate (R10) ------------------------------

SET LOCAL ROLE evidenta_rls;

CREATE OR REPLACE FUNCTION rls.journal_entry_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.status = 'posted' THEN
            RAISE EXCEPTION 'journal_entry % is posted and cannot be deleted; '
                            'correction is a reversal, not an erasure', OLD.id
                USING ERRCODE = 'raise_exception';
        END IF;
        RETURN OLD;
    END IF;

    IF OLD.status = 'posted' THEN
        -- Singura scriere admisa pe o inregistrare postata: totalurile, asezate
        -- de triggerul de mai sus in aceeasi tranzactie cu liniile. Orice
        -- altceva — data, perioada, descrierea, tipul — e refuzat.
        IF NEW.status IS DISTINCT FROM OLD.status
           OR NEW.accounting_date IS DISTINCT FROM OLD.accounting_date
           OR NEW.period_id IS DISTINCT FROM OLD.period_id
           OR NEW.entry_type IS DISTINCT FROM OLD.entry_type
           OR NEW.accounting_event_id IS DISTINCT FROM OLD.accounting_event_id
           OR NEW.reverses_entry_id IS DISTINCT FROM OLD.reverses_entry_id
           OR NEW.corrects_period_id IS DISTINCT FROM OLD.corrects_period_id
           OR NEW.entry_number IS DISTINCT FROM OLD.entry_number
           OR NEW.description IS DISTINCT FROM OLD.description THEN
            RAISE EXCEPTION 'journal_entry % is posted and immutable (R10)', OLD.id
                USING ERRCODE = 'raise_exception';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

RESET ROLE;

CREATE TRIGGER journal_entry_stays_immutable
    BEFORE UPDATE OR DELETE ON journal_entry
    FOR EACH ROW EXECUTE FUNCTION rls.journal_entry_immutable();

-- Liniile unei inregistrari postate nu se modifica si nu se sterg, deloc.
SET LOCAL ROLE evidenta_rls;

CREATE OR REPLACE FUNCTION rls.journal_line_immutable() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    entry_status text;
BEGIN
    SELECT status INTO entry_status FROM journal_entry
     WHERE id = COALESCE(NEW.journal_entry_id, OLD.journal_entry_id);
    IF entry_status = 'posted' THEN
        RAISE EXCEPTION 'journal_line belongs to a posted entry and is immutable (R10)'
            USING ERRCODE = 'raise_exception';
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$;

RESET ROLE;

CREATE TRIGGER journal_line_stays_immutable
    BEFORE UPDATE OR DELETE ON journal_line
    FOR EACH ROW EXECUTE FUNCTION rls.journal_line_immutable();

-- --- refuzul postarii intr-o perioada inchisa (R12, spec-b §6.3) -------------
--
-- A doua bariera. Prima e motorul, si acolo refuzul are cod stabil si mesaj
-- lizibil; aici e ultima linie, pentru caile care nu trec prin motor.
--
-- `end_date` la `period` este INCLUSIVA (vezi modelul), spre deosebire de
-- ferestrele half-open din restul sistemului. De aceea `BETWEEN`, si de aceea
-- e scris aici: confuzia dintre cele doua conventii produce o eroare de o zi pe
-- an, gasita la un client, nu intr-un test.

SET LOCAL ROLE evidenta_rls;

CREATE OR REPLACE FUNCTION rls.journal_entry_period_open() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    period_state text;
BEGIN
    SELECT status INTO period_state FROM period WHERE id = NEW.period_id;

    IF period_state IS NULL THEN
        RAISE EXCEPTION 'journal_entry names period % which does not exist', NEW.period_id
            USING ERRCODE = 'foreign_key_violation';
    END IF;

    IF period_state <> 'open' THEN
        RAISE EXCEPTION 'period % is % — nothing posts into it (R12)',
            NEW.period_id, period_state
            USING ERRCODE = 'raise_exception';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM period
         WHERE id = NEW.period_id
           AND NEW.accounting_date BETWEEN start_date AND end_date
    ) THEN
        RAISE EXCEPTION 'accounting_date % falls outside period %',
            NEW.accounting_date, NEW.period_id
            USING ERRCODE = 'raise_exception';
    END IF;

    RETURN NEW;
END;
$$;

RESET ROLE;

CREATE TRIGGER journal_entry_needs_open_period
    BEFORE INSERT ON journal_entry
    FOR EACH ROW EXECUTE FUNCTION rls.journal_entry_period_open();

-- --- politici: sablonul complet din ADR-004, cu toate patru clauzele ---------
--
-- Inclusiv ingustarea pe `app.current_company_id()`, pe care ADR-004 o cere si
-- pe care majoritatea tabelelor company-scoped nu o poarta (`OD-57`). Pe tabele
-- NOI nu exista motiv sa se abata: costul azi e zero — functia intoarce NULL
-- cand GUC-ul lipseste, deci clauza e adevarata — iar adaugarea ei mai tarziu pe
-- `journal_line` ar fi migrare pe cea mai mare tabela din sistem.

ALTER TABLE journal_entry ENABLE ROW LEVEL SECURITY;
ALTER TABLE journal_entry FORCE  ROW LEVEL SECURITY;
CREATE POLICY journal_entry_access ON journal_entry
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

ALTER TABLE journal_line ENABLE ROW LEVEL SECURITY;
ALTER TABLE journal_line FORCE  ROW LEVEL SECURITY;
CREATE POLICY journal_line_access ON journal_line
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

ALTER TABLE company_dimension ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_dimension FORCE  ROW LEVEL SECURITY;
CREATE POLICY company_dimension_access ON company_dimension
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
-- Fara DELETE pe registru. Corectia se face prin storno si reinregistrare
-- (R10), iar aici asta e o lipsa de privilegiu, nu o conventie pe care cineva
-- si-o aminteste. UPDATE ramane acordat fiindca `draft -> posted` este un
-- UPDATE — triggerul de imutabilitate decide care UPDATE trece.
GRANT SELECT, INSERT, UPDATE ON journal_entry TO evidenta_app;
REVOKE DELETE ON journal_entry FROM evidenta_app;

GRANT SELECT, INSERT, UPDATE ON journal_line TO evidenta_app;
REVOKE DELETE ON journal_line FROM evidenta_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON company_dimension TO evidenta_app;

-- `evidenta_rls` are BYPASSRLS dar NICIUN privilegiu de tabela implicit — i se
-- acorda punctual, doar pe ce citesc functiile de mai sus. Fara randurile astea,
-- triggerele ar esua cu „permission denied" la prima linie inserata.
GRANT SELECT, UPDATE ON journal_entry TO evidenta_rls;
GRANT SELECT         ON journal_line  TO evidenta_rls;
GRANT SELECT         ON period        TO evidenta_rls;

-- Functiile de trigger nu se apeleaza din aplicatie; nimeni nu are nevoie de
-- EXECUTE pe ele, si PUBLIC nu trebuie sa-l pastreze pe cel implicit.
REVOKE ALL ON FUNCTION rls.journal_entry_totals()      FROM PUBLIC;
REVOKE ALL ON FUNCTION rls.journal_entry_balanced()    FROM PUBLIC;
REVOKE ALL ON FUNCTION rls.journal_entry_immutable()   FROM PUBLIC;
REVOKE ALL ON FUNCTION rls.journal_line_immutable()    FROM PUBLIC;
REVOKE ALL ON FUNCTION rls.journal_entry_period_open() FROM PUBLIC;
