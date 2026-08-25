-- Inversul lui 0031_attachments.up.sql. Tabela e stearsa de migrarea Django;
-- aici se desface doar ce a adaugat SQL-ul manual.

DROP POLICY IF EXISTS attachment_metadata_access ON attachment_metadata;

ALTER TABLE attachment_metadata NO FORCE ROW LEVEL SECURITY;
ALTER TABLE attachment_metadata DISABLE  ROW LEVEL SECURITY;
