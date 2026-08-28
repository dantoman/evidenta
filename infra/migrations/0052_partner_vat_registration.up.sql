-- =============================================================================
-- Contrapartea: inregistrarea in scopuri de TVA ca stare cu data efectiva
--
-- Autoritate:  docs/decisions/034-denumire-legala-si-interna.md
--              docs/specs/spec-a-tenancy.md §2.5
--              CLAUDE.md R1, R18, C34
--
-- Aceeasi forma pe care `company_vat_registration` o are deja, si din acelasi
-- motiv: o contraparte se inregistreaza si poate fi radiata in cursul anului,
-- iar un document emis inainte de radiere era corect atunci. Recalcularea acelei
-- perioade trebuie sa foloseasca starea de atunci (`R18`) — ceea ce un indicator
-- pe partener nu poate exprima.
--
-- De aceea `partner.vat_code` a fost mutata aici, nu duplicata: codul apartine
-- inregistrarii. Un partener radiat si reinregistrat primeste altul, iar o
-- singura coloana l-ar fi suprascris tacit pe cel pe care facturile deja emise
-- il poarta.
-- =============================================================================

ALTER TABLE partner_vat_registration ALTER COLUMN vat_code TYPE text COLLATE "C";

ALTER TABLE partner_vat_registration ENABLE ROW LEVEL SECURITY;
ALTER TABLE partner_vat_registration FORCE  ROW LEVEL SECURITY;

-- Tenant-scoped, ca partenerul pe care il descrie: acelasi furnizor e acelasi
-- pentru toate companiile firmei (amendament §C.1), si statutul lui de platitor
-- de TVA nu se schimba de la o companie la alta.
CREATE POLICY partner_vat_registration_access ON partner_vat_registration
    FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id))
    WITH CHECK (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id));

GRANT SELECT, INSERT, UPDATE, DELETE ON partner_vat_registration TO evidenta_app;
