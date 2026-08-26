-- Inversul lui 0039_opening_balances.up.sql (ADR-012). Tabelele le sterge
-- migrarea Django; aici se desface doar ce a adaugat SQL-ul manual.

REVOKE ALL ON opening_balance_batch,
              opening_balance_gl,
              opening_balance_receivable,
              opening_balance_payable,
              opening_balance_inventory,
              opening_balance_asset,
              opening_balance_payroll_cumulative
       FROM evidenta_app;
REVOKE ALL ON opening_balance_batch FROM evidenta_rls;

DROP POLICY IF EXISTS opening_balance_payroll_access    ON opening_balance_payroll_cumulative;
DROP POLICY IF EXISTS opening_balance_asset_access      ON opening_balance_asset;
DROP POLICY IF EXISTS opening_balance_inventory_access  ON opening_balance_inventory;
DROP POLICY IF EXISTS opening_balance_payable_access    ON opening_balance_payable;
DROP POLICY IF EXISTS opening_balance_receivable_access ON opening_balance_receivable;
DROP POLICY IF EXISTS opening_balance_gl_access         ON opening_balance_gl;
DROP POLICY IF EXISTS opening_balance_batch_access      ON opening_balance_batch;

ALTER TABLE opening_balance_payroll_cumulative NO FORCE ROW LEVEL SECURITY;
ALTER TABLE opening_balance_payroll_cumulative DISABLE  ROW LEVEL SECURITY;
ALTER TABLE opening_balance_asset      NO FORCE ROW LEVEL SECURITY;
ALTER TABLE opening_balance_asset      DISABLE  ROW LEVEL SECURITY;
ALTER TABLE opening_balance_inventory  NO FORCE ROW LEVEL SECURITY;
ALTER TABLE opening_balance_inventory  DISABLE  ROW LEVEL SECURITY;
ALTER TABLE opening_balance_payable    NO FORCE ROW LEVEL SECURITY;
ALTER TABLE opening_balance_payable    DISABLE  ROW LEVEL SECURITY;
ALTER TABLE opening_balance_receivable NO FORCE ROW LEVEL SECURITY;
ALTER TABLE opening_balance_receivable DISABLE  ROW LEVEL SECURITY;
ALTER TABLE opening_balance_gl         NO FORCE ROW LEVEL SECURITY;
ALTER TABLE opening_balance_gl         DISABLE  ROW LEVEL SECURITY;
ALTER TABLE opening_balance_batch      NO FORCE ROW LEVEL SECURITY;
ALTER TABLE opening_balance_batch      DISABLE  ROW LEVEL SECURITY;

DROP TRIGGER IF EXISTS opening_balance_payroll_frozen    ON opening_balance_payroll_cumulative;
DROP TRIGGER IF EXISTS opening_balance_asset_frozen      ON opening_balance_asset;
DROP TRIGGER IF EXISTS opening_balance_inventory_frozen  ON opening_balance_inventory;
DROP TRIGGER IF EXISTS opening_balance_payable_frozen    ON opening_balance_payable;
DROP TRIGGER IF EXISTS opening_balance_receivable_frozen ON opening_balance_receivable;
DROP TRIGGER IF EXISTS opening_balance_gl_frozen         ON opening_balance_gl;
DROP TRIGGER IF EXISTS opening_balance_batch_immutable   ON opening_balance_batch;
DROP TRIGGER IF EXISTS opening_balance_start_is_fixed    ON opening_balance_batch;

-- `SET LOCAL ROLE`, ca in fisierul de dus. Functiile din schema `rls` apartin lui
-- `evidenta_rls`, iar `evidenta_owner` este NOINHERIT — deci un DROP emis ca
-- owner esueaza cu „must be owner of function". Gasit rulandu-l: prima incercare
-- de derulare inapoi a picat exact acolo.
SET LOCAL ROLE evidenta_rls;

DROP FUNCTION IF EXISTS rls.opening_balance_line_frozen();
DROP FUNCTION IF EXISTS rls.opening_balance_batch_immutable();
DROP FUNCTION IF EXISTS rls.opening_balance_start_is_fixed();

RESET ROLE;

ALTER TABLE opening_balance_payroll_cumulative ALTER COLUMN code TYPE text;
ALTER TABLE opening_balance_payable    ALTER COLUMN document_number TYPE text;
ALTER TABLE opening_balance_receivable ALTER COLUMN document_number TYPE text;
