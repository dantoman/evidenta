-- =============================================================================
-- F0.3.1 — Tenant, Company, CompanyVatRegistration: tipuri, colații, politici
--
-- Autoritate:  docs/specs/spec-a-tenancy.md §1.1, §1.2, §2.5
--              docs/decisions/003-rls-tenancy-tables.md  (forma politicilor)
--              docs/decisions/004-context-de-companie.md (company_id îngustează)
--              docs/decisions/015-colatie-icu.md         (C34)
--
-- Ordinea impusă de ADR-012: tabela există deja din migrarea Django care referă
-- acest fișier, apoi ENABLE → FORCE → POLICY → GRANT, în aceeași tranzacție.
-- =============================================================================

-- --- tipuri pe care Django nu le exprimă ------------------------------------

-- Subdomeniul este singura sursă a contextului de tenant (C8). Comparația
-- insensibilă la majuscule se face de tip, nu prin lower() în interogări.
ALTER TABLE tenant ALTER COLUMN subdomain TYPE citext;

ALTER TABLE tenant ADD CONSTRAINT tenant_subdomain_format
    CHECK (subdomain ~ '^[a-z][a-z0-9-]{2,29}$');

-- Coduri, nu denumiri: ordonare pe octeți (C34). Un cod ordonat lingvistic
-- produce rapoarte în ordine ciudată, iar cauza se caută în raport.
ALTER TABLE company ALTER COLUMN idno TYPE text COLLATE "C";
ALTER TABLE company_vat_registration ALTER COLUMN vat_code TYPE text COLLATE "C";

-- O companie nu poate avea două înregistrări TVA suprapuse. În serviciu ar fi o
-- verificare pe care importul în masă o ocolește; aici nu.
ALTER TABLE company_vat_registration
    ADD CONSTRAINT company_vat_registration_no_overlap
    EXCLUDE USING gist (
        company_id WITH =,
        daterange(valid_from, valid_to, '[)') WITH &&
    );

-- --- tenant: policy_shape = tenant_predicate --------------------------------
--
-- Tenant este rădăcina: nu are tenant_id, deci nu se compară cu
-- app.current_tenant_id(). Cine îl vede decid predicatele — membru al lui, sau
-- firmă cu engagement viu asupra lui.

ALTER TABLE tenant ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant FORCE  ROW LEVEL SECURITY;

CREATE POLICY tenant_access ON tenant
    FOR ALL TO evidenta_app
    USING      (rls.has_tenant_access(id))
    WITH CHECK (rls.has_tenant_access(id));

-- --- company: tenant-scoped, plus dreptul pe companie -----------------------
--
-- Două condiții, nu una. `tenant_id = app.current_tenant_id()` leagă rândul de
-- contextul cererii; `rls.has_company_access(id)` decide dacă utilizatorul are
-- voie la ACEASTĂ companie — un membru al tenantului nu are automat acces la
-- toate companiile lui.
--
-- `app.company_id` NU apare aici, deliberat: el îngustează (ADR-004), iar
-- îngustarea aplicată chiar tabelei `company` ar face imposibil comutatorul de
-- companie din interfață — ecranul care listează companiile la care ai acces.

ALTER TABLE company ENABLE ROW LEVEL SECURITY;
ALTER TABLE company FORCE  ROW LEVEL SECURITY;

CREATE POLICY company_access ON company
    FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id)
                AND rls.has_company_access(id))
    WITH CHECK (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id)
                AND rls.has_company_access(id));

-- --- company_vat_registration: company-scoped -------------------------------

ALTER TABLE company_vat_registration ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_vat_registration FORCE  ROW LEVEL SECURITY;

CREATE POLICY company_vat_registration_access ON company_vat_registration
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

-- --- granturi ---------------------------------------------------------------

GRANT SELECT, INSERT, UPDATE, DELETE
    ON tenant, company, company_vat_registration
    TO evidenta_app;
