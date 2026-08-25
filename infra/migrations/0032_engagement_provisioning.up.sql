-- =============================================================================
-- F0.2.4 — Provizionarea accesului pe companie derivat dintr-un engagement
--
-- Autoritate:  docs/specs/spec-a-tenancy.md §8.3 (IZ-25…IZ-27), §4.3
--              docs/decisions/003-rls-tenancy-tables.md
--
-- Oglinda lui `rls.revoke_engagement_company_access` din `0014`. Aceea stinge
-- accesele derivate cand relatia se termina; aceasta le intinde asupra unei
-- companii aparute dupa ce relatia a inceput.
--
-- De ce e nevoie de ea: `covers_all_companies` era scris de serviciul de ciclu de
-- viata si citit de NIMIC — zero aparitii in tot `infra/`. Un engagement declarat
-- ca acoperind toate companiile acoperea, in fapt, exact companiile pentru care
-- cineva crease un rand `company_access` manual. Coloana promitea o regula pe
-- care nu o impunea nimeni.
--
-- Impunerea sta la provizionare, nu in predicat (decizia proprietarului): `rls
-- .has_company_access` ramane cum e, iar accesul continua sa fie un rand, nu o
-- deductie. Ce se schimba este cine scrie randul.
--
-- Ce NU face, deliberat: nu acorda acces initial. Cine primeste acces la un
-- client cand engagementul e acceptat este `OD-42` — repartizarea interna dintr-o
-- firma — si e deschisa. Functia doar PROPAGA accesele care exista deja: cine
-- serveste acest client vede si compania noua a clientului. Cine nu, nu.
-- =============================================================================

SET LOCAL ROLE evidenta_rls;

CREATE OR REPLACE FUNCTION rls.provision_engagement_company_access(p_company_id uuid)
RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, app, rls, pg_temp AS $fn$
DECLARE
    v_tenant uuid;
    v_count  integer;
BEGIN
    SELECT tenant_id INTO v_tenant FROM company WHERE id = p_company_id;

    IF v_tenant IS NULL THEN
        RAISE EXCEPTION 'evidenta: compania % nu exista', p_company_id
            USING ERRCODE = '42501';
    END IF;

    -- Aceeasi conditie de siguranta ca la revocare, si din acelasi motiv: fara
    -- ea, oricine ar putea intinde accesele unui tenant strain cunoscand un uuid.
    IF NOT rls.has_tenant_access(v_tenant) THEN
        RAISE EXCEPTION 'evidenta: fara drept asupra tenantului %', v_tenant
            USING ERRCODE = '42501';
    END IF;

    INSERT INTO company_access (
        id, tenant_id, company_id, user_id, role_id, granted_via, engagement_id,
        valid_from, granted_by_user_id, created_at, updated_at
    )
    SELECT DISTINCT
           gen_random_uuid(), v_tenant, p_company_id, ca.user_id, ca.role_id,
           'engagement', ca.engagement_id, current_date, ca.granted_by_user_id,
           now(), now()
      FROM company_access ca
      JOIN engagement e ON e.id = ca.engagement_id
     WHERE ca.granted_via         = 'engagement'
       AND ca.revoked_at         IS NULL
       AND ca.company_id         <> p_company_id
       AND e.client_tenant_id     = v_tenant
       AND e.status               = 'active'
       -- Aici se citeste, in sfarsit, coloana: un engagement cu scope pe companii
       -- anume nu se intinde peste o companie care nu exista cand a fost semnat.
       AND e.covers_all_companies
       AND e.valid_from          <= current_date
       AND (e.valid_to IS NULL OR e.valid_to >= current_date)
       AND NOT EXISTS (
           SELECT 1 FROM company_access existing
            WHERE existing.company_id  = p_company_id
              AND existing.user_id     = ca.user_id
              AND existing.granted_via = 'engagement'
              AND existing.revoked_at IS NULL
       );

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END
$fn$;

RESET ROLE;

REVOKE ALL ON FUNCTION rls.provision_engagement_company_access(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION rls.provision_engagement_company_access(uuid) TO evidenta_app;

-- `0014` a dat lui evidenta_rls SELECT si UPDATE pe company_access — destul pentru
-- revocare, nu si pentru a scrie randuri. Functia de mai sus ruleaza sub acel rol.
GRANT INSERT ON company_access TO evidenta_rls;

-- Si SELECT pe `company`, pentru un singur lucru: functia isi rezolva tenantul din
-- compania primita. Fara el esueaza cu „permission denied for table company" —
-- masurat, nu presupus. Grantul ramane cat se poate de ingust: citire, o tabela.
GRANT SELECT ON company TO evidenta_rls;
