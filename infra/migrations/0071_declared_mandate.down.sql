-- Inversul lui 0071_declared_mandate.up.sql.
--
-- Tipurile revin la `text` cu colatia implicita a bazei; coloanele insele sunt
-- sterse de migrarea Django, dupa acest fisier.

ALTER TABLE engagement ALTER COLUMN claim_contact_email TYPE text;
ALTER TABLE engagement ALTER COLUMN mandate_ref TYPE text;
