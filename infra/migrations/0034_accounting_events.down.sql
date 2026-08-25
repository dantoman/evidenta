-- Inversul lui 0034_accounting_events.up.sql. Tabela e stearsa de migrarea
-- Django; aici se desface doar ce a adaugat SQL-ul manual.

DROP TRIGGER IF EXISTS accounting_event_no_delete ON accounting_event;
DROP TRIGGER IF EXISTS accounting_event_immutable ON accounting_event;
DROP FUNCTION IF EXISTS app.accounting_event_no_delete();
DROP FUNCTION IF EXISTS app.accounting_event_immutable();

DROP INDEX IF EXISTS acc_event_queue_idx;

DROP POLICY IF EXISTS accounting_event_access ON accounting_event;

ALTER TABLE accounting_event NO FORCE ROW LEVEL SECURITY;
ALTER TABLE accounting_event DISABLE  ROW LEVEL SECURITY;
