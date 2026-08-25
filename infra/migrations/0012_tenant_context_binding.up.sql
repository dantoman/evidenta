-- =============================================================================
-- F0.3.2 — `tenant`: legarea politicii de contextul cererii
--
-- Fișier nou, nu o editare a lui 0010: acela a fost deja aplicat, iar fișierele
-- din infra/migrations/ sunt append-only (ADR-012, regula 2). Corecția este un
-- fișier nou și o migrare nouă — aceeași regulă ca pentru ledger.
--
-- CE SE CORECTEAZĂ
--
-- Politica din 0010 era `USING (rls.has_tenant_access(id))`. Ea răspunde corect la
-- „cine are voie la rândul acesta", dar nu leagă rândul de tenantul cerut. Efectul,
-- măsurat: un utilizator membru al tenantului A, într-o cerere pe contextul
-- tenantului B, primea rândul tenantului A.
--
-- Nu este scurgere între utilizatori — utilizatorul avea oricum drept la A. Este
-- scurgere de CONTEXT: date din afara tenantului cererii apar în rezultatele
-- cererii. Un raport construit în contextul lui B ar culege rândul lui A, exact
-- clasa de defect pentru care ADR-004 a păstrat îngustarea pe companie.
--
-- Forma nouă este identică în principiu cu orice altă tabelă tenant-scoped:
-- întâi legarea de context, apoi dreptul.
--
-- CONSECINȚĂ care necesită confirmare (OD-41): „la ce tenanți aparțin" nu se mai
-- poate răspunde din această tabelă. Este o întrebare cross-tenant prin natura ei,
-- deci locul ei este în read models (INV-10) sau pe o cale privilegiată. Comutatorul
-- de tenant din interfață depinde de răspuns.
-- =============================================================================

DROP POLICY tenant_access ON tenant;

CREATE POLICY tenant_access ON tenant
    FOR ALL TO evidenta_app
    USING      (id = app.current_tenant_id() AND rls.has_tenant_access(id))
    WITH CHECK (id = app.current_tenant_id() AND rls.has_tenant_access(id));
