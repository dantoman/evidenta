-- Inversul lui 0072_provision_company_role.up.sql: corpul din `0045`, verbatim.
--
-- Se restaureaza rolul de membership, adica defectul descris in fisierul forward.
-- Asta e ce inseamna o derulare inapoi onesta: intoarce sistemul in starea in
-- care era, nu intr-una mai buna pe care istoria n-a avut-o niciodata.

SET LOCAL ROLE evidenta_rls;

CREATE OR REPLACE FUNCTION rls.provision_company(
    p_tenant_id             uuid,
    p_idno                  text,
    p_legal_name            text,
    p_currency              text,
    p_accounting_start      date,
    p_fiscal_year_start_month smallint
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, app, rls, pg_temp
AS $function$
DECLARE
    v_user    uuid := app.current_user_id();
    v_role    uuid;
    v_company uuid := gen_random_uuid();
BEGIN
    IF v_user IS NULL THEN
        RAISE EXCEPTION 'evidenta: fara utilizator in context'
            USING ERRCODE = '42501';
    END IF;

    IF NOT rls.has_tenant_access(p_tenant_id) THEN
        RAISE EXCEPTION 'evidenta: fara drept asupra tenantului %', p_tenant_id
            USING ERRCODE = '42501';
    END IF;

    SELECT m.role_id INTO v_role
      FROM membership m
     WHERE m.tenant_id  = p_tenant_id
       AND m.user_id    = v_user
       AND m.status     = 'active'
       AND m.removed_at IS NULL;

    IF v_role IS NULL THEN
        RAISE EXCEPTION 'evidenta: utilizatorul % nu e membru activ al tenantului %', v_user, p_tenant_id
            USING ERRCODE = '42501';
    END IF;

    IF EXISTS (SELECT 1 FROM company c WHERE c.tenant_id = p_tenant_id AND c.idno = p_idno) THEN
        RAISE EXCEPTION 'evidenta: IDNO % exista deja in acest tenant', p_idno
            USING ERRCODE = '23505';
    END IF;

    INSERT INTO company (
        id, tenant_id, idno, legal_name, functional_currency,
        fiscal_year_start_month, accounting_start_date, status, created_at, updated_at
    )
    VALUES (
        v_company, p_tenant_id, p_idno, p_legal_name, p_currency,
        p_fiscal_year_start_month, p_accounting_start, 'active', now(), now()
    );

    INSERT INTO company_access (
        id, tenant_id, company_id, user_id, role_id, granted_via, engagement_id,
        valid_from, granted_by_user_id, created_at, updated_at
    )
    VALUES (
        gen_random_uuid(), p_tenant_id, v_company, v_user, v_role, 'membership', NULL,
        current_date, v_user, now(), now()
    );

    PERFORM rls.provision_engagement_company_access(v_company);

    RETURN v_company;
END
$function$;

RESET ROLE;
