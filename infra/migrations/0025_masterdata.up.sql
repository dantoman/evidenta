-- =============================================================================
-- F0.7 — Master data: colatii, politici, granturi
--
-- Autoritate:  _input/evidenta-master-plan-v2-amendament-1.md §C.1
--              docs/specs/spec-a-tenancy.md §5, §2.5, §2.6
--              CLAUDE.md C34
-- =============================================================================

-- --- colatii: IDNO, IDNP, coduri, SKU si coduri de bare sunt CODURI (C34) ----
ALTER TABLE counterparty_registry ALTER COLUMN idno TYPE text COLLATE "C";
ALTER TABLE counterparty_registry ALTER COLUMN vat_code TYPE text COLLATE "C";
ALTER TABLE partner ALTER COLUMN idno TYPE text COLLATE "C";
ALTER TABLE partner ALTER COLUMN idnp TYPE text COLLATE "C";
ALTER TABLE partner ALTER COLUMN vat_code TYPE text COLLATE "C";
ALTER TABLE item ALTER COLUMN sku TYPE text COLLATE "C";
ALTER TABLE item ALTER COLUMN barcode TYPE text COLLATE "C";
ALTER TABLE item_category ALTER COLUMN code TYPE text COLLATE "C";
ALTER TABLE unit_of_measure ALTER COLUMN code TYPE text COLLATE "C";
ALTER TABLE company_partner ALTER COLUMN receivable_account_code TYPE text COLLATE "C";
ALTER TABLE company_partner ALTER COLUMN payable_account_code TYPE text COLLATE "C";

-- --- counterparty_registry: global, citire libera ----------------------------
--
-- Fara tenant_id — este una dintre exceptiile enumerate (spec-a §5.4). Scrierea
-- trece prin calea privilegiata P-5: registrul se alimenteaza din surse publice,
-- nu de utilizatori. Un tenant care ar putea scrie in el ar putea schimba ce
-- „spune statul" despre o contraparte, pentru toti ceilalti.

ALTER TABLE counterparty_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE counterparty_registry FORCE  ROW LEVEL SECURITY;

CREATE POLICY counterparty_registry_read ON counterparty_registry
    FOR SELECT TO evidenta_app USING (true);

-- --- partner, unit_of_measure, unit_conversion, item, item_category ----------
--
-- Tenant-scoped: partenerul se introduce o data per tenant si e vizibil
-- companiilor lui (amendament §C.1). Nu se ingusteaza pe companie — asta e chiar
-- diferenta fata de `company_partner`.

ALTER TABLE partner ENABLE ROW LEVEL SECURITY;
ALTER TABLE partner FORCE  ROW LEVEL SECURITY;
CREATE POLICY partner_access ON partner
    FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id))
    WITH CHECK (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id));

ALTER TABLE unit_of_measure ENABLE ROW LEVEL SECURITY;
ALTER TABLE unit_of_measure FORCE  ROW LEVEL SECURITY;
CREATE POLICY unit_of_measure_access ON unit_of_measure
    FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id))
    WITH CHECK (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id));

ALTER TABLE unit_conversion ENABLE ROW LEVEL SECURITY;
ALTER TABLE unit_conversion FORCE  ROW LEVEL SECURITY;
CREATE POLICY unit_conversion_access ON unit_conversion
    FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id))
    WITH CHECK (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id));

ALTER TABLE item_category ENABLE ROW LEVEL SECURITY;
ALTER TABLE item_category FORCE  ROW LEVEL SECURITY;
CREATE POLICY item_category_access ON item_category
    FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id))
    WITH CHECK (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id));

ALTER TABLE item ENABLE ROW LEVEL SECURITY;
ALTER TABLE item FORCE  ROW LEVEL SECURITY;
CREATE POLICY item_access ON item
    FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id))
    WITH CHECK (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id));

-- --- company_partner: company-scoped -----------------------------------------

ALTER TABLE company_partner ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_partner FORCE  ROW LEVEL SECURITY;
CREATE POLICY company_partner_access ON company_partner
    FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id)
                AND rls.has_company_access(company_id))
    WITH CHECK (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id)
                AND rls.has_company_access(company_id));

-- --- granturi ---------------------------------------------------------------

-- Citire, si numai citire. GRANT-ul singur nu ajunge: `0001_roles.sql` acorda
-- privilegii IMPLICITE de INSERT/UPDATE/DELETE pentru fiecare tabela creata de
-- owner, deci o tabela „doar citire" nu e read-only la nivel de grant decat daca
-- i se retrag explicit. Fara REVOKE, singurul lucru care oprea scrierea era
-- absenta unei politici de INSERT — iar o migrare viitoare care adauga una din
-- alt motiv ar fi deschis tacit scrierea pentru toti tenantii.
GRANT SELECT ON counterparty_registry TO evidenta_app;
REVOKE INSERT, UPDATE, DELETE ON counterparty_registry FROM evidenta_app;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON partner, company_partner, unit_of_measure, unit_conversion, item, item_category
    TO evidenta_app;
