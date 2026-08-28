-- =============================================================================
-- Articolul: unitati alternative, coduri de bare, pozitie tarifara
--
-- Autoritate:  docs/decisions/034-denumire-legala-si-interna.md
--              docs/specs/spec-a-tenancy.md §2.5
--              CLAUDE.md R1, C34
--
-- `item_unit` e distincta de `unit_conversion`, care e generala: o cutie tine
-- douasprezece bucati DIN ACEST articol si sase din altul, deci coeficientul
-- apartine perechii, nu unitatilor. Amandoua exista; confundarea lor ar face
-- gresita fiecare intrare de nomenclator care se ambaleaza altfel decat
-- implicitul tenantului.
--
-- `item_barcode` e tabela, nu coloana, fiindca un articol are de regula mai
-- multe — unul pe bucata, unul pe cutie, unul vechi al furnizorului care inca
-- apare pe livrari. Coloana unica lasa al doilea cod fara unde sa mearga, iar
-- solutia obisnuita e o lista separata prin virgula pe care n-o poate indexa
-- nimeni.
-- =============================================================================

ALTER TABLE item         ALTER COLUMN tariff_code TYPE text COLLATE "C";
ALTER TABLE item_barcode ALTER COLUMN barcode     TYPE text COLLATE "C";

ALTER TABLE item_unit ENABLE ROW LEVEL SECURITY;
ALTER TABLE item_unit FORCE  ROW LEVEL SECURITY;
CREATE POLICY item_unit_access ON item_unit
    FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id))
    WITH CHECK (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id));

ALTER TABLE item_barcode ENABLE ROW LEVEL SECURITY;
ALTER TABLE item_barcode FORCE  ROW LEVEL SECURITY;
CREATE POLICY item_barcode_access ON item_barcode
    FOR ALL TO evidenta_app
    USING      (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id))
    WITH CHECK (tenant_id = app.current_tenant_id() AND rls.has_tenant_access(tenant_id));

GRANT SELECT, INSERT, UPDATE, DELETE ON item_unit, item_barcode TO evidenta_app;
