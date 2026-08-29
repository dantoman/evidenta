REVOKE ALL ON coa_template, coa_template_account FROM evidenta_refdata;
DROP POLICY IF EXISTS coa_template_account_refdata_write ON coa_template_account;
DROP POLICY IF EXISTS coa_template_refdata_write         ON coa_template;
-- Inversul readuce exact starea din 0044: politica proprietarului, ca
-- incarcatorul de atunci sa poata rula din nou.
CREATE POLICY coa_template_owner_write ON coa_template
    FOR ALL TO evidenta_owner USING (true) WITH CHECK (true);
CREATE POLICY coa_template_account_owner_write ON coa_template_account
    FOR ALL TO evidenta_owner USING (true) WITH CHECK (true);

REVOKE ALL ON counterparty_registry FROM evidenta_refdata;
DROP POLICY IF EXISTS counterparty_registry_refdata_write ON counterparty_registry;

REVOKE ALL ON exchange_rate FROM evidenta_refdata;
DROP POLICY IF EXISTS exchange_rate_refdata_write ON exchange_rate;

REVOKE ALL ON fiscal_parameter_confidence_event FROM evidenta_refdata;
DROP POLICY IF EXISTS fiscal_parameter_confidence_event_refdata_insert ON fiscal_parameter_confidence_event;
DROP POLICY IF EXISTS fiscal_parameter_confidence_event_refdata_read   ON fiscal_parameter_confidence_event;

REVOKE ALL ON fiscal_logic_version, fiscal_parameter, fiscal_parameter_source FROM evidenta_refdata;
DROP POLICY IF EXISTS fiscal_logic_version_refdata_write    ON fiscal_logic_version;
DROP POLICY IF EXISTS fiscal_parameter_refdata_write        ON fiscal_parameter;
DROP POLICY IF EXISTS fiscal_parameter_source_refdata_write ON fiscal_parameter_source;
