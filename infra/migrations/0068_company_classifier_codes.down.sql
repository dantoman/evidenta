-- Inversul lui 0068_company_classifier_codes.up.sql.
--
-- Colatia se intoarce la cea implicita a bazei; coloanele insele sunt sterse de
-- migrarea Django.

ALTER TABLE company ALTER COLUMN cuatm_code TYPE text;
ALTER TABLE company ALTER COLUMN caem_code  TYPE text;
