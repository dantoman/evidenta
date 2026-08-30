-- =============================================================================
-- Scutirile la impozitul pe venit — cerere cu data efectiva, nu bifa
--
-- Autoritate:  docs/decisions/065-schema-salarizarii.md §5
--              Codul fiscal art. 33-35, art. 88
--              Regulamentul aprobat prin HG nr. 697 din 22.08.2014, pct. 9, 18, 22
--              CLAUDE.md R18, R25, C34; spec-a §2.6
--
-- Trei tabele company_scoped. Scutirea nu e stare, e ISTORIE: pct. 18 acorda si
-- anuleaza „incepand cu luna urmatoare" celei in care s-a depus sau retras
-- cererea, iar `R18` cere ca recalcularea unei luni trecute sa foloseasca ce era
-- in vigoare ATUNCI. O bifa pe angajat n-ar putea raspunde „ce scutiri avea in
-- martie".
--
-- Nicio suma aici. Cat valoreaza o scutire e parametru fiscal (`R15`), rezolvat
-- dupa data efectiva a perioadei calculate.
-- =============================================================================

-- --- Coduri: ordonare pe octeti (C34) ---------------------------------------

ALTER TABLE exemption_dependent ALTER COLUMN idnp                     TYPE text COLLATE "C";
ALTER TABLE exemption_dependent ALTER COLUMN identity_document_number TYPE text COLLATE "C";
ALTER TABLE exemption_dependent ALTER COLUMN identity_document_type   TYPE text COLLATE "C";
ALTER TABLE exemption_entitlement ALTER COLUMN code                   TYPE text COLLATE "C";

-- --- Pct. 18 ca CHECK, nu ca obicei ------------------------------------------
--
-- Cererea poarta `filed_on` tocmai ca regula sa fie VERIFICABILA. Cu numai data
-- efectiva, „din luna urmatoare" ar trai in aplicatie: un import in masa sau o
-- corectie scrisa direct in tabela o ocolesc, iar recalcularea unei luni trecute
-- n-are faptul stocat din care sa arate ca data a fost derivata corect.

ALTER TABLE exemption_application
    ADD CONSTRAINT exemption_effective_from_is_the_month_after_filing
    CHECK (effective_from = (date_trunc('month', filed_on::timestamp) + interval '1 month')::date);

-- --- Acelasi copil, de doua ori, la acelasi angajat --------------------------
--
-- Interdictia e INTRE randurile aceluiasi angajat, pentru aceeasi persoana
-- intretinuta si acelasi cod, cu perioade care se suprapun. NU intre angajati:
-- numarul de contribuabili care pot folosi scutirea pentru aceeasi persoana nu e
-- limitat prin lege — ambii parinti pot sa o foloseasca pentru acelasi copil —,
-- iar un UNIQUE acolo ar fi inventia noastra si ar refuza un caz permis.
--
-- `COALESCE(dependent_id, uuid_nil)` fiindca `P`, `M` si `Sm` n-au persoana
-- intretinuta, iar NULL <> NULL: fara COALESCE, exact scutirile personale ar
-- scapa de constrangere, adica singurele care nu se pot repeta niciodata.

ALTER TABLE exemption_entitlement
    ADD CONSTRAINT exemption_entitlement_no_overlap
    EXCLUDE USING gist (
        employee_id WITH =,
        code WITH =,
        (COALESCE(dependent_id, '00000000-0000-0000-0000-000000000000'::uuid)) WITH =,
        daterange(valid_from, valid_to, '[)') WITH &&
    );

-- --- Politici: sablonul company_scoped ---------------------------------------

ALTER TABLE exemption_dependent ENABLE ROW LEVEL SECURITY;
ALTER TABLE exemption_dependent FORCE  ROW LEVEL SECURITY;
CREATE POLICY exemption_dependent_access ON exemption_dependent
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

ALTER TABLE exemption_application ENABLE ROW LEVEL SECURITY;
ALTER TABLE exemption_application FORCE  ROW LEVEL SECURITY;
CREATE POLICY exemption_application_access ON exemption_application
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

ALTER TABLE exemption_entitlement ENABLE ROW LEVEL SECURITY;
ALTER TABLE exemption_entitlement FORCE  ROW LEVEL SECURITY;
CREATE POLICY exemption_entitlement_access ON exemption_entitlement
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

-- --- Privilegii --------------------------------------------------------------
--
-- Fara DELETE pe indreptatiri: o scutire nu se sterge, se inchide cu `valid_to`.
-- Stearsa, luna in care a fost acordata s-ar recalcula altfel decat s-a declarat,
-- si nimic n-ar arata de ce. Acelasi motiv pentru care randurile de tip nu se
-- sterg niciodata (ADR-071 §4ter).

GRANT SELECT, INSERT, UPDATE, DELETE ON exemption_dependent   TO evidenta_app;
GRANT SELECT, INSERT                 ON exemption_application TO evidenta_app;
GRANT SELECT, INSERT, UPDATE         ON exemption_entitlement TO evidenta_app;

-- REVOKE explicit, si prima redactie n-a avut-o. `0001_roles.sql` acorda
-- INSERT/UPDATE/DELETE pentru orice tabela creata de owner (OD-47), deci un
-- GRANT care ENUMERA mai putin NU retrage nimic: privilegiul lipsa din lista
-- ramane acolo unde era. Masurat — testul care cerea refuzul stergerii unei
-- indreptatiri a trecut prin ea fara sa clipeasca.
--
-- Dependentele pastreaza DELETE: una tastata gresit se sterge inainte sa fie
-- revendicata, iar dupa aceea cheia straina o tine oricum.

REVOKE UPDATE, DELETE ON exemption_application FROM evidenta_app;
REVOKE DELETE         ON exemption_entitlement FROM evidenta_app;
