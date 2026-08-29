-- 0060 — scrierea datelor de referinta trece sub `evidenta_refdata` (OD-67, ADR-049)
--
-- Context:     infra/bootstrap/0004_refdata_role.sql — rolul
--              infra/rls/exceptions.toml — `writer_role = "evidenta_refdata"` pe fiecare
--                  tabela de mai jos; gardianul de model verifica IZ-78 dupa el
--              infra/migrations/0027_fiscal, 0029_exchange_rate, 0033_coa, 0042_fiscal_confidence,
--                  0044_coa_reference_load — politicile de citire pe care se aseaza asta
--              docs/decisions/049-rolul-de-date-de-referinta.md
--
-- Pana azi, singura cale de scriere in tabelele globale de referinta era conexiunea
-- de owner, si numai pentru planul de conturi (0044). Parametrii fiscali,
-- versiunile de logica, istoricul de increderii si cursurile BNM n-aveau niciuna:
-- mecanismul de precizie/rotunjire era complet si inert (ADR-037 §0, OD-67).
--
-- O singura cale, nu trei: acelasi rol, aceeasi forma de politica, aceeasi
-- inregistrare in `privileged_access_log`, pentru P-3, P-4, P-5 si P-10.
--
-- Fara DELETE nicaieri. Datele de referinta se versioneaza (`valid_from` /
-- `valid_to`), nu se sterg: un parametru citat de o stampila (ADR-047) sau un
-- cont de sablon referit de un `company_account` nu are voie sa dispara.

-- --- parametri fiscali si versiuni de logica (P-4) ---------------------------

CREATE POLICY fiscal_parameter_source_refdata_write ON fiscal_parameter_source
    FOR ALL TO evidenta_refdata USING (true) WITH CHECK (true);
CREATE POLICY fiscal_parameter_refdata_write ON fiscal_parameter
    FOR ALL TO evidenta_refdata USING (true) WITH CHECK (true);
CREATE POLICY fiscal_logic_version_refdata_write ON fiscal_logic_version
    FOR ALL TO evidenta_refdata USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE ON fiscal_parameter_source TO evidenta_refdata;
GRANT SELECT, INSERT, UPDATE ON fiscal_parameter        TO evidenta_refdata;
GRANT SELECT, INSERT, UPDATE ON fiscal_logic_version    TO evidenta_refdata;

-- Istoricul e append-only (0042): citire si inserare, fara politica de UPDATE
-- sau DELETE si fara privilegiu — triggerul ramane a doua bariera, nu prima.
CREATE POLICY fiscal_parameter_confidence_event_refdata_read ON fiscal_parameter_confidence_event
    FOR SELECT TO evidenta_refdata USING (true);
CREATE POLICY fiscal_parameter_confidence_event_refdata_insert ON fiscal_parameter_confidence_event
    FOR INSERT TO evidenta_refdata WITH CHECK (true);
GRANT SELECT, INSERT ON fiscal_parameter_confidence_event TO evidenta_refdata;

-- --- cursul BNM (P-3) ----------------------------------------------------------

CREATE POLICY exchange_rate_refdata_write ON exchange_rate
    FOR ALL TO evidenta_refdata USING (true) WITH CHECK (true);
GRANT SELECT, INSERT, UPDATE ON exchange_rate TO evidenta_refdata;

-- --- registrul de contraparti (P-5) ---------------------------------------------

CREATE POLICY counterparty_registry_refdata_write ON counterparty_registry
    FOR ALL TO evidenta_refdata USING (true) WITH CHECK (true);
GRANT SELECT, INSERT, UPDATE ON counterparty_registry TO evidenta_refdata;

-- --- planul de conturi (P-10) --------------------------------------------------
--
-- 0044 daduse proprietarului o politica FOR ALL pe cele doua tabele, ca
-- incarcatorul sa poata scrie. Se retrage: doua cai de scriere pentru aceeasi
-- tabela e exact „doua mecanisme usor diferite" pe care OD-67 le refuza, iar
-- owner-ul redevine ce e — rolul de migrare, fara nicio politica pe date.

DROP POLICY IF EXISTS coa_template_owner_write         ON coa_template;
DROP POLICY IF EXISTS coa_template_account_owner_write ON coa_template_account;

CREATE POLICY coa_template_refdata_write ON coa_template
    FOR ALL TO evidenta_refdata USING (true) WITH CHECK (true);
CREATE POLICY coa_template_account_refdata_write ON coa_template_account
    FOR ALL TO evidenta_refdata USING (true) WITH CHECK (true);
GRANT SELECT, INSERT, UPDATE ON coa_template, coa_template_account TO evidenta_refdata;
