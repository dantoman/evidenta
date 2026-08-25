-- =============================================================================
-- F0.1 — Verificarea colației bazei
--
-- Autoritate:  docs/decisions/015-colatie-icu.md
--
-- Rulează PRIMUL, în baza țintă, ca evidenta_owner sau superuser. Nu modifică nimic.
--
-- De ce există. Colația implicită a bazei este o decizie „la creare": nu se schimbă
-- ulterior fără reconstruirea tuturor indecșilor pe text. O bază creată greșit
-- funcționează perfect și sortează greșit pentru totdeauna — `Zaharia` înaintea lui
-- `Șerban` — iar cauza se caută în raport, nu în definiția bazei.
--
-- Este exact tiparul pe care restul proiectului îl refuză: fail-closed nu ajunge,
-- trebuie și fail-loud. Un defect care nu produce nicio eroare nu se descoperă.
-- =============================================================================

\set ON_ERROR_STOP on

DO $locale$
DECLARE
    v_provider "char";
    v_locale   text;
    v_db       text := current_database();
BEGIN
    SELECT datlocprovider, datlocale
      INTO v_provider, v_locale
      FROM pg_database
     WHERE datname = v_db;

    IF v_provider <> 'i' THEN
        RAISE EXCEPTION
            'evidenta: baza "%" nu foloseste providerul ICU (are %). Colatia nu se poate corecta '
            'printr-o migrare: baza trebuie recreata cu '
            'CREATE DATABASE ... LOCALE_PROVIDER icu ICU_LOCALE ''ro'' TEMPLATE template0. '
            'Vezi ADR-015.',
            v_db, v_provider
            USING ERRCODE = '42501';
    END IF;

    -- ICU accepta si forme cu extensie privata (`ro-x-icu`), pe care le ignora.
    -- Le acceptam la verificare, dar semnalam: valoarea canonica este `ro`.
    IF v_locale IS NULL OR split_part(v_locale, '-', 1) <> 'ro' THEN
        RAISE EXCEPTION
            'evidenta: baza "%" are ICU locale "%" in loc de "ro". Vezi ADR-015.',
            v_db, coalesce(v_locale, '<null>')
            USING ERRCODE = '42501';
    END IF;

    IF v_locale <> 'ro' THEN
        RAISE WARNING
            'evidenta: ICU locale este "%" in loc de "ro". Se comporta identic, dar difera de '
            'documentatie. `ro-x-icu` este numele obiectului de colatie, nu al locale-ului.',
            v_locale;
    END IF;
END
$locale$;
