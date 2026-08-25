-- =============================================================================
-- F0.3.4 — CompanyAccess: politică, granturi, cale de revocare
--
-- Autoritate:  docs/specs/spec-a-tenancy.md §1.7, §4.3
--              docs/decisions/003-rls-tenancy-tables.md
--
-- Din acest punct `company` devine interogabilă: politica ei referea deja
-- rls.has_company_access, iar tabela pe care acesta o citește există abia acum.
-- =============================================================================

-- --- company_access: policy_shape = self_row --------------------------------
--
-- Ca la `membership`, și din același motiv: `rls.has_company_access` citește
-- chiar această tabelă, deci o politică pe ea care ar apela predicatul ar
-- recursa. Rândurile proprii se văd direct.

ALTER TABLE company_access ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_access FORCE  ROW LEVEL SECURITY;

CREATE POLICY company_access_self ON company_access
    FOR ALL TO evidenta_app
    USING      (user_id = app.current_user_id())
    WITH CHECK (user_id = app.current_user_id());

-- --- revocarea în cascadă: cale privilegiată îngustă -------------------------
--
-- Politica de mai sus are o consecință: un administrator NU poate revoca accesul
-- altcuiva prin ORM — rândurile altor utilizatori îi sunt invizibile. Aceasta nu
-- este o scăpare, este forma `self_row` aplicată consecvent; dar revocarea unui
-- engagement TREBUIE să stingă accesele derivate din el, în aceeași tranzacție
-- (spec-a §4.3). Accesul nu poate supraviețui relației care l-a produs.
--
-- Deci: o funcție SECURITY DEFINER, îngustă prin construcție. Nu primește nume de
-- tabele, nu acceptă SQL, nu poate revoca decât accesele derivate dintr-un
-- engagement anume, și doar dacă apelantul are dreptul să vadă acel engagement.
-- Ultima condiție este cea care o face sigură: fără ea, orice utilizator ar putea
-- stinge accesele oricui, cunoscând un uuid.

-- Funcția stă în schema `rls`, nu în `app`, și asta nu e cosmetic: schema `rls`
-- este deținută de evidenta_rls, iar o funcție SECURITY DEFINER trebuie să fie
-- deținută de rolul sub care vrem să ruleze. Creată în `app` — deținută de
-- evidenta_owner — ar fi supusă chiar politicilor pe care trebuie să le ocolească
-- (FORCE ROW LEVEL SECURITY se aplică și proprietarului), deci ar revoca zero
-- rânduri și ar raporta succes.
--
-- Owner-ul o poate crea acolo pentru că este membru al lui evidenta_rls: SET ROLE.
SET LOCAL ROLE evidenta_rls;

CREATE OR REPLACE FUNCTION rls.revoke_engagement_company_access(p_engagement_id uuid)
RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, app, rls, pg_temp AS $fn$
DECLARE
    v_client uuid;
    v_firm   uuid;
    v_count  integer;
BEGIN
    SELECT client_tenant_id, firm_id INTO v_client, v_firm
      FROM engagement WHERE id = p_engagement_id;

    IF v_client IS NULL THEN
        RAISE EXCEPTION 'evidenta: engagement % nu exista', p_engagement_id
            USING ERRCODE = '42501';
    END IF;

    -- Dreptul apelantului se verifică prin acelasi predicat ca politica de pe
    -- `engagement`. Fara asta, functia ar fi o portita, nu o cale.
    IF NOT rls.can_see_engagement(v_client, v_firm) THEN
        RAISE EXCEPTION 'evidenta: fara drept asupra engagementului %', p_engagement_id
            USING ERRCODE = '42501';
    END IF;

    UPDATE company_access
       SET revoked_at = now(), updated_at = now()
     WHERE engagement_id = p_engagement_id
       AND granted_via = 'engagement'
       AND revoked_at IS NULL;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END
$fn$;

RESET ROLE;

REVOKE ALL ON FUNCTION rls.revoke_engagement_company_access(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION rls.revoke_engagement_company_access(uuid) TO evidenta_app;

-- --- granturi ---------------------------------------------------------------

GRANT SELECT, INSERT, UPDATE, DELETE ON company_access TO evidenta_app;

-- Punctual: rolul de rezolvare citește company_access pentru rls.has_company_access.
GRANT SELECT, UPDATE ON company_access TO evidenta_rls;
