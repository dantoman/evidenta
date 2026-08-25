-- =============================================================================
-- F0.3.3b — Sincronizarea denormalizarilor din engagement_module_scope
--
-- Autoritate:  docs/decisions/018-engagementuri-multiple.md
--              docs/decisions/019-vocabular-scope.md
--
-- ADR-018 cere ca regula de nesuprapunere — cel mult un engagement viu per tenant
-- revendica un modul — sa fie impusa IN BAZA, nu in serviciu. Motivul e scris
-- acolo: o verificare in servicii e ocolita de primul import in masa sau de prima
-- scriere concurenta, iar rezultatul ar fi doua firme cu acces la aceleasi salarii.
--
-- Indexul unic partial din migrarea Django face impunerea. El poate vedea doar
-- coloane de pe propria tabela, deci `client_tenant_id` si `is_live` sunt
-- denormalizate din engagementul parinte. Fisierul de fata le tine sincronizate.
--
-- De ce nu un simplu trigger de verificare, care ar citi parintele: sub READ
-- COMMITTED, doua tranzactii care insereaza `payroll` pentru doua firme diferite
-- nu se vad una pe alta, ambele trec verificarea si ambele fac commit. Indexul
-- unic este singura forma care tine fara sa serializeze fiecare scriere.
-- =============================================================================

-- Functiile stau in schema `rls`, nu in `app`, din acelasi motiv ca la 0014: o
-- functie SECURITY DEFINER trebuie DETINUTA de rolul sub care vrem sa ruleze, iar
-- schimbarea proprietarului cere CREATE pe schema — pe care evidenta_rls nu il are
-- pe `app`, deliberat. Schema `rls` ii apartine, deci acolo le creeaza direct.
SET LOCAL ROLE evidenta_rls;

CREATE OR REPLACE FUNCTION rls.sync_module_scope_from_engagement()
RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, app, pg_temp AS $fn$
DECLARE
    v_tenant uuid;
    v_status text;
BEGIN
    SELECT client_tenant_id, status INTO v_tenant, v_status
      FROM engagement WHERE id = NEW.engagement_id;

    IF v_tenant IS NULL THEN
        RAISE EXCEPTION 'evidenta: engagement % nu exista', NEW.engagement_id
            USING ERRCODE = '23503';
    END IF;

    NEW.client_tenant_id := v_tenant;
    NEW.is_live := v_status IN ('invited', 'active', 'suspended');
    RETURN NEW;
END
$fn$;



-- La schimbarea starii engagementului: elibereaza sau revendica modulele.
-- Fara asta, un engagement revocat ar continua sa blocheze `payroll` pentru orice
-- alta firma — adica revocarea ar taia accesul dar nu ar elibera relatia, iar
-- clientul nu ar putea numi un contabil nou.

CREATE OR REPLACE FUNCTION rls.sync_module_scope_liveness()
RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, app, pg_temp AS $fn$
BEGIN
    UPDATE engagement_module_scope
       SET is_live = NEW.status IN ('invited', 'active', 'suspended')
     WHERE engagement_id = NEW.id
       AND is_live <> (NEW.status IN ('invited', 'active', 'suspended'));
    RETURN NULL;
END
$fn$;



RESET ROLE;

-- Triggerele se creeaza ca owner: crearea unui trigger cere proprietatea tabelei.
CREATE TRIGGER engagement_module_scope_sync
    BEFORE INSERT OR UPDATE OF engagement_id ON engagement_module_scope
    FOR EACH ROW EXECUTE FUNCTION rls.sync_module_scope_from_engagement();

CREATE TRIGGER engagement_status_scope_sync
    AFTER UPDATE OF status ON engagement
    FOR EACH ROW WHEN (OLD.status IS DISTINCT FROM NEW.status)
    EXECUTE FUNCTION rls.sync_module_scope_liveness();

GRANT SELECT, UPDATE ON engagement_module_scope TO evidenta_rls;
