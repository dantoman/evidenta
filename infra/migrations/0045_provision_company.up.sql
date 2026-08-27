-- 0045 — `P-9`: provizionarea unei companii
--
-- Context:     docs/decisions/040-crearea-tenantului-si-a-companiei.md (Acceptat)
--              docs/specs/spec-a-tenancy.md §6.2 — enumerarea cailor privilegiate
--              CLAUDE.md R5, R7, C30
--
-- De ce trebuie sa fie cale privilegiata, masurat pe politica vie:
--
--   company_access USING/WITH CHECK:
--     tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id)
--                                         AND rls.has_company_access(id)
--
-- A treia conditie cere ca accesul sa existe INAINTE de rand. Randul de acces
-- cere compania. Deci rolul aplicatiei nu poate crea prima companie prin nicio
-- succesiune de instructiuni — nu e o restrictie de serviciu, e o imposibilitate
-- a politicii. De asta ADR-040 o scoate pe o cale proprie.
--
-- Scopul ingust, ca la celelalte opt: creeaza o companie in tenantul dat, acorda
-- creatorului acces cu rolul pe care il are DEJA din membership, si propaga
-- accesele de engagement. Nu creeaza utilizatori, nu acorda permisiuni in afara
-- companiei noi, nu atinge companii existente (ADR-040 §2.2).
--
-- `granted_via = 'membership'` si `engagement_id IS NULL`: perechea e impusa de
-- `company_access_engagement_consistency`, deci nu e alegere de stil.

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

    -- Aceeasi conditie de siguranta ca la propagarea accesului: fara ea, oricine
    -- ar putea crea companii intr-un tenant strain cunoscand un uuid.
    IF NOT rls.has_tenant_access(p_tenant_id) THEN
        RAISE EXCEPTION 'evidenta: fara drept asupra tenantului %', p_tenant_id
            USING ERRCODE = '42501';
    END IF;

    -- Rolul nu e ales aici si nu e inventat: e cel pe care utilizatorul il are in
    -- tenant. O functie privilegiata care si-ar alege rolul ar fi o cale de
    -- escaladare, nu o cale de provizionare.
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

    -- In aceeasi tranzactie, ADR-040 §2.1: altfel un engagement cu
    -- `covers_all_companies` ar acoperi exact companiile existente la semnare.
    PERFORM rls.provision_engagement_company_access(v_company);

    RETURN v_company;
END
$function$;

RESET ROLE;

-- Granturile: exact ca la celelalte cai privilegiate. Rolul aplicatiei primeste
-- EXECUTE, niciodata apartenenta la `evidenta_rls` (R5).
REVOKE ALL ON FUNCTION rls.provision_company(uuid, text, text, text, date, smallint) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION rls.provision_company(uuid, text, text, text, date, smallint) TO evidenta_app;

-- Ce ii trebuie definitorului ca sa poata face ce face, si nimic peste.
GRANT INSERT ON company TO evidenta_rls;
GRANT SELECT ON membership TO evidenta_rls;
