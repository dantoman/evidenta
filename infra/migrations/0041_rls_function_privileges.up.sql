-- =============================================================================
-- Privilegiile functiilor din schema `rls` — reparatie si prevenire
--
-- Autoritate:  docs/decisions/043-privilegiile-functiilor-rls.md
--              CLAUDE.md R5, R7
--              docs/specs/spec-a-tenancy.md §6 (caile privilegiate)
--
-- DEFECTUL, masurat si demonstrat, nu dedus.
--
-- Migrarile care creeaza functii in schema `rls` fac asa:
--
--     SET LOCAL ROLE evidenta_rls;
--     CREATE FUNCTION rls.x() ... SECURITY DEFINER ...;
--     RESET ROLE;
--     REVOKE ALL ON FUNCTION rls.x() FROM PUBLIC;   <-- emis de OWNER
--
-- Ultima linie NU FACE NIMIC. Functia apartine lui `evidenta_rls`, iar un REVOKE
-- emis de cine nu detine obiectul produce un WARNING, nu o eroare. SQL-ul ruleaza,
-- migrarea trece, si privilegiul ramane.
--
-- Rezultatul, citit din `pg_proc.proacl` pe o baza migrata de la zero: 22 din 25
-- de functii pastreaza `=X/evidenta_rls` — adica PUBLIC are EXECUTE. Printre ele,
-- toate cele SECURITY DEFINER de dinaintea contextului: `auth_lookup_user`,
-- `auth_mfa_methods`, `auth_backup_codes`, `auth_spend_backup_code`,
-- `resolve_session`, plus ambele cai privilegiate de acces
-- (`provision_engagement_company_access`, `revoke_engagement_company_access`).
--
-- Demonstrat prin apel, sub rolul aplicatiei, nu doar din catalog:
--   `SELECT * FROM rls.auth_lookup_user('...')`  -> EXECUTA
--   `SELECT rls.provision_engagement_company_access('...')` -> ajunge la linia 9
--   din corpul functiei si e oprita de garda ei interna, nu de privilegiu.
--
-- Apararea era scrisa in migrare, se credea in vigoare, si nu era.
--
-- CE FACE FISIERUL ASTA, in ordine:
--   1. retrage EXECUTE de la PUBLIC pe toate functiile din `rls`, de data asta
--      SUB ROLUL CARE LE DETINE, deci cu efect;
--   2. acorda EXECUTE lui `evidenta_app` pe multimea EXACTA de care are nevoie —
--      derivata prin masuratoare, nu prin judecata: functiile apelate din Python
--      (`grep -r 'rls\.' backend/evidenta/`) reunite cu cele folosite in
--      expresiile politicilor (`pg_policy`), fiindca o politica se evalueaza ca
--      utilizatorul care interogheaza;
--
-- CE NU FACE, si de ce nu: `ALTER DEFAULT PRIVILEGES ... REVOKE EXECUTE ON
-- FUNCTIONS FROM PUBLIC` pare mecanismul evident de prevenire si NU functioneaza
-- aici. Masurat, nu presupus: nici forma cu REVOKE singur, nici cea cu GRANT
-- explicit catre `evidenta_rls` nu schimba ACL-ul unei functii create dupa ele —
-- nici in aceeasi tranzactie, nici intr-una noua, dupa commit. Functia iese cu
-- ACL implicit, adica din nou cu EXECUTE pentru PUBLIC.
--
-- Prevenirea o poarta deci GARDIANUL, nu schema:
-- `backend/tests/schema_guard/test_function_privileges.py` interogheaza catalogul
-- pe o baza construita de la zero la fiecare rulare, deci prima migrare care
-- adauga o functie fara sa-i retraga PUBLIC-ul face suita rosie. E idiomul
-- proiectului oricum — un gardian, nu o conventie.
--
-- CE NU PRIMESTE `evidenta_app`, si de ce nu se rupe nimic: functiile de trigger
-- (`journal_*`, `opening_balance_*`, `sync_module_scope_*`,
-- `refuse_compliance_flag_override`). PostgreSQL verifica EXECUTE pe functia de
-- trigger la CREATE TRIGGER, nu la declansare — deci un trigger continua sa
-- ruleze, iar aplicatia pierde exact ce n-ar trebui sa poata apela direct: opt
-- functii SECURITY DEFINER in plus, scoase din raza ei.
-- =============================================================================

SET LOCAL ROLE evidenta_rls;

-- 1. Retragerea propriu-zisa. Acum de la proprietar, deci cu efect.
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA rls FROM PUBLIC;

-- 2. Multimea masurata, acordata DUPA NUME, cu semnatura rezolvata dinamic.
--
-- Nu pe semnaturi scrise de mana, si motivul e concret: `GRANT ... ON FUNCTION`
-- cere semnatura exacta, iar `OD-63` (ADR-041) tocmai adauga un al doilea
-- parametru — ziua — lui `has_tenant_access` si `has_company_access`. O lista de
-- semnaturi ar fi cazut cu „function does not exist" in ziua aceea, si ar fi
-- cazut la ALTA sesiune, nu la asta.
--
-- Varianta fara lista de argumente (`GRANT ... ON FUNCTION rls.x TO ...`) merge
-- doar cat numele e unic in schema — masurat: la prima supraincarcare cade cu
-- „function name is not unique". Deci nici aceea.
--
-- Numele sunt CONTRACTUL. Sunt aceleasi cu multimea declarata in
-- `backend/tests/schema_guard/test_function_privileges.py`, care verifica ce s-a
-- acordat — iar cele doua vorbesc acum aceeasi limba.

DO $grants$
DECLARE
    v_names text[] := ARRAY[
        -- Predicatele de acces: folosite IN EXPRESIILE POLITICILOR, care se
        -- evalueaza ca utilizatorul care interogheaza. Fara ele, orice interogare
        -- pe orice tabela business esueaza. `R5` le numeste explicit ca singurul
        -- lucru pe care aplicatia il primeste din `rls`.
        'has_tenant_access', 'has_company_access', 'can_see_engagement',
        -- Calea de dinaintea contextului (ADR-026): autentificarea ruleaza cand
        -- nu exista inca niciun tenant setat, deci nu poate trece prin RLS.
        'auth_lookup_user', 'auth_mfa_methods', 'auth_backup_codes',
        'auth_spend_backup_code', 'resolve_session', 'resolve_tenant_by_subdomain',
        -- Caile privilegiate enumerate in spec-a §6.2, apelate din servicii.
        'provision_engagement_company_access', 'revoke_engagement_company_access',
        -- Expedierea notificarilor: ruleaza fara identitate de utilizator, iar
        -- politica pe `notification` ingusteaza la destinatar (OD-50).
        'create_notification', 'create_notification_delivery', 'notify_tenant_members'
    ];
    v_signature text;
    v_found     integer := 0;
BEGIN
    FOR v_signature IN
        SELECT p.oid::regprocedure::text
          FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname = 'rls' AND p.proname = ANY (v_names)
    LOOP
        EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO evidenta_app', v_signature);
        v_found := v_found + 1;
    END LOOP;

    -- Un nume din lista care nu exista in schema inseamna ca lista a ramas in
    -- urma codului. Fail-loud, nu fail-silent: exact clasa de defect pe care
    -- fisierul asta o repara.
    IF v_found < array_length(v_names, 1) THEN
        RAISE EXCEPTION 'lista de granturi nu se potriveste cu schema: % nume declarate, % functii gasite',
            array_length(v_names, 1), v_found;
    END IF;
END
$grants$;

RESET ROLE;
--     REVOKE ALL ON FUNCTION rls.x() FROM PUBLIC;   <-- emis de OWNER
--
-- Ultima linie NU FACE NIMIC. Functia apartine lui `evidenta_rls`, iar un REVOKE
-- emis de cine nu detine obiectul produce un WARNING, nu o eroare. SQL-ul ruleaza,
-- migrarea trece, si privilegiul ramane.
--
-- Rezultatul, citit din `pg_proc.proacl` pe o baza migrata de la zero: 22 din 25
-- de functii pastreaza `=X/evidenta_rls` — adica PUBLIC are EXECUTE. Printre ele,
-- toate cele SECURITY DEFINER de dinaintea contextului: `auth_lookup_user`,
-- `auth_mfa_methods`, `auth_backup_codes`, `auth_spend_backup_code`,
-- `resolve_session`, plus ambele cai privilegiate de acces
-- (`provision_engagement_company_access`, `revoke_engagement_company_access`).
--
-- Demonstrat prin apel, sub rolul aplicatiei, nu doar din catalog:
--   `SELECT * FROM rls.auth_lookup_user('...')`  -> EXECUTA
--   `SELECT rls.provision_engagement_company_access('...')` -> ajunge la linia 9
--   din corpul functiei si e oprita de garda ei interna, nu de privilegiu.
--
-- Apararea era scrisa in migrare, se credea in vigoare, si nu era.
--
-- CE FACE FISIERUL ASTA, in ordine:
--   1. retrage EXECUTE de la PUBLIC pe toate functiile din `rls`, de data asta
--      SUB ROLUL CARE LE DETINE, deci cu efect;
--   2. acorda EXECUTE lui `evidenta_app` pe multimea EXACTA de care are nevoie —
--      derivata prin masuratoare, nu prin judecata: functiile apelate din Python
--      (`grep -r 'rls\.' backend/evidenta/`) reunite cu cele folosite in
--      expresiile politicilor (`pg_policy`), fiindca o politica se evalueaza ca
--      utilizatorul care interogheaza;
--
-- CE NU FACE, si de ce nu: `ALTER DEFAULT PRIVILEGES ... REVOKE EXECUTE ON
-- FUNCTIONS FROM PUBLIC` pare mecanismul evident de prevenire si NU functioneaza
-- aici. Masurat, nu presupus: nici forma cu REVOKE singur, nici cea cu GRANT
-- explicit catre `evidenta_rls` nu schimba ACL-ul unei functii create dupa ele —
-- nici in aceeasi tranzactie, nici intr-una noua, dupa commit. Functia iese cu
-- ACL implicit, adica din nou cu EXECUTE pentru PUBLIC.
--
-- Prevenirea o poarta deci GARDIANUL, nu schema:
-- `backend/tests/schema_guard/test_function_privileges.py` interogheaza catalogul
-- pe o baza construita de la zero la fiecare rulare, deci prima migrare care
-- adauga o functie fara sa-i retraga PUBLIC-ul face suita rosie. E idiomul
-- proiectului oricum — un gardian, nu o conventie.
--
-- CE NU PRIMESTE `evidenta_app`, si de ce nu se rupe nimic: functiile de trigger
-- (`journal_*`, `opening_balance_*`, `sync_module_scope_*`,
-- `refuse_compliance_flag_override`). PostgreSQL verifica EXECUTE pe functia de
-- trigger la CREATE TRIGGER, nu la declansare — deci un trigger continua sa
-- ruleze, iar aplicatia pierde exact ce n-ar trebui sa poata apela direct: opt
-- functii SECURITY DEFINER in plus, scoase din raza ei.
-- =============================================================================

SET LOCAL ROLE evidenta_rls;

-- 1. Retragerea propriu-zisa. Acum de la proprietar, deci cu efect.
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA rls FROM PUBLIC;

-- 2. Multimea masurata. Fiecare rand are un motiv, nu o presupunere.

-- Predicatele de acces: folosite IN EXPRESIILE POLITICILOR, care se evalueaza ca
-- utilizatorul care interogheaza. Fara ele, orice interogare pe orice tabela
-- business esueaza. `R5` le numeste explicit ca singurul lucru pe care aplicatia
-- il primeste din `rls`.
GRANT EXECUTE ON FUNCTION rls.has_tenant_access(p_tenant_id uuid)                     TO evidenta_app;
GRANT EXECUTE ON FUNCTION rls.has_company_access(p_company_id uuid)                   TO evidenta_app;
GRANT EXECUTE ON FUNCTION rls.can_see_engagement(p_client_tenant_id uuid, p_firm_id uuid) TO evidenta_app;

-- Calea de dinaintea contextului (ADR-026): autentificarea ruleaza cand nu exista
-- inca niciun tenant setat, deci nu poate trece prin RLS si trece prin astea.
GRANT EXECUTE ON FUNCTION rls.auth_lookup_user(p_email citext)                        TO evidenta_app;
GRANT EXECUTE ON FUNCTION rls.auth_mfa_methods(p_user_id uuid)                        TO evidenta_app;
GRANT EXECUTE ON FUNCTION rls.auth_backup_codes(p_user_id uuid)                       TO evidenta_app;
GRANT EXECUTE ON FUNCTION rls.auth_spend_backup_code(p_code_id uuid)                  TO evidenta_app;
GRANT EXECUTE ON FUNCTION rls.resolve_session(p_token_hash text)                      TO evidenta_app;
GRANT EXECUTE ON FUNCTION rls.resolve_tenant_by_subdomain(p_subdomain citext)         TO evidenta_app;

-- Caile privilegiate enumerate in spec-a §6.2, apelate din servicii.
GRANT EXECUTE ON FUNCTION rls.provision_engagement_company_access(p_company_id uuid)  TO evidenta_app;
GRANT EXECUTE ON FUNCTION rls.revoke_engagement_company_access(p_engagement_id uuid)  TO evidenta_app;

-- Expedierea notificarilor: ruleaza fara identitate de utilizator, iar politica pe
-- `notification` ingusteaza la destinatar (OD-50).
GRANT EXECUTE ON FUNCTION rls.create_notification(p_tenant_id uuid, p_recipient_id uuid, p_type_key text, p_params jsonb, p_company_id uuid) TO evidenta_app;
GRANT EXECUTE ON FUNCTION rls.create_notification_delivery(p_tenant_id uuid, p_notification_id uuid, p_channel text, p_status text)          TO evidenta_app;
GRANT EXECUTE ON FUNCTION rls.notify_tenant_members(p_tenant_id uuid, p_type_key text, p_params jsonb, p_company_id uuid)                    TO evidenta_app;

RESET ROLE;
