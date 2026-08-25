-- Raport RLS — per tabelă: politici, RLS activ, FORCE, prezența coloanei de tenant.
--
-- Read-only. Rulat de `make rls-report`, singura cale prin care `schema-reviewer` vede starea
-- reală a bazei. Există pentru că un fișier de migrare citit nu este același lucru cu schema pe
-- care a produs-o: o politică poate lipsi, un `FORCE` poate fi uitat, iar diferența nu se vede
-- decât interogând catalogul.
--
-- `tenant_id` apare aici deliberat, deși R1 se verifică în gardianul de model (suita 2): raportul
-- e citit de un om sau de un agent care compară cu `infra/rls/exceptions.toml`, iar o tabelă fără
-- tenant_id și fără politică este exact tiparul pe care trebuie să-l observe dintr-o privire.

\set ON_ERROR_STOP on

SELECT
    n.nspname                                                   AS schema,
    c.relname                                                   AS tabela,
    c.relrowsecurity                                            AS rls,
    c.relforcerowsecurity                                       AS force_rls,
    (SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid) AS politici,
    EXISTS (
        SELECT 1
        FROM pg_attribute a
        WHERE a.attrelid = c.oid
          AND a.attname = 'tenant_id'
          AND a.attnum > 0
          AND NOT a.attisdropped
    )                                                           AS tenant_id
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'p')            -- tabele obișnuite și partiționate
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
  AND n.nspname NOT LIKE 'pg_toast%'
ORDER BY n.nspname, c.relname;
