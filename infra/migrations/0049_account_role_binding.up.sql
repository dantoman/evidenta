-- Ce cont inseamna un rol semantic, pentru o companie, la o data — ADR-036 §5.1.
--
-- Handler-ul cere `TVA_COLECTATA`; nu scrie niciodata `5344`. Un cod de cont
-- intr-un handler e parametru fiscal compilat in cod, iar `R15` numeste asta
-- defect critic.
--
-- Versionata fiindca recalcularea lui martie in iunie trebuie sa ajunga la contul
-- la care a ajuns martie (`R18`). Constrangerea de neintersectare e in baza, nu
-- in serviciu: doua legari active simultan nu sunt o preferinta de rezolvat, sunt
-- doua raspunsuri, iar motorul ar alege unul din intamplare.

ALTER TABLE account_role_binding ALTER COLUMN role TYPE text COLLATE "C";

ALTER TABLE account_role_binding ENABLE ROW LEVEL SECURITY;
ALTER TABLE account_role_binding FORCE  ROW LEVEL SECURITY;

CREATE POLICY account_role_binding_access ON account_role_binding
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

-- Fara DELETE: o legare care a servit o postare explica acea postare. Se inchide
-- cu `valid_to`, nu se sterge — altfel o inregistrare din martie ramane fara
-- raspuns la intrebarea „de ce contul asta".
GRANT SELECT, INSERT, UPDATE ON account_role_binding TO evidenta_app;
REVOKE DELETE ON account_role_binding FROM evidenta_app;
