-- =============================================================================
-- F1.7.3 — Sabloanele de operatiuni tipice: colatii, identitate, politici, granturi
--
-- Autoritate:  docs/decisions/036-forma-postarii.md §8 (stratul 4, sabloane
--                  LIBERE) si §3 (tabelul straturilor)
--              docs/decisions/029-dimensiuni-analitice.md — vocabularul inchis
--              docs/specs/spec-b-accounting.md §1.5 — nota manuala
--              CLAUDE.md R1, R2, C30, C34, C10
--
-- Un sablon este o SCURTATURA DE INTERFATA catre nota contabila manuala. Nu e a
-- doua cale catre registru si nu e o forma noua de tratament: se desface intr-un
-- payload de `manual.journal_entry` si trece prin acelasi motor. Tabelele de mai
-- jos nu contin nimic contabil — niciun sold, nicio suma postata, nicio data de
-- inregistrare. Contin ce ar tasta un om intr-un formular.
--
-- DE ACEEA NU AU: coloana de data (linia sablonului ia data notei), coloana de
-- valuta (nota in valuta e refuzata azi — `DNB-08`), si nicio expresie de calcul.
-- O suma e fie fixa, fie tastata de om. Fara inmultire nu exista produs, deci
-- nu exista rotunjire — iar regula de rotunjire e chiar decizia deschisa pe care
-- un sablon cu procent ar lua-o tacit, in aval, in registru.
--
-- CE NU E AICI, deliberat:
--
--   * NICIO CHEIE STRAINA CATRE `company_account`. Registrul insusi nu are una
--     (`journal_line.account_id` e uuid gol), iar aici motivul e mai tare: daca
--     un cont poate primi o postare e o intrebare CU DATA in ea, la care motorul
--     raspunde in ziua postarii (invariantul 4). O cheie straina ar fi al doilea
--     raspuns la aceeasi intrebare, dat de alt modul, in alta zi.
--   * NICIO STARE si niciun `version`. Sablonul se desface in momentul folosirii,
--     iar registrul e append-only: o inregistrare deja postata nu se schimba
--     fiindca sablonul ei s-a schimbat. Aceeasi garantie ca la §6.4.
-- =============================================================================

-- --- colatii: numele de input sunt CODURI (C34, ADR-015) ---------------------
--
-- `input_key` e cheia sub care omul isi tasteaza valoarea — identificator, nu
-- cuvant. Ordinea lui trebuie sa fie pe octeti. Eticheta pe care o citeste omul
-- e interfata (stratul 0) si sta in fisier de resurse (C32), nu in coloana asta.

ALTER TABLE operation_template_line      ALTER COLUMN input_key TYPE text COLLATE "C";
ALTER TABLE operation_template_dimension ALTER COLUMN input_key TYPE text COLLATE "C";

-- --- copilul nu poate migra la alta companie ---------------------------------
--
-- Cele trei tabele poarta `company_id` fiindca `R1` cere context de tenant pe
-- fiecare tabela business, iar politica ingusteaza si pe companie. Consecinta:
-- exista o stare inexprimabila in model si perfect exprimabila in tabela — o
-- linie cu `company_id`-ul altei companii decat sablonul ei. Nu e o inconsecventa
-- cosmetica: linia ar fi vizibila sub un context in care sablonul nu e, adica
-- exact gaura pe care politica o inchide.
--
-- Cheia straina compusa o face imposibila. `company_id` implica tenantul (o
-- companie apartine unui singur tenant), deci nu mai e nevoie de o a doua pereche.

ALTER TABLE operation_template
    ADD CONSTRAINT operation_template_identity_unique UNIQUE (id, company_id);

ALTER TABLE operation_template_line
    ADD CONSTRAINT operation_template_line_same_company
    FOREIGN KEY (template_id, company_id)
    REFERENCES operation_template (id, company_id);

ALTER TABLE operation_template_line
    ADD CONSTRAINT operation_template_line_identity_unique UNIQUE (id, company_id);

ALTER TABLE operation_template_dimension
    ADD CONSTRAINT operation_template_dimension_same_company
    FOREIGN KEY (line_id, company_id)
    REFERENCES operation_template_line (id, company_id);

-- --- politici: sablonul la nivel de companie (spec-a §2.6, ADR-004) ----------
--
-- `WITH CHECK` identic cu `USING`: fara el un rand s-ar putea scrie cu
-- company_id-ul altcuiva si ar deveni invizibil chiar in momentul commit-ului.
--
-- Patru clauze, ca la `period`, `fiscal_year` si `vat_period`. A patra nu
-- ingusteaza nimic azi — calea de request nu seteaza `app.company_id` — si e
-- scrisa oricum, fiindca adaugarea ei ulterioara ar fi o migrare peste o tabela
-- citita intre timp. Divergenta cu restul tabelelor company-scoped e inregistrata
-- ca `OD-57`; aici se scrie forma din ADR-004, nu se repara restul.

ALTER TABLE operation_template ENABLE ROW LEVEL SECURITY;
ALTER TABLE operation_template FORCE  ROW LEVEL SECURITY;
CREATE POLICY operation_template_access ON operation_template
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

ALTER TABLE operation_template_line ENABLE ROW LEVEL SECURITY;
ALTER TABLE operation_template_line FORCE  ROW LEVEL SECURITY;
CREATE POLICY operation_template_line_access ON operation_template_line
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

ALTER TABLE operation_template_dimension ENABLE ROW LEVEL SECURITY;
ALTER TABLE operation_template_dimension FORCE  ROW LEVEL SECURITY;
CREATE POLICY operation_template_dimension_access ON operation_template_dimension
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

-- --- granturi ----------------------------------------------------------------
--
-- Aici DELETE se acorda pe copii si se retrage pe parinte, iar asimetria e
-- intentionata. Editarea unui sablon inseamna „liniile sunt cele pe care le spui
-- acum" — se sterg si se rescriu, si nu se pierde nimic: nicio inregistrare
-- postata nu le refera. Sablonul insusi nu se sterge, ci se retrage
-- (`is_active = false`), fiindca un sablon disparut ia cu el raspunsul la
-- „ce facea scurtatura pe care toata lumea a folosit-o anul trecut".
--
-- `0001_roles.sql` acorda privilegii IMPLICITE pentru orice tabela creata de
-- owner, deci fara REVOKE stergerea parintelui ar fi posibila din omisiune
-- (`OD-47`), nu din decizie.

GRANT SELECT, INSERT, UPDATE         ON operation_template            TO evidenta_app;
REVOKE DELETE                        ON operation_template          FROM evidenta_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON operation_template_line       TO evidenta_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON operation_template_dimension  TO evidenta_app;
