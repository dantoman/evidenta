-- =============================================================================
-- F1.1 — Planul de conturi: colatii, nesuprapunere, politici, granturi
--
-- Autoritate:  docs/specs/spec-b-accounting.md §2
--              infra/rls/exceptions.toml — `coa_template` si
--                  `coa_template_account` erau declarate `global_read_only`
--                  DINAINTE de F1.1, cu sursa „V2 §4.3, §7.1". Contractul RLS nu
--                  s-a modificat, deci nu s-a deschis ADR.
--              docs/decisions/029-dimensiuni-analitice.md — vocabularul inchis
--                  al dimensiunilor, impus prin CHECK pe `required_dimensions`
--              CLAUDE.md C34, R1, R2, R15
--
-- Doua niveluri, doua forme de politica:
--
--   coa_template, coa_template_account   globale, citire libera, scriere prin
--                                        cale privilegiata (nescrisa — vezi mai
--                                        jos si `OD-56`)
--   company_chart, company_account       la nivel de companie, sablonul din
--                                        spec-a §2.6
--
-- NIMIC NU SE STERGE. O linie de jurnal refera contul FARA cheie straina (R21,
-- spec-b §1.3), iar registrul e append-only: un cont disparut face istoricul
-- propriu ilizibil. Inchiderea unui cont e `valid_to`, interzicerea postarii e
-- `is_blocked`. De aceea rolul aplicatiei NU primeste DELETE pe cele doua tabele
-- de companie — un refuz doar in serviciu ar fi ocolit de importatorul 1C si de
-- orice migrare de date, adica exact de caile pe care un plan de conturi se
-- strica.
-- =============================================================================

-- --- colatii: codurile de cont sunt CODURI (C34, ADR-015) ---------------------
--
-- Ordinea lor trebuie sa fie pe octeti, nu lingvistica: o balanta ordonata
-- lingvistic dupa codul de cont iese intr-o ordine ciudata a carei cauza se
-- cauta apoi in raport.

ALTER TABLE coa_template         ALTER COLUMN code         TYPE text COLLATE "C";
ALTER TABLE coa_template_account ALTER COLUMN account_code TYPE text COLLATE "C";
ALTER TABLE coa_template_account ALTER COLUMN parent_code  TYPE text COLLATE "C";
ALTER TABLE company_account      ALTER COLUMN account_code TYPE text COLLATE "C";

-- --- o singura versiune publicata in vigoare la un moment dat -----------------
--
-- Doua versiuni `published` care se suprapun in timp inseamna ca intrebarea „ce
-- plan de conturi se instantiaza azi" are doua raspunsuri. Ca la parametrii
-- fiscali (0027), refuzul sta in baza, unde ajunge si incarcatorul care ocoleste
-- serviciul.
--
-- Doar peste randurile `published`: un `draft` pentru anul viitor trebuie sa
-- poata sta alaturi de versiunea in vigoare — asta e chiar felul in care se
-- pregateste o modificare inainte sa intre in vigoare.

CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE coa_template
    ADD CONSTRAINT coa_template_no_overlap
    EXCLUDE USING gist (
        code WITH =,
        daterange(valid_from, valid_to, '[)') WITH &&
    ) WHERE (status = 'published');

-- --- coa_template, coa_template_account: globale, doar citire -----------------
--
-- Aceeasi lege pentru toti, deci fara coloana de tenant — exceptie declarata in
-- `infra/rls/exceptions.toml`, unde statea dinainte de F1.1. Fisierul acela e
-- ADR prin propria lui regula, dar nu s-a modificat aici: F1.1 a construit
-- tabelele pe care contractul le astepta, nu a cerut o exceptie noua.
--
-- Scrierea nu are inca o cale: continutul planului este `OD-23` si nu exista.
-- Cand va exista, incarcatorul are nevoie de o cale privilegiata proprie —
-- enumerarea din spec-a §6.2 nu contine niciuna care sa acopere publicarea unei
-- versiuni de plan de conturi. Inregistrat ca `OD-56`. Pana atunci scrierea e
-- retrasa explicit, nu doar lipsita de politica: `0001_roles.sql` acorda
-- privilegii IMPLICITE de INSERT/UPDATE/DELETE pentru orice tabela creata de
-- owner, deci fara REVOKE singurul lucru care ar opri scrierea ar fi o omisiune
-- (vezi `OD-47`).

ALTER TABLE coa_template ENABLE ROW LEVEL SECURITY;
ALTER TABLE coa_template FORCE  ROW LEVEL SECURITY;
CREATE POLICY coa_template_read ON coa_template
    FOR SELECT TO evidenta_app USING (true);

ALTER TABLE coa_template_account ENABLE ROW LEVEL SECURITY;
ALTER TABLE coa_template_account FORCE  ROW LEVEL SECURITY;
CREATE POLICY coa_template_account_read ON coa_template_account
    FOR SELECT TO evidenta_app USING (true);

-- --- company_chart, company_account: la nivel de companie ---------------------
--
-- Sablonul din spec-a §2.6, in intregime: tenantul din context, accesul la
-- tenant si accesul la companie. `WITH CHECK` identic cu `USING` — fara el un
-- rand s-ar putea scrie cu company_id-ul altcuiva si ar deveni invizibil in
-- chiar momentul commit-ului.

ALTER TABLE company_chart ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_chart FORCE  ROW LEVEL SECURITY;
CREATE POLICY company_chart_access ON company_chart
    FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id)
                AND rls.has_company_access(company_id))
    WITH CHECK (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id)
                AND rls.has_company_access(company_id));

ALTER TABLE company_account ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_account FORCE  ROW LEVEL SECURITY;
CREATE POLICY company_account_access ON company_account
    FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id)
                AND rls.has_company_access(company_id))
    WITH CHECK (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id)
                AND rls.has_company_access(company_id));

-- --- granturi ----------------------------------------------------------------

GRANT SELECT ON coa_template, coa_template_account TO evidenta_app;
REVOKE INSERT, UPDATE, DELETE ON coa_template, coa_template_account FROM evidenta_app;

-- Fara DELETE. Vezi antetul: un cont nu se sterge niciodata, iar aici asta e o
-- lipsa de privilegiu, nu o conventie.
GRANT SELECT, INSERT, UPDATE ON company_chart, company_account TO evidenta_app;
REVOKE DELETE ON company_chart, company_account FROM evidenta_app;
