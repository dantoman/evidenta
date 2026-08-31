-- =============================================================================
-- Decontarea: ce document a stins o miscare
--
-- Autoritate:  docs/decisions/087-decontarea-e-o-alocare.md
--              docs/decisions/057-diferentele-realizate-la-decontare.md
--              docs/specs/spec-b-accounting.md §4.2
--              CLAUDE.md R1, R2, C30
--
-- Tabela nu are efect contabil propriu. Incasarea a debitat trezoreria si a
-- creditat creantele deja; alocarea ei pe o factura anume nu misca niciun sold.
-- Ce adauga randul e raspunsul la *care factura* — si soldurile deschise pe care
-- raspunsul acela le face posibile.
--
-- Fara trigger de „continutul urmeaza starea documentului": o decontare NU e
-- continutul unui document, e o legatura intre doua. Randul se scrie dupa ce
-- ambele sunt postate, adica exact cand un trigger de tipul acela ar refuza-o.
-- =============================================================================

ALTER TABLE settlement ENABLE ROW LEVEL SECURITY;
ALTER TABLE settlement FORCE  ROW LEVEL SECURITY;
CREATE POLICY settlement_access ON settlement
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

-- Fara DELETE, si nu din prudenta: o decontare stearsa ar face soldul deschis al
-- unei facturi sa creasca inapoi fara nicio urma ca cineva a decis asta.
-- Corectia e o decontare de sens invers, cand va exista — aceeasi regula ca la
-- registru, din acelasi motiv (`R10`, prin analogie).
GRANT SELECT, INSERT ON settlement TO evidenta_app;
