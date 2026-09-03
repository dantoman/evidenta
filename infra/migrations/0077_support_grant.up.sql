-- 0077 — `support_grant`: singura cale a platformei catre datele unui client (ADR-077)
--
-- Context:     docs/decisions/077-grantul-de-suport.md §3–§6
--              docs/decisions/094-sesiunea-de-suport-e-doar-citire-la-nivel-de-tranzactie.md
--              infra/bootstrap/0002_app_context.sql — `app.current_support_grant_id()`
--              infra/bootstrap/0003_access_predicates.sql — ramura a treia a predicatelor
--              infra/migrations/0028_auth_request_path.up.sql — `rls.resolve_session`, inlocuita aici
--
-- TREI MISCARI, TREI SCRIITORI (ADR-077 §2). Cererea e privilegiata: `rls.request_support_access`,
-- SECURITY DEFINER, apelata de un angajat cu rol `support` de pe consola. Aprobarea e OBISNUITA:
-- un membru al clientului, prin politica sablon a tabelei, cu UPDATE — de aceea rolul aplicatiei
-- pastreaza SELECT si UPDATE, dar PIERDE INSERT si DELETE: un client nu poate scrie o cerere in
-- numele platformei ca apoi s-o aprobe, iar istoricul nu se sterge. Accesul e in predicat (0003),
-- marginit de now(), fara niciun job.
--
-- PLAFONUL STA IN BAZA. `expires_at <= approved_at + 72h` e aici, nu in serviciu, fiindca serviciul
-- e cel care se schimba la ora la care se rezolva incidentele. Django nu poate scrie intervalul,
-- deci constrangerea vine din acest fisier, langa politica.
--
-- `rls.resolve_session` se INLOCUIESTE (tipul intors se schimba, deci DROP + CREATE): intoarce si
-- `support_grant_id`, si refuza sa rezolve o sesiune al carei grant a fost revocat sau a expirat.
-- Asa se face „invalidarea sesiunilor in aceeasi tranzactie" din ADR-077 §6 fara o a doua functie:
-- urmatoarea cerere a suportului primeste 401, nu o interfata care esueaza rand cu rand.

ALTER TABLE support_grant
    ADD CONSTRAINT support_grant_window_max
    CHECK (expires_at IS NULL OR expires_at <= approved_at + interval '72 hours');

ALTER TABLE support_grant ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_grant FORCE  ROW LEVEL SECURITY;

CREATE POLICY support_grant_access ON support_grant
    FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id))
    WITH CHECK (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id));

REVOKE INSERT, DELETE ON support_grant FROM evidenta_app;
GRANT  SELECT, UPDATE ON support_grant TO evidenta_app;

-- BYPASSRLS spune „politicile nu se aplica"; GRANT spune „ai voie sa atingi tabela" (0028).
GRANT SELECT, INSERT ON support_grant          TO evidenta_rls;
GRANT INSERT         ON privileged_access_log  TO evidenta_rls;
-- Notificarea cererii se scrie din functie (mai jos); 0030 a dat deja SELECT, INSERT pe
-- `notification` si `notification_delivery` rolului — se repeta idempotent, ca sa se vada aici.
GRANT SELECT, INSERT ON notification, notification_delivery TO evidenta_rls;

SET LOCAL ROLE evidenta_rls;

-- --- P-7: cererea (ADR-077 §5) ------------------------------------------------------------------
-- Verifica in SQL, acolo unde apelantul n-o poate uita: apelant cu rand viu `support`, de pe
-- consola (fara context de tenant); spatiul exista si nu e arhivat; compania, daca e numita, e a
-- spatiului; numarul solicitarii si justificarea sunt nevide; nu exista deja o cerere sau un grant
-- viu al aceluiasi angajat pe acelasi spatiu. Scrie randul NEAPROBAT si randul de jurnal, in
-- aceeasi tranzactie. Cererea nu da acces; aprobarea o scrie clientul.
CREATE OR REPLACE FUNCTION rls.request_support_access(
    p_tenant_id     uuid,
    p_company_id    uuid,
    p_request_ref   text,
    p_justification text
) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = public, app, rls, pg_temp AS $fn$
DECLARE
    v_user   uuid := app.current_user_id();
    v_role   text;
    v_status text;
    v_id     uuid;
BEGIN
    IF NULLIF(current_setting('app.tenant_id', true), '') IS NOT NULL THEN
        RAISE EXCEPTION 'evidenta: cererea de suport se face doar de pe consola'
            USING ERRCODE = '42501';
    END IF;
    SELECT s.staff_role INTO v_role
      FROM platform_staff s
     WHERE s.user_id = v_user AND s.revoked_at IS NULL;
    IF v_role IS DISTINCT FROM 'support' THEN
        RAISE EXCEPTION 'evidenta: doar rolul support cere un grant de suport'
            USING ERRCODE = '42501';
    END IF;
    IF p_request_ref IS NULL OR btrim(p_request_ref) = ''
       OR p_justification IS NULL OR btrim(p_justification) = '' THEN
        RAISE EXCEPTION 'evidenta: cererea de suport cere numarul solicitarii si justificarea'
            USING ERRCODE = '22023';
    END IF;
    SELECT t.status INTO v_status FROM tenant t WHERE t.id = p_tenant_id;
    IF v_status IS NULL OR v_status = 'archived' THEN
        RAISE EXCEPTION 'evidenta: spatiul nu exista sau este arhivat'
            USING ERRCODE = '42501';
    END IF;
    IF p_company_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM company c WHERE c.id = p_company_id AND c.tenant_id = p_tenant_id
    ) THEN
        RAISE EXCEPTION 'evidenta: compania nu este a spatiului numit'
            USING ERRCODE = '42501';
    END IF;
    IF EXISTS (
        SELECT 1 FROM support_grant sg
         WHERE sg.tenant_id = p_tenant_id
           AND sg.requested_by_user_id = v_user
           AND sg.revoked_at IS NULL
           AND (sg.approved_at IS NULL OR sg.expires_at > now())
    ) THEN
        RAISE EXCEPTION 'evidenta: exista deja o cerere sau un grant viu pentru acest spatiu'
            USING ERRCODE = '23505';
    END IF;

    INSERT INTO support_grant
        (id, tenant_id, company_id, requested_by_user_id, request_ref, justification, requested_at)
    VALUES
        (gen_random_uuid(), p_tenant_id, p_company_id, v_user,
         btrim(p_request_ref), btrim(p_justification), now())
    RETURNING id INTO v_id;

    INSERT INTO privileged_access_log
        (occurred_at, path_code, actor_user_id, actor, subject_tenant_id, tenant_count,
         request_id, justification, payload)
    VALUES
        (now(), 'P-7', v_user, 'console:support', p_tenant_id, 1,
         COALESCE(NULLIF(current_setting('app.request_id', true), ''), 'console'),
         btrim(p_justification),
         jsonb_build_object('operation', 'request', 'grant_id', v_id,
                            'request_ref', btrim(p_request_ref), 'company_id', p_company_id));

    -- ADR-077 §6: membrii activi ai clientului afla de cerere pe loc. Scris aici, nu prin
    -- `rls.notify_tenant_members`, fiindca aceea cere `rls.has_tenant_access` — un context de
    -- tenant pe care consola nu-l are prin constructie. Aceleasi coloane, acelasi proprietar
    -- (evidenta_rls), acelasi canal in-app „trimis" ca in dispatch-ul Python (OD-50).
    WITH notice AS (
        INSERT INTO notification
            (id, tenant_id, recipient_user_id, type_key, params, company_id, created_at)
        SELECT gen_random_uuid(), p_tenant_id, m.user_id, 'support.requested',
               jsonb_build_object('request_ref', btrim(p_request_ref)), p_company_id, now()
          FROM membership m
         WHERE m.tenant_id = p_tenant_id
           AND m.status = 'active'
        RETURNING id
    )
    INSERT INTO notification_delivery
        (id, tenant_id, notification_id, channel, status, attempts, sent_at, created_at, updated_at)
    SELECT gen_random_uuid(), p_tenant_id, notice.id, 'in_app', 'sent', 0, now(), now(), now()
      FROM notice;

    RETURN v_id;
END
$fn$;

-- --- autentificarea suportului pe gazda clientului (ADR-077 §6) ---------------------------------
-- Grantul aprobat, viu, al acestui angajat pe acest spatiu — sau NULL. Cere si randul viu de
-- personal: un angajat plecat nu mai intra pe un grant ramas deschis.
CREATE OR REPLACE FUNCTION rls.auth_support_grant(p_user_id uuid, p_tenant_id uuid) RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, rls, pg_temp AS $fn$
    SELECT sg.id
      FROM support_grant sg
      JOIN platform_staff ps ON ps.user_id = sg.requested_by_user_id AND ps.revoked_at IS NULL
     WHERE sg.requested_by_user_id = p_user_id
       AND sg.tenant_id   = p_tenant_id
       AND sg.approved_at IS NOT NULL
       AND sg.revoked_at  IS NULL
       AND sg.expires_at  > now()
     ORDER BY sg.expires_at DESC
     LIMIT 1;
$fn$;

-- --- sesiunea, cu grantul ei --------------------------------------------------------------------
DROP FUNCTION IF EXISTS rls.resolve_session(text);
CREATE FUNCTION rls.resolve_session(p_token_hash text)
RETURNS TABLE (session_id uuid, user_id uuid, tenant_id uuid, actor_firm_id uuid, support_grant_id uuid)
LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = public, rls, pg_temp AS $fn$
    UPDATE user_session s
       SET last_seen_at = now()
     WHERE s.token_hash = p_token_hash
       AND s.revoked_at IS NULL
       AND s.expires_at > now()
       AND (s.support_grant_id IS NULL OR EXISTS (
               SELECT 1 FROM support_grant sg
                WHERE sg.id          = s.support_grant_id
                  AND sg.approved_at IS NOT NULL
                  AND sg.revoked_at  IS NULL
                  AND sg.expires_at  > now()))
    RETURNING s.id, s.user_id, s.tenant_id, s.actor_firm_id, s.support_grant_id;
$fn$;

-- --- pagina consolei (ADR-076 §4.3, forma din 0076) ---------------------------------------------
-- Fara denumirea companiei: e a clientului. Compania numita apare ca identificator.
CREATE OR REPLACE FUNCTION rls.console_support_grants()
RETURNS TABLE (
    id uuid, subdomain text, legal_name text, company_id uuid,
    requested_by_email text, request_ref text, justification text, requested_at timestamptz,
    approved_at timestamptz, expires_at timestamptz, revoked_at timestamptz
)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public, app, rls, pg_temp AS $fn$
BEGIN
    PERFORM rls.console_caller_role();
    RETURN QUERY
    SELECT sg.id, t.subdomain::text, t.legal_name, sg.company_id,
           u.email::text, sg.request_ref, sg.justification, sg.requested_at,
           sg.approved_at, sg.expires_at, sg.revoked_at
      FROM support_grant sg
      JOIN tenant t ON t.id = sg.tenant_id
      JOIN "user" u ON u.id = sg.requested_by_user_id
     ORDER BY sg.requested_at DESC;
END
$fn$;

REVOKE ALL ON FUNCTION rls.request_support_access(uuid, uuid, text, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION rls.auth_support_grant(uuid, uuid)                 FROM PUBLIC;
REVOKE ALL ON FUNCTION rls.resolve_session(text)                          FROM PUBLIC;
REVOKE ALL ON FUNCTION rls.console_support_grants()                       FROM PUBLIC;

GRANT EXECUTE ON FUNCTION rls.request_support_access(uuid, uuid, text, text) TO evidenta_app;
GRANT EXECUTE ON FUNCTION rls.auth_support_grant(uuid, uuid)                 TO evidenta_app;
GRANT EXECUTE ON FUNCTION rls.resolve_session(text)                          TO evidenta_app;
GRANT EXECUTE ON FUNCTION rls.console_support_grants()                       TO evidenta_app;

RESET ROLE;
