-- =============================================================================
-- F1.5.3 — Perioada fiscala TVA: entitate distincta de perioada contabila
--
-- Autoritate:  docs/decisions/039-valuta-si-perioade.md §7 (Acceptat)
--              Codul fiscal art. 114 alin. (1) si alin. (2)
--              CLAUDE.md R1, R2, R15, C30, C34
--
-- Art. 114 alin. (1): perioada fiscala privind TVA este luna calendaristica,
-- pentru toti. Nu exista varianta trimestriala — nici pe prag, nici pe categorie.
--
-- Art. 114 alin. (2): la anularea inregistrarii, ULTIMA perioada fiscala incepe
-- in prima zi a lunii in care a avut loc anularea si se termina in ultima zi a
-- lunii in care actul de anulare a intrat in vigoare. Cand cele doua luni difera,
-- o singura perioada fiscala TVA acopera mai multe perioade contabile.
--
-- DE ACEEA E TABELA SEPARATA, si nu o coloana pe `period`. In 99% din luni cele
-- doua coincid, deci un model unit ar arata corect ani la rand — iar cazul de
-- anulare n-ar fi doar incomod de raportat, ci inexprimabil.
--
-- CE NU E AICI, deliberat:
--
--   * NICIO STARE. `period` are `open`/`closed`/`locked` fiindca refuza postari.
--     Perioada TVA nu refuza nimic: e conturul declaratiei, nu o blocare.
--     `DNB-07` — o stare pentru tot, blocari per modul, sau perioade per domeniu
--     — e DESCHISA, iar o coloana `status` aici ar raspunde varianta (C) tacit.
--   * NICIUN TERMEN. Art. 115 pune declaratia la data de 25 a lunii urmatoare,
--     iar o versiune anterioara a aceluiasi articol spunea „ultima zi a lunii".
--     Calendarul de raportare este PARAMETRU FISCAL (`R15`, ADR-039 §7.1), cu
--     `valid_from`/`valid_to` si sursa — nu o constanta scrisa aici.
--   * NICIO LEGATURA cu `period`. In luna in care difera, o cheie straina ar
--     trebui sa arate spre doua randuri.
-- =============================================================================

-- --- o singura perioada fiscala peste o zi data ------------------------------
--
-- Doua perioade fiscale peste aceeasi zi inseamna doua declaratii pentru aceeasi
-- zi. Serviciul verifica si el, ca sa dea un cod stabil in loc de o eroare de
-- integritate — dar garantia sta aici, unde ajung si importatorul, si orice
-- migrare de date.
--
-- Interval inchis la ambele capete: `end_date` ESTE ultima zi a perioadei.
-- Aceeasi conventie ca la `period`, si deliberat ALTA decat fereastra
-- `[valid_from, valid_to)` de pe `company_vat_registration` — tabela vecina cu
-- care aceasta se confunda cel mai usor.

CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE vat_period
    ADD CONSTRAINT vat_period_no_overlap
    EXCLUDE USING gist (
        company_id WITH =,
        daterange(start_date, end_date, '[]') WITH &&
    );

-- --- capetele cad pe marginile lunii -----------------------------------------
--
-- Amandoua alineatele vorbesc in luni intregi: alin. (1) da luna calendaristica,
-- iar alin. (2) — singurul caz neregulat pe care legea il numeste — tot „prima zi
-- a lunii" si „ultima zi a lunii" spune. O perioada care incepe pe 15 nu e o
-- preferinta de produs, e o perioada fiscala pe care articolul n-o descrie.

ALTER TABLE vat_period
    ADD CONSTRAINT vat_period_starts_a_month
    CHECK (start_date = date_trunc('month', start_date)::date);

ALTER TABLE vat_period
    ADD CONSTRAINT vat_period_ends_a_month
    CHECK (end_date = (date_trunc('month', end_date) + INTERVAL '1 month - 1 day')::date);

-- --- doar perioada finala are voie sa depaseasca luna ------------------------
--
-- `monthly` = alin. (1), exact o luna calendaristica. `final` = alin. (2),
-- singura care se poate intinde peste mai multe luni. Impus in baza fiindca
-- exact aici s-ar strecura, printr-un import sau o migrare de date, o „luna" de
-- doua luni pentru o companie oarecare — iar diferenta s-ar vedea in declaratie,
-- nu la scriere.

ALTER TABLE vat_period
    ADD CONSTRAINT vat_period_monthly_is_one_month
    CHECK (
        kind <> 'monthly'
        OR end_date = (date_trunc('month', start_date) + INTERVAL '1 month - 1 day')::date
    );

-- --- perioada finala nu se rescrie in loc ------------------------------------
--
-- Tranzitia permisa este `monthly -> final`, o singura data: luna in care a avut
-- loc anularea se prelungeste pana la sfarsitul lunii in care actul a intrat in
-- vigoare. Inapoi nu se merge, si nici datele unei perioade finale nu se mai
-- misca: acolo s-a depus deja o declaratie, iar mutarea capatului ei ar schimba
-- perioada pe care contribuabilul a declarat-o.
--
-- Ca la `period_locked_is_terminal`: refuzul sta in baza fiindca importatorul
-- 1C, migrarile de date si orice UPDATE direct ocolesc serviciul.

CREATE OR REPLACE FUNCTION vat_period_final_is_terminal() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.kind = 'final'
       AND (NEW.kind <> OLD.kind
            OR NEW.start_date <> OLD.start_date
            OR NEW.end_date <> OLD.end_date) THEN
        RAISE EXCEPTION 'vat period % is the final period of a cancelled VAT '
                        'registration; it is not revised in place',
                        to_char(OLD.start_date, 'YYYY-MM')
            USING ERRCODE = 'raise_exception';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER vat_period_final_is_terminal
    BEFORE UPDATE ON vat_period
    FOR EACH ROW EXECUTE FUNCTION vat_period_final_is_terminal();

-- --- politica: sablonul la nivel de companie (spec-a §2.6, ADR-004) ----------
--
-- `WITH CHECK` identic cu `USING`: fara el un rand s-ar putea scrie cu
-- company_id-ul altcuiva si ar deveni invizibil chiar in momentul commit-ului.
--
-- Patru clauze, ca la `fiscal_year` si `period` din 0035. A patra nu ingusteaza
-- nimic azi — calea de request nu seteaza `app.company_id`, doar decoratorul
-- Celery o face — si e scrisa oricum, fiindca adaugarea ei ulterioara ar fi o
-- migrare peste o tabela citita intre timp de declaratie. Divergenta cu restul
-- tabelelor company-scoped e inregistrata ca `OD-57`; aici se scrie forma din
-- ADR-004, nu se repara restul.

ALTER TABLE vat_period ENABLE ROW LEVEL SECURITY;
ALTER TABLE vat_period FORCE  ROW LEVEL SECURITY;
CREATE POLICY vat_period_access ON vat_period
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
-- Fara DELETE, ca la `period`. `0001_roles.sql` acorda privilegii IMPLICITE
-- pentru orice tabela creata de owner, deci fara REVOKE singurul lucru care ar
-- opri stergerea unei perioade fiscale pe care s-a depus o declaratie ar fi o
-- omisiune (`OD-47`).

GRANT SELECT, INSERT, UPDATE ON vat_period TO evidenta_app;
REVOKE DELETE ON vat_period FROM evidenta_app;
