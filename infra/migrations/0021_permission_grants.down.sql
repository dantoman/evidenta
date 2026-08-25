-- Inversa lui 0021_permission_grants.up.sql (ADR-012).
--
-- Readuce privilegiile pe care `ALTER DEFAULT PRIVILEGES` le-ar fi dat oricum la
-- crearea tabelei, ca starea de dinaintea migrării să fie reconstituită exact.

GRANT INSERT, UPDATE, DELETE ON permission TO evidenta_app;
