-- =============================================================================
-- Reevaluarea elementelor monetare in valuta la data raportarii (A10)
--
-- Autoritate:  docs/decisions/097-valuta-cursul-decontarea-reevaluarea.md
--              docs/specs/spec-b-accounting.md §7.3
--              CLAUDE.md R1, R2, R13, C30
--
-- `revaluation` e documentul-sursa al evenimentului
-- `accounting.revaluation_calculated`: inregistrarea numeste evenimentul,
-- evenimentul numeste randul de aici, iar randul enumera soldurile pe care
-- inregistrarea sta (`revaluation_item`, cu ambele cursuri).
--
-- Fara UPDATE si fara DELETE: o reevaluare care nu mai trebuie sa stea se
-- storneaza prin inregistrarea ei (`R14`), iar cursul pe care l-a scris nu mai
-- duce mai departe cat timp stornoul sta. Randul nu se editeaza, ca registrul.
-- =============================================================================

ALTER TABLE revaluation ENABLE ROW LEVEL SECURITY;
ALTER TABLE revaluation FORCE  ROW LEVEL SECURITY;
CREATE POLICY revaluation_access ON revaluation
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
GRANT SELECT, INSERT ON revaluation TO evidenta_app;

ALTER TABLE revaluation_item ALTER COLUMN currency TYPE varchar(3) COLLATE "C";
ALTER TABLE revaluation_item ALTER COLUMN side     TYPE text       COLLATE "C";

ALTER TABLE revaluation_item ENABLE ROW LEVEL SECURITY;
ALTER TABLE revaluation_item FORCE  ROW LEVEL SECURITY;
CREATE POLICY revaluation_item_access ON revaluation_item
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
GRANT SELECT, INSERT ON revaluation_item TO evidenta_app;
