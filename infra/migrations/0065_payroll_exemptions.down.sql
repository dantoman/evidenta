-- Inversul lui 0065_payroll_exemptions.up.sql. Tabelele sunt sterse de migrarea
-- Django; aici se desface doar ce a adaugat SQL-ul manual.

REVOKE ALL ON exemption_entitlement FROM evidenta_app;
REVOKE ALL ON exemption_application FROM evidenta_app;
REVOKE ALL ON exemption_dependent   FROM evidenta_app;

DROP POLICY IF EXISTS exemption_entitlement_access ON exemption_entitlement;
DROP POLICY IF EXISTS exemption_application_access ON exemption_application;
DROP POLICY IF EXISTS exemption_dependent_access   ON exemption_dependent;

ALTER TABLE exemption_entitlement NO FORCE ROW LEVEL SECURITY;
ALTER TABLE exemption_entitlement DISABLE  ROW LEVEL SECURITY;
ALTER TABLE exemption_application NO FORCE ROW LEVEL SECURITY;
ALTER TABLE exemption_application DISABLE  ROW LEVEL SECURITY;
ALTER TABLE exemption_dependent   NO FORCE ROW LEVEL SECURITY;
ALTER TABLE exemption_dependent   DISABLE  ROW LEVEL SECURITY;

ALTER TABLE exemption_entitlement DROP CONSTRAINT IF EXISTS exemption_entitlement_no_overlap;
ALTER TABLE exemption_application
    DROP CONSTRAINT IF EXISTS exemption_effective_from_is_the_month_after_filing;
