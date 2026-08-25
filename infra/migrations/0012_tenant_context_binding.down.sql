-- Revine la forma din 0010. Derularea înapoi lărgește politica, deci nu se face
-- decât împreună cu derularea migrării care a introdus-o.

DROP POLICY tenant_access ON tenant;

CREATE POLICY tenant_access ON tenant
    FOR ALL TO evidenta_app
    USING      (rls.has_tenant_access(id))
    WITH CHECK (rls.has_tenant_access(id));
