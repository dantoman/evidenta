-- Evenimentele contabile — Spec B §1.1, sarcina F1.3.1.
--
-- Nivel companie. NU e tabela append-only de volum mare in sensul `R21` — Spec B
-- o spune explicit — deci poate primi chei straine. Singura pe care n-o primeste
-- deliberat e cea catre documentul sursa: ar obliga `accounting` sa cunoasca
-- schema modulelor care produc documente, adica exact `D2`.

ALTER TABLE accounting_event ALTER COLUMN event_type           TYPE text COLLATE "C";
ALTER TABLE accounting_event ALTER COLUMN idempotency_key      TYPE text COLLATE "C";
ALTER TABLE accounting_event ALTER COLUMN source_module        TYPE text COLLATE "C";
ALTER TABLE accounting_event ALTER COLUMN source_document_type TYPE text COLLATE "C";
ALTER TABLE accounting_event ALTER COLUMN request_id           TYPE text COLLATE "C";

ALTER TABLE accounting_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounting_event FORCE  ROW LEVEL SECURITY;

-- Sablonul company-scoped din ADR-004: contextul DECIDE tenantul, iar
-- `rls.has_company_access` decide compania. Ambele, nu una — contextul singur ar
-- lasa orice membru al tenantului sa vada orice companie a lui.

CREATE POLICY accounting_event_access ON accounting_event
    FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id)
                AND rls.has_company_access(company_id))
    WITH CHECK (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id)
                AND rls.has_company_access(company_id));

-- --- Coada de repostare ------------------------------------------------------
--
-- Index partial: `pending` si `failed` sunt o fractiune din tabela dupa prima
-- luna, iar interogarea cozii nu are ce cauta intr-un index peste tot istoricul.

CREATE INDEX acc_event_queue_idx
    ON accounting_event (company_id, status)
    WHERE status IN ('pending', 'failed');

-- --- Ce nu se modifica dupa postare ------------------------------------------
--
-- Evenimentul postat e originea unei inregistrari imutabile (`R10`). Daca
-- payload-ul lui s-ar putea schimba dupa postare, lantul din `R13` ar duce
-- inapoi la altceva decat ce a produs postarea — iar reconstituirea unei
-- perioade ar da alt rezultat decat postarea originala.
--
-- Tranzitiile permise dupa `posted` sunt doar catre `superseded`, si numai ale
-- starii: un eveniment inlocuit ramane, fiindca ramane si registrul pe care l-a
-- produs.

CREATE OR REPLACE FUNCTION app.accounting_event_immutable()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.status <> 'posted' THEN
        RETURN NEW;
    END IF;

    IF NEW.status = 'superseded'
       AND NEW.payload            IS NOT DISTINCT FROM OLD.payload
       AND NEW.accounting_date    IS NOT DISTINCT FROM OLD.accounting_date
       AND NEW.event_type         IS NOT DISTINCT FROM OLD.event_type
       AND NEW.idempotency_key    IS NOT DISTINCT FROM OLD.idempotency_key
       AND NEW.capability_snapshot IS NOT DISTINCT FROM OLD.capability_snapshot THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'accounting.event_immutable'
        USING HINT = 'un eveniment postat nu se modifica; corectia se face prin storno';
END;
$$;

CREATE TRIGGER accounting_event_immutable
    BEFORE UPDATE ON accounting_event
    FOR EACH ROW EXECUTE FUNCTION app.accounting_event_immutable();

CREATE OR REPLACE FUNCTION app.accounting_event_no_delete()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'accounting.event_immutable'
        USING HINT = 'evenimentele contabile nu se sterg';
END;
$$;

CREATE TRIGGER accounting_event_no_delete
    BEFORE DELETE ON accounting_event
    FOR EACH ROW EXECUTE FUNCTION app.accounting_event_no_delete();

GRANT SELECT, INSERT, UPDATE ON accounting_event TO evidenta_app;
REVOKE DELETE ON accounting_event FROM evidenta_app;
