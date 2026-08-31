-- 0072 — `P-9`: rolul scris in `company_access` e de nivel companie
--
-- Context:     docs/decisions/084-rolul-la-provizionare.md
--              docs/decisions/020-roluri-ca-date.md
--              infra/migrations/0045_provision_company.up.sql (fisierul corectat)
--              CLAUDE.md C31 — fisierul vechi nu se editeaza, corectia e unul nou
--
-- CE ERA GRESIT, MASURAT. `0045` scria in `company_access.role_id` rolul pe care
-- utilizatorul il are din `membership` — adica un rol de nivel TENANT. Dar
-- `role_permission` leaga scopul permisiunii de nivelul rolului, deci pe un rand
-- de acces cu rol de tenant nu se poate tine NICIO cheie de nivel companie.
-- Consecinta: `company.revoke_access` (in catalog de la F0.3.3), `company.edit` si
-- `company.close` (ADR-083) erau de neatins pentru cine crease compania.
--
-- Masurat pe baza de dezvoltare la 2026-08-31: toate cele patru randuri vii
-- purtau `owner` — nivel tenant, sapte permisiuni, niciuna de companie.
--
-- DE CE NU E O ESCALADARE, care e obiectia scrisa in `0045` si care ramane
-- valabila ca principiu: functia nu ALEGE un rol si nu il inventeaza. Scrie rolul
-- de sistem de nivel companie pe care platforma il creeaza ea insasi odata cu
-- tenantul, prin `create_system_roles` — singurul rol de nivel companie pe care
-- produsul il garanteaza. Diferenta fata de „si-ar alege rolul" e ca aici nu
-- exista alegere: e o cautare cu un singur rezultat posibil.
--
-- DACA LIPSESTE, REFUZA. Un tenant fara `company_admin` e un tenant cu
-- provizionarea intrerupta (cazul reparat de `repair_system_roles`). A cadea
-- inapoi pe rolul de membership ar readuce exact defectul, tacut si doar la
-- tenantii stricati — adica acolo unde nimeni nu s-ar uita.

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

    -- Apartenenta ramane conditie: crearea unei companii e actul unui MEMBRU al
    -- tenantului. O firma cu engagement trece de `has_tenant_access` si nu are
    -- membership aici, deci nu creeaza companii in tenantul clientului — asta era
    -- comportamentul lui `0045` si nu se schimba.
    IF NOT EXISTS (
        SELECT 1 FROM membership m
         WHERE m.tenant_id  = p_tenant_id
           AND m.user_id    = v_user
           AND m.status     = 'active'
           AND m.removed_at IS NULL
    ) THEN
        RAISE EXCEPTION 'evidenta: utilizatorul % nu e membru activ al tenantului %', v_user, p_tenant_id
            USING ERRCODE = '42501';
    END IF;

    -- Rolul randului de acces: cel de sistem, de nivel companie. Nu ales, cautat.
    SELECT r.id INTO v_role
      FROM role r
     WHERE r.tenant_id = p_tenant_id
       AND r.key       = 'company_admin'
       AND r.level     = 'company'
       AND r.is_system;

    IF v_role IS NULL THEN
        RAISE EXCEPTION 'evidenta: tenantul % nu are rolul de sistem company_admin; rulati repair_system_roles', p_tenant_id
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

-- Ce ii trebuie definitorului in plus fata de `0045`: sa poata citi rolurile
-- tenantului. Numai SELECT — nu creeaza roluri si nu le modifica.
GRANT SELECT ON role TO evidenta_rls;
