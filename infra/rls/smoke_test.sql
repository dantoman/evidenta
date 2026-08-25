-- =============================================================================
-- Proba de fum RLS (F0.1). Rulează ca **evidenta_app**, după smoke_fixture.sql.
--
-- NU înlocuiește suitele din F0.2. Este proba, în SQL, că design-ul din ADR-003
-- funcționează — scrisă înaintea mediului Python, pentru că o afirmație de
-- arhitectură nemăsurată nu valorează nimic.
--
-- CONDIȚIA DE ȘTERGERE, fixată în backlogul F0.2:
--   Acest fișier și smoke_fixture.sql se șterg ABIA când FIECARE scenariu de mai jos
--   are echivalent Python care trece, și se șterg în ACELAȘI commit care le adaugă.
--   Nu se retrage nimic parțial. O suită verde care acoperă mai puțin decât cea pe
--   care o înlocuiește este o regresie deghizată în progres.
--
-- Verificat pe PostgreSQL 18.6. Rezultate așteptate:
--   IZ-30 eroare · IZ-01 un rând · IZ-03 zero · IZ-10 un rând
--   IZ-11 zero    · IZ-18 zero   · IZ-08 un rând · IZ-50 refuz
-- =============================================================================

\echo '--- IZ-30: interogare fara context -> EROARE, nu zero randuri'
BEGIN; SELECT count(*) FROM partner; ROLLBACK;
\echo '--- IZ-01: UA, context tenant A -> doar partenerii lui A'
BEGIN;
SET LOCAL app.tenant_id = '11111111-1111-1111-1111-111111111111';
SET LOCAL app.user_id   = 'aaaaaaaa-0000-0000-0000-000000000001';
SELECT name FROM partner;
ROLLBACK;
\echo '--- IZ-03: UA seteaza tenant_id = B -> zero randuri (has_tenant_access esueaza)'
BEGIN;
SET LOCAL app.tenant_id = '22222222-2222-2222-2222-222222222222';
SET LOCAL app.user_id   = 'aaaaaaaa-0000-0000-0000-000000000001';
SELECT count(*) FROM partner;
ROLLBACK;
\echo '--- IZ-10: UF cu engagement activ, context tenant B -> acces'
BEGIN;
SET LOCAL app.tenant_id     = '22222222-2222-2222-2222-222222222222';
SET LOCAL app.user_id       = 'ffffffff-0000-0000-0000-000000000001';
SET LOCAL app.actor_firm_id = 'ffffffff-ffff-ffff-ffff-ffffffffffff';
SELECT name FROM partner;
ROLLBACK;
\echo '--- IZ-11: engagement expirat (valid_to trecut, status inca active) -> zero'
BEGIN;
SET LOCAL app.tenant_id     = '11111111-1111-1111-1111-111111111111';
SET LOCAL app.user_id       = 'ffffffff-0000-0000-0000-000000000001';
SET LOCAL app.actor_firm_id = 'ffffffff-ffff-ffff-ffff-ffffffffffff';
SELECT count(*) FROM partner;
ROLLBACK;
\echo '--- IZ-18: UA imprumuta actor_firm_id al firmei -> zero (nu e membru al firmei)'
BEGIN;
SET LOCAL app.tenant_id     = '22222222-2222-2222-2222-222222222222';
SET LOCAL app.user_id       = 'aaaaaaaa-0000-0000-0000-000000000001';
SET LOCAL app.actor_firm_id = 'ffffffff-ffff-ffff-ffff-ffffffffffff';
SELECT count(*) FROM partner;
ROLLBACK;
\echo '--- IZ-08: membership -> UA vede doar randurile lui'
BEGIN;
SET LOCAL app.tenant_id = '11111111-1111-1111-1111-111111111111';
SET LOCAL app.user_id   = 'aaaaaaaa-0000-0000-0000-000000000001';
SELECT count(*) FROM membership;
ROLLBACK;
\echo '--- IZ-50: INSERT cu tenant_id strain -> refuzat de WITH CHECK'
BEGIN;
SET LOCAL app.tenant_id = '11111111-1111-1111-1111-111111111111';
SET LOCAL app.user_id   = 'aaaaaaaa-0000-0000-0000-000000000001';
INSERT INTO partner VALUES (gen_random_uuid(),'22222222-2222-2222-2222-222222222222','furat');
ROLLBACK;
