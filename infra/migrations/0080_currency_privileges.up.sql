-- 0080 — the revaluation tables and `settlement` are written once and read forever.
--
-- 0079 granted `SELECT, INSERT` and said "never edited or deleted" — but the
-- bootstrap's default privileges already hand every new table `UPDATE, DELETE`
-- to `evidenta_app`, and a GRANT only adds. Measured on the running database by
-- the schema reviewer (2026-09-03): the application role could rewrite a posted
-- revaluation. Same gap on `settlement` (0074). The fix is the pattern of
-- 0018_audit and 0024_documents: REVOKE after the GRANT. New file, not an edit
-- of 0074 or 0079 (C31).
--
-- Also `settlement.currency`: a code column, so `COLLATE "C"` (C34), like
-- `exchange_rate.currency` and `revaluation_item.currency`.

REVOKE UPDATE, DELETE ON revaluation FROM evidenta_app;
REVOKE UPDATE, DELETE ON revaluation_item FROM evidenta_app;
REVOKE UPDATE, DELETE ON settlement FROM evidenta_app;

ALTER TABLE settlement ALTER COLUMN currency TYPE varchar(3) COLLATE "C";
