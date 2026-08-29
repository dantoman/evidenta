-- 0061 — precizia unei unitati de masura ingheata la prima cantitate purtata (ADR-055, OD-70)
--
-- Context:     infra/migrations/0025_masterdata.up.sql — `unit_of_measure`, politica de tenant
--              docs/decisions/055-precizia-cantitatii-e-a-unitatii.md
--              CLAUDE.md R10 (linia postata e imutabila), C30
--
-- `unit_of_measure.decimal_places` spune cate zecimale poate purta o cantitate in
-- unitatea aceea. Odata ce o linie de document sau de jurnal a fost scrisa cu o
-- cantitate in unitate, precizia nu mai are voie sa se miste: o linie postata e
-- imutabila (R10), iar o unitate care declara azi trei zecimale si maine zero ar
-- face ca „12,500 kg" din registru sa nu mai fie o cantitate pe care unitatea o
-- admite. Corectia e o unitate noua, nu o editare.
--
-- Se verifica cele patru tabele care poarta o cantitate cu unitatea ei:
-- `document_line.unit_id`, `journal_line.uom_id`, `journal_formula.uom_id`,
-- `opening_balance_inventory.uom_id`. Nu si catalogul (`item.base_unit_id`,
-- `item_unit`, `item_barcode`): un articol care refera unitatea nu poarta o
-- cantitate, deci schimbarea il atinge doar pentru liniile viitoare.
--
-- Costul, spus: `journal_line` si `journal_formula` sunt tabele de volum mare fara
-- index pe `uom_id`; verificarea e un EXISTS pe ele. Triggerul e `UPDATE OF
-- decimal_places`, deci ruleaza doar la schimbarea acestei coloane — o operatiune
-- de administrare rara, nu o cale de runtime. Functia ruleaza cu drepturile
-- apelantului, sub politicile lui: rolul aplicatiei isi vede propriul tenant.
--
-- Tiparul din 0042/0058: functia sub `evidenta_rls`, grantul catre owner emis tot
-- de el (ADR-043 §4.1), apoi triggerul ca owner.

SET LOCAL ROLE evidenta_rls;

CREATE OR REPLACE FUNCTION rls.refuse_unit_precision_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.decimal_places IS NOT DISTINCT FROM OLD.decimal_places THEN
        RETURN NEW;
    END IF;
    IF EXISTS (SELECT 1 FROM document_line WHERE unit_id = OLD.id)
       OR EXISTS (SELECT 1 FROM journal_line WHERE uom_id = OLD.id)
       OR EXISTS (SELECT 1 FROM journal_formula WHERE uom_id = OLD.id)
       OR EXISTS (SELECT 1 FROM opening_balance_inventory WHERE uom_id = OLD.id)
    THEN
        RAISE EXCEPTION
            'unit_of_measure % already carries quantities: decimal_places is frozen (ADR-055); define a new unit instead',
            OLD.code
            USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END;
$$;

REVOKE ALL ON FUNCTION rls.refuse_unit_precision_change() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION rls.refuse_unit_precision_change() TO evidenta_owner;

RESET ROLE;

CREATE TRIGGER unit_of_measure_precision_frozen
    BEFORE UPDATE OF decimal_places ON unit_of_measure
    FOR EACH ROW EXECUTE FUNCTION rls.refuse_unit_precision_change();
