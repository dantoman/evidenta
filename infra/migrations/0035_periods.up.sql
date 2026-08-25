-- =============================================================================
-- F1.5 — Perioade si exercitii: colatie, nesuprapunere, luni intregi, politici
--
-- Autoritate:  docs/decisions/039-valuta-si-perioade.md §6-§8 (Acceptat)
--              docs/specs/spec-b-accounting.md §6
--              CLAUDE.md R1, R2, R12, C34
--
-- Doua tabele, amandoua la nivel de companie:
--
--   fiscal_year   exercitiul, cu start_date/end_date EXPLICITE. Art. 24 alin. (1)
--                 lit. b) din Legea 287/2017 permite exercitiu complet
--                 necalendaristic, iar aceea e situatia normala pentru filiala
--                 unei companii-mama straine — deci „ianuarie-decembrie" nu are
--                 voie sa fie o presupunere nicaieri.
--   period        perioada operationala, STRICT o luna calendaristica.
--
-- NIMIC NU SE STERGE. Rolul aplicatiei nu primeste DELETE: o perioada stearsa
-- ia cu ea urma propriei inchideri („cine a inchis martie, si cand"), iar
-- inregistrarile postate in ea raman si o refera. Ca la planul de conturi
-- (0033), lipsa privilegiului e bariera, nu conventia din serviciu.
--
-- `locked` E TERMINALA, si asta se impune in baza, nu doar in serviciu. Un
-- trigger refuza orice iesire din `locked` — fiindca importatorul 1C, migrarile
-- de date si orice UPDATE direct ocolesc serviciul, iar acelea sunt exact caile
-- pe care un exercitiu depus se redeschide fara ca cineva sa decida asta.
-- =============================================================================

-- --- colatie: codul exercitiului e COD, nu denumire (C34, ADR-015) ------------
--
-- `2026`, `2026/2027`. Se potriveste si se ordoneaza pe octeti; o ordonare
-- lingvistica ar aseza exercitiile intr-o ordine a carei cauza se cauta apoi in
-- raport.

ALTER TABLE fiscal_year ALTER COLUMN code TYPE text COLLATE "C";

-- --- un singur exercitiu, o singura perioada peste o zi data -----------------
--
-- Doua exercitii care se suprapun inseamna doua raspunsuri la „in ce perioada
-- cade postarea din 15 martie". Serviciul verifica si el, ca sa dea un cod
-- stabil in loc de o eroare de integritate — dar garantia sta aici, unde ajung
-- si importatorul, si orice migrare de date.
--
-- Interval inchis la ambele capete: `end_date` ESTE ultima zi a perioadei, nu
-- prima zi din urmatoarea.

CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE fiscal_year
    ADD CONSTRAINT fiscal_year_no_overlap
    EXCLUDE USING gist (
        company_id WITH =,
        daterange(start_date, end_date, '[]') WITH &&
    );

ALTER TABLE period
    ADD CONSTRAINT period_no_overlap
    EXCLUDE USING gist (
        company_id WITH =,
        daterange(start_date, end_date, '[]') WITH &&
    );

-- --- exercitiul: cel mult douasprezece luni ----------------------------------
--
-- Regula care ducea prima perioada pana la 31 decembrie al anului URMATOR statea
-- in Legea 113/2007 si nu mai exista in legea in vigoare (ADR-039 §6). Un
-- exercitiu de treisprezece luni nu e o preferinta, e o perioada de gestiune pe
-- care legea n-o cunoaste.

ALTER TABLE fiscal_year
    ADD CONSTRAINT fiscal_year_at_most_twelve_months
    CHECK (end_date < (start_date + INTERVAL '1 year'));

-- --- perioada: exact o luna calendaristica -----------------------------------
--
-- ADR-039 §7: perioada contabila e luna, pentru toti. Impus in baza fiindca o
-- perioada intinsa peste doua luni face ca „soldul lunii" sa insemne altceva
-- pentru o companie decat pentru restul, iar diferenta se descopera la
-- reconciliere, nu la scriere.

ALTER TABLE period
    ADD CONSTRAINT period_is_one_calendar_month
    CHECK (
        start_date = date_trunc('month', start_date)::date
        AND end_date = (date_trunc('month', start_date) + INTERVAL '1 month - 1 day')::date
    );

-- --- `locked` nu se mai deschide, si baza o stie -----------------------------

CREATE OR REPLACE FUNCTION period_locked_is_terminal() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status = 'locked' AND NEW.status <> 'locked' THEN
        RAISE EXCEPTION 'period % is locked; correction goes through a reversal '
                        'posted in an open period, not through reopening it',
                        to_char(OLD.start_date, 'YYYY-MM')
            USING ERRCODE = 'raise_exception';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER period_locked_is_terminal
    BEFORE UPDATE ON period
    FOR EACH ROW EXECUTE FUNCTION period_locked_is_terminal();

-- --- politici: sablonul la nivel de companie (spec-a §2.6, ADR-004) ----------
--
-- `WITH CHECK` identic cu `USING`: fara el un rand s-ar putea scrie cu
-- company_id-ul altcuiva si ar deveni invizibil chiar in momentul commit-ului.
--
-- PATRU clauze, nu trei. A patra — `app.current_company_id() IS NULL OR
-- company_id = app.current_company_id()` — e sablonul din ADR-004 (Acceptat), si
-- azi nu ingusteaza nimic: calea de request nu seteaza `app.company_id`, doar
-- decoratorul Celery o face. E scrisa oricum, fiindca a adauga o clauza de
-- politica ulterior inseamna o migrare peste o tabela care intre timp e citita
-- de motor, iar costul ei acum e zero: functia intoarce NULL cand GUC-ul
-- lipseste, deci clauza e adevarata.
--
-- Masurat de sesiunea paralela peste `pg_policy`: din sase tabele company-scoped
-- existente, doar `company_vat_registration` o poarta. Divergenta e inregistrata
-- ca decizie deschisa; nu se repara aici, tabela cu tabela — jumatate de
-- ingustare e mai rea decat absenta ei uniforma.

ALTER TABLE fiscal_year ENABLE ROW LEVEL SECURITY;
ALTER TABLE fiscal_year FORCE  ROW LEVEL SECURITY;
CREATE POLICY fiscal_year_access ON fiscal_year
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

ALTER TABLE period ENABLE ROW LEVEL SECURITY;
ALTER TABLE period FORCE  ROW LEVEL SECURITY;
CREATE POLICY period_access ON period
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
-- Fara DELETE. Vezi antetul: `0001_roles.sql` acorda privilegii IMPLICITE pentru
-- orice tabela creata de owner, deci fara REVOKE singurul lucru care ar opri
-- stergerea unei perioade inchise ar fi o omisiune (`OD-47`).

GRANT SELECT, INSERT, UPDATE ON fiscal_year, period TO evidenta_app;
REVOKE DELETE ON fiscal_year, period FROM evidenta_app;
