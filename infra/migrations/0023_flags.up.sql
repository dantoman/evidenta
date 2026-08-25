-- =============================================================================
-- F0.5.2 — Feature flags si release rings: politici, granturi, si R24 in baza
--
-- Autoritate:  docs/specs/spec-a-tenancy.md §10.5
--              CLAUDE.md R23, R24
--
-- `feature_flag` si `release_ring` sunt globale: descriu codul, nu un tenant.
-- Citire libera rolului de aplicatie, scriere numai prin cale privilegiata.
--
-- `tenant_release_ring` si `feature_flag_override` sunt tenant-scoped.
-- =============================================================================

-- `code` este identificator, nu denumire: ordonare pe octeti (C34, ADR-015). Un
-- cod ordonat lingvistic produce liste in ordine ciudata, iar cauza se cauta in
-- raport, nu in definitia coloanei.
ALTER TABLE release_ring ALTER COLUMN code TYPE text COLLATE "C";
ALTER TABLE tenant_release_ring ALTER COLUMN ring_code TYPE text COLLATE "C";

ALTER TABLE feature_flag ENABLE ROW LEVEL SECURITY;
ALTER TABLE feature_flag FORCE  ROW LEVEL SECURITY;
CREATE POLICY feature_flag_read ON feature_flag FOR SELECT TO evidenta_app USING (true);

ALTER TABLE release_ring ENABLE ROW LEVEL SECURITY;
ALTER TABLE release_ring FORCE  ROW LEVEL SECURITY;
CREATE POLICY release_ring_read ON release_ring FOR SELECT TO evidenta_app USING (true);

ALTER TABLE tenant_release_ring ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_release_ring FORCE  ROW LEVEL SECURITY;
CREATE POLICY tenant_release_ring_access ON tenant_release_ring
    FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id))
    WITH CHECK (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id));

ALTER TABLE feature_flag_override ENABLE ROW LEVEL SECURITY;
ALTER TABLE feature_flag_override FORCE  ROW LEVEL SECURITY;
CREATE POLICY feature_flag_override_access ON feature_flag_override
    FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id))
    WITH CHECK (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id));

-- --- R24 in baza, nu intr-un comentariu de review ---------------------------
--
-- „Conformitatea nu este niciodata capability platibila sau dezactivabila."
-- Un override pe un flag de conformitate ar livra o modificare legislativa unei
-- parti din tenanti si nu altora — exact ce interzice invariantul.
--
-- Nu se poate exprima printr-un CHECK: conditia priveste o coloana din ALTA
-- tabela (`feature_flag.is_compliance`). De aceea trigger. Alternativa — verificare
-- in serviciu — ar fi ocolita de primul import sau de prima scriere directa, iar
-- rezultatul ar fi tocmai clientii care nu afla ca legea s-a schimbat.

SET LOCAL ROLE evidenta_rls;

CREATE OR REPLACE FUNCTION rls.refuse_compliance_flag_override()
RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, rls, pg_temp AS $fn$
BEGIN
    IF (SELECT is_compliance FROM feature_flag WHERE key = NEW.flag_key) THEN
        RAISE EXCEPTION
            'evidenta: %  este flag de conformitate si nu se suprascrie per tenant. '
            'Modificarile de conformitate ajung la toti simultan (R24).',
            NEW.flag_key
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END
$fn$;

RESET ROLE;

CREATE TRIGGER feature_flag_override_no_compliance
    BEFORE INSERT OR UPDATE ON feature_flag_override
    FOR EACH ROW EXECUTE FUNCTION rls.refuse_compliance_flag_override();

GRANT SELECT ON feature_flag, release_ring TO evidenta_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON tenant_release_ring, feature_flag_override
    TO evidenta_app;
GRANT SELECT ON feature_flag TO evidenta_rls;
