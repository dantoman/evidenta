-- =============================================================================
-- F0.3.7a — Permission, Role, RolePermission: tipuri, integritate, politici
--
-- Autoritate:  docs/decisions/020-roluri-ca-date.md
--              docs/specs/spec-a-tenancy.md §1.6, §1.7, §11.8
--              docs/decisions/015-colatie-icu.md (C34)
--
-- Ordinea impusă de ADR-012: tabelele există din migrarea Django care referă
-- acest fișier, apoi tipuri → constrângeri → ENABLE → FORCE → POLICY → GRANT.
--
-- Ce face fișierul și migrarea Django nu poate: cheile străine **compuse**.
-- Django nu le exprimă, iar fără ele un rând ar putea trimite la rolul altui
-- tenant — exact scurgerea pe care restul modelului o închide.
-- =============================================================================

-- --- tipuri -----------------------------------------------------------------
--
-- Coduri, nu denumiri: ordonare pe octeți (C34). `role.name` rămâne pe colația
-- bazei — acela chiar este o denumire, aleasă de tenant.

ALTER TABLE permission ALTER COLUMN key TYPE text COLLATE "C";
ALTER TABLE role       ALTER COLUMN key TYPE text COLLATE "C";

-- --- integritate între tenanți ----------------------------------------------
--
-- Chei candidate pe care se sprijină cheile străine compuse de mai jos. Sunt
-- redundante ca unicitate — `id` este deja cheie primară — dar PostgreSQL cere
-- o constrângere unică pe exact coloanele referite.

ALTER TABLE role ADD CONSTRAINT role_tenant_id_unique UNIQUE (tenant_id, id);
ALTER TABLE role ADD CONSTRAINT role_tenant_id_level_unique UNIQUE (tenant_id, id, level);
ALTER TABLE permission ADD CONSTRAINT permission_key_scope_unique UNIQUE (key, scope);

-- Un membership nu poate purta rolul altui tenant. Verificarea în serviciu ar
-- fi ocolită de primul import în masă; aici nu se poate ocoli deloc.
ALTER TABLE membership
    ADD CONSTRAINT membership_role_same_tenant
    FOREIGN KEY (tenant_id, role_id) REFERENCES role (tenant_id, id);

ALTER TABLE company_access
    ADD CONSTRAINT company_access_role_same_tenant
    FOREIGN KEY (tenant_id, role_id) REFERENCES role (tenant_id, id);

-- O singură cheie străină acoperă două invariante deodată: rândul aparține
-- aceluiași tenant ca rolul, iar permisiunea are exact domeniul rolului. Un rol
-- de nivel `tenant` nu poate primi o permisiune de companie, și invers.
ALTER TABLE role_permission
    ADD CONSTRAINT role_permission_role_same_tenant_and_level
    FOREIGN KEY (tenant_id, role_id, scope) REFERENCES role (tenant_id, id, level);

ALTER TABLE role_permission
    ADD CONSTRAINT role_permission_permission_same_scope
    FOREIGN KEY (permission_key, scope) REFERENCES permission (key, scope);

-- --- rolurile de sistem nu se pot goli ---------------------------------------
--
-- ADR-020: rolurile de sistem nu se șterg și nu pot pierde administrarea
-- rolurilor. Fără asta, primul client care își editează rolurile greșit rămâne
-- blocat în afara propriului tenant, iar recuperarea devine intervenție manuală
-- în producție — adică exact ce nu se poate audita.
--
-- Trigger, nu constrângere: regula privește ștergerea unui rând, iar un CHECK nu
-- se evaluează la DELETE.

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

    -- role_permission: se poate retrage orice permisiune, mai puțin cea care
    -- face rolul de sistem administrabil.
    IF OLD.permission_key = 'tenant.manage_roles'
       AND EXISTS (SELECT 1 FROM role r WHERE r.id = OLD.role_id AND r.is_system)
    THEN
        RAISE EXCEPTION 'system role cannot lose tenant.manage_roles'
            USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN OLD;
END;
$$;

CREATE TRIGGER role_protect_system
    BEFORE DELETE ON role
    FOR EACH ROW EXECUTE FUNCTION app.protect_system_role();

CREATE TRIGGER role_permission_protect_system
    BEFORE DELETE ON role_permission
    FOR EACH ROW EXECUTE FUNCTION app.protect_system_role();

-- --- permission: policy_shape = global_read_only -----------------------------
--
-- Catalogul este același pentru toți și nu aparține nimănui: aceeași lege pentru
-- toate tenanturile, ca `fiscal_parameter`. Aplicația îl citește; scrie doar
-- calea privilegiată, adică rolul de migrare — care este exact ce înseamnă
-- „alimentat din cod" din ADR-020.

ALTER TABLE permission ENABLE ROW LEVEL SECURITY;
ALTER TABLE permission FORCE  ROW LEVEL SECURITY;

CREATE POLICY permission_read ON permission
    FOR SELECT TO evidenta_app
    USING (true);

CREATE POLICY permission_platform_write ON permission
    FOR ALL TO evidenta_owner
    USING      (true)
    WITH CHECK (true);

-- --- role și role_permission: șablonul de tenant -----------------------------

ALTER TABLE role ENABLE ROW LEVEL SECURITY;
ALTER TABLE role FORCE  ROW LEVEL SECURITY;

CREATE POLICY role_access ON role
    FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id))
    WITH CHECK (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id));

ALTER TABLE role_permission ENABLE ROW LEVEL SECURITY;
ALTER TABLE role_permission FORCE  ROW LEVEL SECURITY;

CREATE POLICY role_permission_access ON role_permission
    FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id))
    WITH CHECK (tenant_id = app.current_tenant_id()
                AND rls.has_tenant_access(tenant_id));

-- --- granturi ----------------------------------------------------------------

GRANT SELECT ON permission TO evidenta_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON role, role_permission TO evidenta_app;
