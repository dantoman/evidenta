-- Inversul lui 0030_notifications.up.sql. Tabelele sunt sterse de migrarea
-- Django; aici se desface doar ce a adaugat SQL-ul manual.

DROP FUNCTION IF EXISTS rls.notify_tenant_members(uuid, text, jsonb, uuid);
DROP FUNCTION IF EXISTS rls.create_notification_delivery(uuid, uuid, text, text);
DROP FUNCTION IF EXISTS rls.create_notification(uuid, uuid, text, jsonb, uuid);

DROP POLICY IF EXISTS notification_delivery_own ON notification_delivery;
DROP POLICY IF EXISTS notification_own          ON notification;

ALTER TABLE notification_delivery NO FORCE ROW LEVEL SECURITY;
ALTER TABLE notification_delivery DISABLE  ROW LEVEL SECURITY;
ALTER TABLE notification          NO FORCE ROW LEVEL SECURITY;
ALTER TABLE notification          DISABLE  ROW LEVEL SECURITY;
