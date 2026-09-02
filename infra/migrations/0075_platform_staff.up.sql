-- 0075 — `platform_staff`: cine e angajat al platformei (ADR-076 §4.1)
--
-- Context:     docs/decisions/076-planul-de-control-al-platformei.md §4.1, §4.2
--              infra/rls/exceptions.toml — `platform_staff`, `policy_shape = "self_row"`,
--                  `writer_role = "evidenta_refdata"`
--              infra/migrations/0021_mfa_sessions.up.sql — forma `self_row` copiata
--              infra/migrations/0060_refdata_write_policies.up.sql — forma scrierii de referinta
--
-- CE ESTE. O lista de persoane, la nivelul lui `user`, fara `tenant_id` — un angajat al
-- platformei nu apartine niciunui tenant. Un rand aici nu deschide nicio politica: nu apare in
-- `rls.has_tenant_access`, nu apare in `rls.has_company_access`. Il citesc usile consolei ca sa
-- afle daca apelantul are voie sa le apeleze, si autentificarea pe gazda `admin.` ca sa afle daca
-- emite o sesiune.
--
-- CITIREA: rand propriu. Rolul aplicatiei vede exact un rand — al utilizatorului din context —
-- ceea ce e tot ce are de aflat consola: „sunt angajat, si cu ce rol". O lista a angajatilor
-- platformei nu e a niciunui tenant si nu se citeste de pe o gazda de tenant; pe consola se va
-- citi printr-o cale privilegiata, cand `admin` primeste ecranul lui (OD-133).
--
-- SCRIEREA: doar `evidenta_refdata`, fara DELETE. „Retragerea e o data, nu o stergere" (ADR-076
-- §4.1): cine a fost angajat si cand face parte din raspunsul la „cine putea rula calea asta", iar
-- un rand sters nu mai raspunde. Rolul aplicatiei nu scrie deloc: privilegiile implicite din
-- 0001_roles.sql se retrag explicit, ca declaratia din `exceptions.toml` si baza sa spuna acelasi
-- lucru (lectia lui 0047).
--
-- R1 — excepția LARGESTE accesul (tabela se scrie la runtime, de oameni), deci a cerut
-- confirmarea proprietarului; e data prin acceptarea ADR-076 si consemnata acolo, nu aici.

ALTER TABLE platform_staff ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_staff FORCE  ROW LEVEL SECURITY;

CREATE POLICY platform_staff_self ON platform_staff
    FOR SELECT TO evidenta_app
    USING (user_id = app.current_user_id());

CREATE POLICY platform_staff_refdata_write ON platform_staff
    FOR ALL TO evidenta_refdata USING (true) WITH CHECK (true);

REVOKE INSERT, UPDATE, DELETE ON platform_staff FROM evidenta_app;
GRANT  SELECT ON platform_staff TO evidenta_app;
GRANT  SELECT, INSERT, UPDATE ON platform_staff TO evidenta_refdata;
