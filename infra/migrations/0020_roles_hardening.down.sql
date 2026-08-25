-- Inversa lui 0020_roles_hardening.up.sql (ADR-012: reverse_sql nu e opțional).
--
-- Readuce funcția la forma din `0019_roles.up.sql` — cea care prinde doar
-- ștergerea. Derularea înapoi reintroduce, deci, gaura pe care `0020` o închide.
-- Este consecința corectă a unei derulări, nu o scăpare: `reverse_sql` restaurează
-- starea anterioară, iar starea anterioară era aceasta.

CREATE INDEX IF NOT EXISTS role_permission_permission_key_e7cfd5c0_like
    ON role_permission (permission_key text_pattern_ops);

ALTER TABLE role_permission ALTER COLUMN permission_key TYPE text;

DROP TRIGGER IF EXISTS role_permission_protect_system_update ON role_permission;
DROP TRIGGER IF EXISTS role_protect_system_update ON role;

CREATE OR REPLACE FUNCTION app.protect_system_role() RETURNS trigger
    LANGUAGE plpgsql AS $$
BEGIN
    IF TG_TABLE_NAME = 'role' THEN
        IF OLD.is_system THEN
            RAISE EXCEPTION 'system role % cannot be deleted', OLD.key
                USING ERRCODE = 'restrict_violation';
        END IF;
        RETURN OLD;
    END IF;

    IF OLD.permission_key = 'tenant.manage_roles'
       AND EXISTS (SELECT 1 FROM role r WHERE r.id = OLD.role_id AND r.is_system)
    THEN
        RAISE EXCEPTION 'system role cannot lose tenant.manage_roles'
            USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN OLD;
END;
$$;
