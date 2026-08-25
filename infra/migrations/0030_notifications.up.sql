-- Notificari in-app si e-mail — Spec A §5.2, sarcina F0.6.5, conflictul X-9.
--
-- Doua lucruri se decid aici, si amandoua in SQL, nu in Python.
--
-- 1. NOTIFICARILE SUNT PERSONALE. Politica ingusteaza la destinatar, nu doar la
--    tenant. Un utilizator al firmei cu engagement viu ajunge la datele
--    clientului — pentru asta exista engagementul — dar notificarile
--    administratorului clientului nu fac parte din ele.
--
-- 2. EXPEDIEREA CATRE ALTCINEVA E CALE PRIVILEGIATA. Serviciul care notifica
--    ruleaza sub contextul celui care actioneaza, iar politica de INSERT cere
--    `recipient_user_id = app.current_user_id()`. Deci a notifica pe altcineva
--    trece printr-o functie care VERIFICA ce nu poate verifica apelantul: ca
--    destinatarul chiar are acces la tenantul respectiv. Judecata sta in SQL
--    tocmai ca apelantul sa n-o poata uita.

-- --- notification ------------------------------------------------------------

ALTER TABLE notification ALTER COLUMN type_key TYPE text COLLATE "C";

ALTER TABLE notification ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification FORCE  ROW LEVEL SECURITY;

CREATE POLICY notification_own ON notification
    FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id)
                AND recipient_user_id = app.current_user_id())
    WITH CHECK (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id)
                AND recipient_user_id = app.current_user_id());

-- --- notification_delivery ---------------------------------------------------
--
-- Urmeaza randul parinte prin EXISTS, care e el insusi protejat. Nu se
-- denormalizeaza destinatarul aici: o a doua copie a conditiei de acces poate
-- diverge de prima, iar divergenta se vede ca o scurgere, nu ca o eroare.

ALTER TABLE notification_delivery ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_delivery FORCE  ROW LEVEL SECURITY;

CREATE POLICY notification_delivery_own ON notification_delivery
    FOR ALL TO evidenta_app
    USING (tenant_id = app.current_tenant_id()
           AND EXISTS (SELECT 1 FROM notification n
                        WHERE n.id = notification_delivery.notification_id))
    WITH CHECK (tenant_id = app.current_tenant_id()
           AND EXISTS (SELECT 1 FROM notification n
                        WHERE n.id = notification_delivery.notification_id));

-- --- Calea privilegiata: notificarea altui utilizator -------------------------
--
-- In schema `rls`, nu in `app`: functia se detine de `evidenta_rls`, iar
-- `evidenta_rls` nu are CREATE pe `app` — prin proiectare (R5). `search_path`
-- fixat in definitie; fara el, o functie SECURITY DEFINER e vector de escaladare.

SET LOCAL ROLE evidenta_rls;

CREATE OR REPLACE FUNCTION rls.create_notification(
    p_tenant_id    uuid,
    p_recipient_id uuid,
    p_type_key     text,
    p_params       jsonb,
    p_company_id   uuid
) RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_id uuid := gen_random_uuid();
BEGIN
    -- Conditia pentru care exista functia. Fara ea, oricine ar putea trimite
    -- text arbitrar oricarui utilizator din instalare, iar destinatarul l-ar
    -- vedea intr-o casuta care poarta numele produsului.
    IF NOT EXISTS (
        SELECT 1 FROM membership m
         WHERE m.user_id = p_recipient_id
           AND m.tenant_id = p_tenant_id
           AND m.status = 'active'
    ) THEN
        RAISE EXCEPTION 'notifications.recipient_has_no_access'
            USING HINT = 'destinatarul nu are acces la acest tenant';
    END IF;

    -- Cel care notifica trebuie sa fie el insusi in tenantul respectiv.
    -- Contextul e fail-closed, deci absenta lui ridica aici, nu mai tarziu.
    -- Cel care notifica trebuie sa aiba el insusi acces la tenantul notificat.
    --
    -- Prin `rls.has_tenant_access`, nu prin `app.current_tenant_id() = p_tenant_id`.
    -- A doua varianta compara doua lucruri pe care le controleaza acelasi
    -- server de aplicatie: GUC-ul si argumentul. Predicatul verifica un FAPT
    -- DE BAZA DE DATE — apartenenta sau engagementul viu — si e chiar cel pe
    -- care il foloseste orice politica, deci nu poate diverge de ele.
    --
    -- Contextul e fail-closed: fara el, predicatul ridica aici, nu mai tarziu.
    IF NOT rls.has_tenant_access(p_tenant_id) THEN
        RAISE EXCEPTION 'notifications.no_access_to_tenant'
            USING HINT = 'cel care notifica nu are acces la tenantul notificat';
    END IF;

    INSERT INTO notification
        (id, tenant_id, recipient_user_id, type_key, params, company_id, created_at)
    VALUES (v_id, p_tenant_id, p_recipient_id, p_type_key,
            COALESCE(p_params, '{}'::jsonb), p_company_id, now());

    RETURN v_id;
END;
$$;

-- Fan-out catre toti membrii activi ai tenantului.
--
-- Lista destinatarilor se calculeaza AICI, nu in Python, si nu din comoditate:
-- `membership` apartine modulului `identity`, iar un serviciu care importa
-- modelele altui modul este exact ce interzice `D6`. In SQL, cautarea sta langa
-- judecata de acces care oricum trebuia facuta, si costa o singura interogare.
CREATE OR REPLACE FUNCTION rls.notify_tenant_members(
    p_tenant_id  uuid,
    p_type_key   text,
    p_params     jsonb,
    p_company_id uuid
) RETURNS SETOF uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    IF NOT rls.has_tenant_access(p_tenant_id) THEN
        RAISE EXCEPTION 'notifications.no_access_to_tenant';
    END IF;

    RETURN QUERY
    INSERT INTO notification
        (id, tenant_id, recipient_user_id, type_key, params, company_id, created_at)
    SELECT gen_random_uuid(), p_tenant_id, m.user_id, p_type_key,
           COALESCE(p_params, '{}'::jsonb), p_company_id, now()
      FROM membership m
     WHERE m.tenant_id = p_tenant_id
       AND m.status = 'active'
    RETURNING id;
END;
$$;

CREATE OR REPLACE FUNCTION rls.create_notification_delivery(
    p_tenant_id       uuid,
    p_notification_id uuid,
    p_channel         text,
    p_status          text
) RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_id uuid := gen_random_uuid();
BEGIN
    IF NOT rls.has_tenant_access(p_tenant_id) THEN
        RAISE EXCEPTION 'notifications.no_access_to_tenant';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM notification n
         WHERE n.id = p_notification_id AND n.tenant_id = p_tenant_id
    ) THEN
        RAISE EXCEPTION 'notifications.unknown_notification';
    END IF;

    INSERT INTO notification_delivery
        (id, tenant_id, notification_id, channel, status, attempts,
         sent_at, created_at, updated_at)
    VALUES (v_id, p_tenant_id, p_notification_id, p_channel, p_status, 0,
            CASE WHEN p_status = 'sent' THEN now() ELSE NULL END, now(), now());

    RETURN v_id;
END;
$$;

RESET ROLE;

-- `evidenta_rls` are BYPASSRLS, dar nu are privilegii pe tabele: atributul si
-- dreptul sunt lucruri diferite in PostgreSQL.
GRANT SELECT, INSERT ON notification           TO evidenta_rls;
GRANT SELECT, INSERT ON notification_delivery  TO evidenta_rls;
GRANT SELECT          ON membership            TO evidenta_rls;

GRANT EXECUTE ON FUNCTION rls.create_notification(uuid, uuid, text, jsonb, uuid)
    TO evidenta_app;
GRANT EXECUTE ON FUNCTION rls.notify_tenant_members(uuid, text, jsonb, uuid)
    TO evidenta_app;
GRANT EXECUTE ON FUNCTION rls.create_notification_delivery(uuid, uuid, text, text)
    TO evidenta_app;
