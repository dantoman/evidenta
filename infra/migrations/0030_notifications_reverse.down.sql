-- Inversul corectat al lui 0030_notifications.up.sql — ADR-043, `OD-64`.
--
-- Inlocuieste `0030_notifications.down.sql`, care NU rulează: functiile din schema `rls` sunt
-- create sub `SET LOCAL ROLE evidenta_rls` si sterse ca owner, iar
-- `evidenta_owner` e `NOINHERIT` — deci apartenenta la rol nu-i da privilegiile
-- fara `SET ROLE`, si `DROP` cade cu „must be owner of function".
--
-- Fisierul vechi nu se editeaza: `C31` il face append-only din clipa in care a
-- fost aplicat, iar istoricul trebuie sa arate in continuare ce a rulat inainte.
-- Corectia este un fisier nou, si asta este el.
--
-- ORDINEA E PARTE DIN CONTRACT: triggere, apoi politici, apoi functii. Fiecare
-- `DROP` numit. **Fara `CASCADE`** — un `CASCADE` nu se opreste la ce a creat
-- migrarea asta: poate sterge obiecte atasate intre timp de alta migrare de
-- aceeasi functie, si o face tacut, raportand succes. Daca un `DROP` cade pe
-- dependenta, eroarea e informatie, nu obstacol.

DROP POLICY IF EXISTS notification_delivery_own ON notification_delivery;
DROP POLICY IF EXISTS notification_own          ON notification;

ALTER TABLE notification_delivery NO FORCE ROW LEVEL SECURITY;
ALTER TABLE notification_delivery DISABLE  ROW LEVEL SECURITY;
ALTER TABLE notification          NO FORCE ROW LEVEL SECURITY;
ALTER TABLE notification          DISABLE  ROW LEVEL SECURITY;

SET LOCAL ROLE evidenta_rls;
DROP FUNCTION IF EXISTS rls.notify_tenant_members(uuid, text, jsonb, uuid);
DROP FUNCTION IF EXISTS rls.create_notification_delivery(uuid, uuid, text, text);
DROP FUNCTION IF EXISTS rls.create_notification(uuid, uuid, text, jsonb, uuid);
RESET ROLE;
