-- =============================================================================
-- F0.3.7a — corecție: protecția rolurilor de sistem prindea doar ștergerea
--
-- Autoritate:  docs/decisions/020-roluri-ca-date.md
--              docs/decisions/012-sql-in-django-migrations.md (C31)
--              docs/decisions/015-colatie-icu.md (C34)
--
-- Fișier nou, nu editarea lui `0019_roles.up.sql`: acela e aplicat, deci
-- append-only. Aceeași regulă ca pentru ledger, din același motiv.
--
-- CE ERA GREȘIT. `app.protect_system_role()` se declanșa `BEFORE DELETE`, iar
-- `evidenta_app` are `UPDATE` pe ambele tabele. Două instrucțiuni obișnuite
-- ocoleau complet garanția:
--
--   UPDATE role SET is_system = false WHERE id = X;  DELETE FROM role WHERE id = X;
--   -- triggerul citește OLD.is_system, care este deja false la momentul DELETE
--
--   UPDATE role_permission SET permission_key = 'altceva'
--    WHERE role_id = X AND permission_key = 'tenant.manage_roles';
--   -- niciun rând nu se șterge, deci triggerul nu rulează deloc
--
-- Rezultatul era exact scenariul pe care protecția există să-l împiedice: un
-- tenant blocat în afara propriului cont, cu recuperare prin intervenție manuală
-- în producție. Găsit de `schema-reviewer`, nu de suită — testele probau
-- ștergerea, adică fix calea acoperită.
-- =============================================================================

-- --- protecția, acum și pe UPDATE -------------------------------------------

CREATE OR REPLACE FUNCTION app.protect_system_role() RETURNS trigger
    LANGUAGE plpgsql AS $$
BEGIN
    IF TG_TABLE_NAME = 'role' THEN
        IF TG_OP = 'DELETE' THEN
            IF OLD.is_system THEN
                RAISE EXCEPTION 'system role % cannot be deleted', OLD.key
                    USING ERRCODE = 'restrict_violation';
            END IF;
            RETURN OLD;
        END IF;

        -- `is_system` nu se mută în niciun sens. Stins, ar face rolul ștergibil
        -- un rând mai jos; aprins, ar face nesteribil un rol al clientului.
        -- Steagul aparține platformei, care îl scrie o singură dată, la INSERT.
        IF NEW.is_system IS DISTINCT FROM OLD.is_system THEN
            RAISE EXCEPTION 'is_system cannot be changed on role %', OLD.key
                USING ERRCODE = 'restrict_violation';
        END IF;
        RETURN NEW;
    END IF;

    -- role_permission
    IF TG_OP = 'DELETE' THEN
        IF OLD.permission_key = 'tenant.manage_roles'
           AND EXISTS (SELECT 1 FROM role r WHERE r.id = OLD.role_id AND r.is_system)
        THEN
            RAISE EXCEPTION 'system role cannot lose tenant.manage_roles'
                USING ERRCODE = 'restrict_violation';
        END IF;
        RETURN OLD;
    END IF;

    -- O permisiune se acordă sau se retrage; nu se transformă în alta. Cele trei
    -- coloane sunt identitatea rândului, iar mutarea lor era calea prin care un
    -- rol de sistem pierdea administrarea fără ca vreun rând să dispară.
    IF NEW.role_id IS DISTINCT FROM OLD.role_id
       OR NEW.permission_key IS DISTINCT FROM OLD.permission_key
       OR NEW.scope IS DISTINCT FROM OLD.scope
    THEN
        RAISE EXCEPTION 'a role permission is granted or revoked, never rewritten'
            USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER role_protect_system_update
    BEFORE UPDATE ON role
    FOR EACH ROW EXECUTE FUNCTION app.protect_system_role();

CREATE TRIGGER role_permission_protect_system_update
    BEFORE UPDATE ON role_permission
    FOR EACH ROW EXECUTE FUNCTION app.protect_system_role();

-- --- colația coloanei de cod (C34) ------------------------------------------
--
-- `permission_key` este cod, ca `permission.key` și `role.key`, și le scăpase.
-- Consecința secundară, vizibilă în `make schema-dump`: fiindcă nu era pe
-- colația "C", Django adăugase un al doilea index, cu `text_pattern_ops`, doar
-- ca potrivirea pe prefix să funcționeze. Cu colația corectă, indexul nu mai are
-- ce servi.

ALTER TABLE role_permission ALTER COLUMN permission_key TYPE text COLLATE "C";

DROP INDEX IF EXISTS role_permission_permission_key_e7cfd5c0_like;
