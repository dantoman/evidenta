-- Inversul lui 0067_invariant_domain.up.sql. Tabela e stearsa de migrarea Django.

REVOKE SELECT ON calculation_invariant_domain FROM evidenta_rls;
REVOKE SELECT ON calculation_invariant_domain FROM evidenta_app;

DROP POLICY IF EXISTS calculation_invariant_domain_write ON calculation_invariant_domain;
DROP POLICY IF EXISTS calculation_invariant_domain_read  ON calculation_invariant_domain;

ALTER TABLE calculation_invariant_domain NO FORCE ROW LEVEL SECURITY;
ALTER TABLE calculation_invariant_domain DISABLE  ROW LEVEL SECURITY;
