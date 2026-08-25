-- =============================================================================
-- F0.4.1 — audit_event: politica si granturile care il fac append-only
--
-- Autoritate:  docs/specs/spec-a-tenancy.md §1, §9.3
--              CLAUDE.md R21, R22
--              infra/schema/append_only.toml
--
-- APPEND-ONLY NU E O CONVENTIE. Un audit pe care aplicatia il poate modifica nu
-- este audit: cine sterge randul care il incrimineaza sterge si dovada. De aceea
-- rolul de aplicatie primeste INSERT si SELECT, si NU primeste UPDATE sau DELETE.
--
-- Diferenta fata de ledger (R10), care se apara prin trigger: acolo exista o
-- tranzitie legitima de modificat (draft -> posted). Aici nu exista niciuna, deci
-- absenta grantului e suficienta si e mai ieftina decat un trigger pe fiecare
-- scriere din sistem.
-- =============================================================================

ALTER TABLE audit_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_event FORCE  ROW LEVEL SECURITY;

-- Citirea urmeaza dreptul la tenant. Cine anume din interiorul unui tenant are
-- voie sa citeasca auditul este o intrebare de roluri — `DN-08`, deschisa — si se
-- ingusteaza cand se inchide. Largirea ulterioara ar fi fost greseala; ingustarea
-- nu este.
CREATE POLICY audit_event_read ON audit_event
    FOR SELECT TO evidenta_app
    USING (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id));

-- Scrierea: numai in propriul context, si numai in numele actorului curent. Fara
-- a doua conditie, un utilizator ar putea scrie in audit o actiune atribuita
-- altcuiva — adica exact falsificarea impotriva careia exista auditul.
CREATE POLICY audit_event_append ON audit_event
    FOR INSERT TO evidenta_app
    WITH CHECK (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id)
                AND actor_user_id = app.current_user_id());

GRANT SELECT, INSERT ON audit_event TO evidenta_app;
GRANT USAGE, SELECT ON SEQUENCE audit_event_id_seq TO evidenta_app;

-- Explicit, ca sa nu vina prin privilegii implicite viitoare.
REVOKE UPDATE, DELETE ON audit_event FROM evidenta_app;
