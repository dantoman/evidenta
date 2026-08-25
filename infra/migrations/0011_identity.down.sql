-- Inversa lui 0011_identity.up.sql (ADR-012: reverse_sql nu e opțional).

REVOKE ALL ON membership FROM evidenta_rls;
REVOKE ALL ON "user", membership FROM evidenta_app;

DROP POLICY IF EXISTS membership_self ON membership;
DROP POLICY IF EXISTS user_self ON "user";

ALTER TABLE membership NO FORCE ROW LEVEL SECURITY;
ALTER TABLE membership DISABLE ROW LEVEL SECURITY;
ALTER TABLE "user" NO FORCE ROW LEVEL SECURITY;
ALTER TABLE "user" DISABLE ROW LEVEL SECURITY;

ALTER TABLE "user" ALTER COLUMN email TYPE text;
