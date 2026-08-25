-- Inversa lui 0026_readonly_grants.up.sql (ADR-012).
-- Restaureaza privilegiile implicite din 0001_roles.sql.

GRANT INSERT, UPDATE, DELETE ON feature_flag TO evidenta_app;
GRANT INSERT, UPDATE, DELETE ON release_ring TO evidenta_app;
