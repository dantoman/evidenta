-- =============================================================================
-- F0.6 — Document core, numerotare, document_event: colatii si politici
--
-- Autoritate:  docs/decisions/022-numerotare-sabloane.md
--              docs/specs/spec-a-tenancy.md §2.6
--              CLAUDE.md R21, R22, C34
-- =============================================================================

-- --- colatii: numerele si seriile sunt coduri, nu denumiri (C34) ------------
ALTER TABLE document ALTER COLUMN series TYPE text COLLATE "C";
ALTER TABLE document ALTER COLUMN formatted_number TYPE text COLLATE "C";
ALTER TABLE numbering_template ALTER COLUMN series TYPE text COLLATE "C";

-- --- document: company-scoped ------------------------------------------------
ALTER TABLE document ENABLE ROW LEVEL SECURITY;
ALTER TABLE document FORCE  ROW LEVEL SECURITY;

CREATE POLICY document_access ON document
    FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id)
                AND rls.has_company_access(company_id)
                AND (app.current_company_id() IS NULL
                     OR company_id = app.current_company_id()))
    WITH CHECK (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id)
                AND rls.has_company_access(company_id)
                AND (app.current_company_id() IS NULL
                     OR company_id = app.current_company_id()));

-- --- numerotarea: company-scoped ---------------------------------------------
ALTER TABLE numbering_template ENABLE ROW LEVEL SECURITY;
ALTER TABLE numbering_template FORCE  ROW LEVEL SECURITY;
CREATE POLICY numbering_template_access ON numbering_template
    FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id)
                AND rls.has_company_access(company_id))
    WITH CHECK (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id)
                AND rls.has_company_access(company_id));

-- Contorul e tenant-scoped, nu company-scoped: sablonul poarta compania, iar
-- contorul urmeaza sablonul. O a doua verificare pe companie ar cere un JOIN in
-- politica, pe randul cel mai des blocat din sistem.
ALTER TABLE numbering_counter ENABLE ROW LEVEL SECURITY;
ALTER TABLE numbering_counter FORCE  ROW LEVEL SECURITY;
CREATE POLICY numbering_counter_access ON numbering_counter
    FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id))
    WITH CHECK (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id));

-- --- document_event: append-only ---------------------------------------------
--
-- Ca la audit_event: append-only prin ABSENTA grantului, nu prin trigger. Nu
-- exista tranzitie legitima de modificat pe un rand de istoric.
ALTER TABLE document_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_event FORCE  ROW LEVEL SECURITY;

CREATE POLICY document_event_read ON document_event
    FOR SELECT TO evidenta_app
    USING (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id));

CREATE POLICY document_event_append ON document_event
    FOR INSERT TO evidenta_app
    WITH CHECK (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id)
                AND actor_user_id = app.current_user_id());

-- --- granturi ---------------------------------------------------------------
GRANT SELECT, INSERT, UPDATE, DELETE ON document, numbering_template, numbering_counter
    TO evidenta_app;
GRANT SELECT, INSERT ON document_event TO evidenta_app;
GRANT USAGE, SELECT ON SEQUENCE document_event_id_seq TO evidenta_app;
REVOKE UPDATE, DELETE ON document_event FROM evidenta_app;
