-- =============================================================================
-- F0.3.3 — Firm, Engagement, scope-uri: colații, politici, granturi
--
-- Autoritate:  docs/specs/spec-a-tenancy.md §1.3, §1.4, §2.7, §4
--              docs/decisions/003-rls-tenancy-tables.md
--
-- Din acest punct se închide A DOUA cale de acces: firmă cu engagement viu
-- asupra tenantului client. Prima (membru) a venit la F0.3.2.
-- =============================================================================

-- --- colații: IDNO este cod, nu denumire (C34) ------------------------------
ALTER TABLE firm ALTER COLUMN idno TYPE text COLLATE "C";

-- --- firm: policy_shape = firm_parties --------------------------------------
--
-- Vizibilă ambelor părți: membrilor tenantului propriu al firmei, și tenanților
-- clienți care au un engagement viu cu ea. Al doilea nu e curtoazie — clientul
-- trebuie să poată răspunde la „cine îmi ține contabilitatea".
--
-- Nu se leagă de app.current_tenant_id(): `firm` nu are tenant_id, iar legarea ar
-- însemna că firma nu-și vede propriul rând decât în contextul tenantului ei.

ALTER TABLE firm ENABLE ROW LEVEL SECURITY;
ALTER TABLE firm FORCE  ROW LEVEL SECURITY;

CREATE POLICY firm_parties ON firm
    FOR ALL TO evidenta_app
    USING      (rls.has_tenant_access(tenant_id))
    WITH CHECK (rls.has_tenant_access(tenant_id));

-- --- engagement: policy_shape = engagement_parties --------------------------
--
-- Rândul leagă doi tenanți, deci nu are un „tenant propriu". Predicatul decide
-- pentru ambele părți: membru al tenantului client, sau membru al tenantului
-- firmei titulare.

ALTER TABLE engagement ENABLE ROW LEVEL SECURITY;
ALTER TABLE engagement FORCE  ROW LEVEL SECURITY;

CREATE POLICY engagement_parties ON engagement
    FOR ALL TO evidenta_app
    USING      (rls.can_see_engagement(client_tenant_id, firm_id))
    WITH CHECK (rls.can_see_engagement(client_tenant_id, firm_id));

-- --- scope-urile: urmează engagementul --------------------------------------
--
-- `engagement_company_scope` are client_tenant_id denormalizat tocmai ca politica
-- să decidă fără JOIN pe engagement — un JOIN acolo ar readuce recursiunea pe care
-- ADR-003 a rupt-o.

ALTER TABLE engagement_company_scope ENABLE ROW LEVEL SECURITY;
ALTER TABLE engagement_company_scope FORCE  ROW LEVEL SECURITY;

CREATE POLICY engagement_company_scope_parties ON engagement_company_scope
    FOR ALL TO evidenta_app
    USING      (rls.has_tenant_access(client_tenant_id))
    WITH CHECK (rls.has_tenant_access(client_tenant_id));

-- `engagement_module_scope` nu are coloană de tenant: este atribut pur al
-- engagementului. Politica îl urmează, prin EXISTS pe rândul părinte — care este
-- el însuși protejat, deci nu lărgește nimic.

ALTER TABLE engagement_module_scope ENABLE ROW LEVEL SECURITY;
ALTER TABLE engagement_module_scope FORCE  ROW LEVEL SECURITY;

CREATE POLICY engagement_module_scope_parties ON engagement_module_scope
    FOR ALL TO evidenta_app
    USING (EXISTS (SELECT 1 FROM engagement e
                    WHERE e.id = engagement_module_scope.engagement_id
                      AND rls.can_see_engagement(e.client_tenant_id, e.firm_id)))
    WITH CHECK (EXISTS (SELECT 1 FROM engagement e
                    WHERE e.id = engagement_module_scope.engagement_id
                      AND rls.can_see_engagement(e.client_tenant_id, e.firm_id)));

-- --- granturi ---------------------------------------------------------------

GRANT SELECT, INSERT, UPDATE, DELETE
    ON firm, engagement, engagement_company_scope, engagement_module_scope
    TO evidenta_app;

-- Punctual, nu prin privilegii implicite: rolul de rezolvare are BYPASSRLS, deci
-- fiecare GRANT către el este o decizie. Citește `engagement` și `firm` pentru a
-- doua cale de acces din rls.has_tenant_access și pentru rls.can_see_engagement.
GRANT SELECT ON engagement, firm TO evidenta_rls;
