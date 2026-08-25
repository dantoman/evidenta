-- =============================================================================
-- Fixtura probei de fum RLS (F0.1). Rulează ca evidenta_owner, pe o bază cu
-- 0001–0003 aplicate. Perechea ei: smoke_test.sql, rulat ca evidenta_app.
--
-- Ordinea contează și este ea însăși o constatare: datele se inserează ÎNAINTE de
-- activarea politicilor. Sub FORCE ROW LEVEL SECURITY, cu politici scrise
-- `TO evidenta_app`, nici rolul de migrare nu are politică aplicabilă — deci nu
-- poate insera nimic. Vezi ADR-003, „Verificat empiric", punctul 4.
-- =============================================================================
-- Tabele minime de tenancy, doar cât să valideze design-ul din ADR-003.
CREATE TABLE tenant (id uuid PRIMARY KEY, name text);
CREATE TABLE firm (id uuid PRIMARY KEY, tenant_id uuid NOT NULL, name text);
CREATE TABLE membership (id uuid PRIMARY KEY, tenant_id uuid NOT NULL, user_id uuid NOT NULL, status text NOT NULL);
CREATE TABLE company_access (id uuid PRIMARY KEY, tenant_id uuid NOT NULL, company_id uuid NOT NULL,
    user_id uuid NOT NULL, revoked_at timestamptz, valid_from date NOT NULL, valid_to date);
CREATE TABLE engagement (id uuid PRIMARY KEY, firm_id uuid NOT NULL, client_tenant_id uuid NOT NULL,
    status text NOT NULL, valid_from date NOT NULL, valid_to date);
CREATE TABLE partner (id uuid PRIMARY KEY, tenant_id uuid NOT NULL, name text);

-- evidenta_rls citește doar tabelele consultate de predicate
GRANT SELECT ON membership, company_access, engagement, firm TO evidenta_rls;

INSERT INTO tenant VALUES
  ('11111111-1111-1111-1111-111111111111','Tenant A'),
  ('22222222-2222-2222-2222-222222222222','Tenant B'),
  ('33333333-3333-3333-3333-333333333333','Tenant Firma');
INSERT INTO firm VALUES ('ffffffff-ffff-ffff-ffff-ffffffffffff','33333333-3333-3333-3333-333333333333','Conta Expert');
INSERT INTO membership VALUES
  ('aa000000-0000-0000-0000-000000000001','11111111-1111-1111-1111-111111111111','aaaaaaaa-0000-0000-0000-000000000001','active'),
  ('bb000000-0000-0000-0000-000000000001','22222222-2222-2222-2222-222222222222','bbbbbbbb-0000-0000-0000-000000000001','active'),
  ('ff000000-0000-0000-0000-000000000001','33333333-3333-3333-3333-333333333333','ffffffff-0000-0000-0000-000000000001','active');
INSERT INTO engagement VALUES
  -- activ, nedeterminat: firma tine tenantul B
  ('e0000000-0000-0000-0000-000000000001','ffffffff-ffff-ffff-ffff-ffffffffffff','22222222-2222-2222-2222-222222222222','active','2020-01-01',NULL),
  -- EXPIRAT, dar cu status inca 'active': niciun job nu i-a schimbat starea.
  -- Existenta acestui rand este chiar poanta scenariului IZ-11.
  ('e0000000-0000-0000-0000-000000000002','ffffffff-ffff-ffff-ffff-ffffffffffff','11111111-1111-1111-1111-111111111111','active','2020-01-01','2024-01-01');
INSERT INTO partner VALUES
  ('a0000000-0000-0000-0000-00000000000a','11111111-1111-1111-1111-111111111111','Partener al lui A'),
  ('b0000000-0000-0000-0000-00000000000b','22222222-2222-2222-2222-222222222222','Partener al lui B');

ALTER TABLE membership     ENABLE ROW LEVEL SECURITY; ALTER TABLE membership     FORCE ROW LEVEL SECURITY;
ALTER TABLE company_access ENABLE ROW LEVEL SECURITY; ALTER TABLE company_access FORCE ROW LEVEL SECURITY;
ALTER TABLE engagement     ENABLE ROW LEVEL SECURITY; ALTER TABLE engagement     FORCE ROW LEVEL SECURITY;
ALTER TABLE firm           ENABLE ROW LEVEL SECURITY; ALTER TABLE firm           FORCE ROW LEVEL SECURITY;
ALTER TABLE tenant         ENABLE ROW LEVEL SECURITY; ALTER TABLE tenant         FORCE ROW LEVEL SECURITY;
ALTER TABLE partner        ENABLE ROW LEVEL SECURITY; ALTER TABLE partner        FORCE ROW LEVEL SECURITY;

-- politici neîncrucișate pe tenancy (ADR-003)
CREATE POLICY p_self ON membership     FOR ALL TO evidenta_app USING (user_id = app.current_user_id());
CREATE POLICY p_self ON company_access FOR ALL TO evidenta_app USING (user_id = app.current_user_id());
CREATE POLICY p_eng  ON engagement     FOR ALL TO evidenta_app USING (rls.can_see_engagement(client_tenant_id, firm_id));
CREATE POLICY p_ten  ON tenant         FOR ALL TO evidenta_app USING (rls.has_tenant_access(id));
CREATE POLICY p_firm ON firm           FOR ALL TO evidenta_app USING (rls.has_tenant_access(tenant_id));

-- șablonul business (spec-a §2.5)
CREATE POLICY p_biz ON partner FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id))
    WITH CHECK (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id));

GRANT SELECT, INSERT, UPDATE, DELETE ON tenant, firm, membership, company_access, engagement, partner TO evidenta_app;


