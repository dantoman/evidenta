-- Inversul lui 0070_tenant_identity.up.sql.
--
-- Colatia se intoarce la cea implicita a bazei; coloanele insele sunt sterse de
-- migrarea Django.

ALTER TABLE tenant ALTER COLUMN idno TYPE text;
