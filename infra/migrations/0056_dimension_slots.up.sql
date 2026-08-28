-- Sloturile de dimensiuni tipizate ale contului — ADR-048, etapa 1+2 a bazei
-- motorului.
--
-- Planul de conturi declara, per cont si per versiune, ce tipuri de dimensiuni
-- poarta contul si in ce pozitie: patru coloane, nu un `jsonb` si nu o tabela
-- atribut-valoare. Coloanele sunt chei din vocabularul inchis ADR-029
-- (`partner`, `dim_1`), deci sunt coduri, nu denumiri: `COLLATE "C"` (C34).
--
-- `required_dimensions` ramane singurul loc care spune ce e OBLIGATORIU; cele
-- patru sloturi spun ce e PURTAT. Doua fapte, doua locuri, o constrangere care
-- le leaga: un cont nu poate cere o dimensiune pe care nu o poarta. Django nu
-- poate exprima `<@` peste un ARRAY construit din alte coloane, de aceea CHECK-ul
-- sta aici si nu in `Meta`.
--
-- Livrata cu declaratiile goale: care conturi poarta ce dimensiuni e decizie
-- contabila a proprietarului, nu a acestei migrari.

ALTER TABLE coa_template_account ALTER COLUMN slot_1_dimension TYPE text COLLATE "C";
ALTER TABLE coa_template_account ALTER COLUMN slot_2_dimension TYPE text COLLATE "C";
ALTER TABLE coa_template_account ALTER COLUMN slot_3_dimension TYPE text COLLATE "C";
ALTER TABLE coa_template_account ALTER COLUMN slot_4_dimension TYPE text COLLATE "C";

ALTER TABLE company_account ALTER COLUMN slot_1_dimension TYPE text COLLATE "C";
ALTER TABLE company_account ALTER COLUMN slot_2_dimension TYPE text COLLATE "C";
ALTER TABLE company_account ALTER COLUMN slot_3_dimension TYPE text COLLATE "C";
ALTER TABLE company_account ALTER COLUMN slot_4_dimension TYPE text COLLATE "C";

-- `array_remove(..., NULL)` face din patru sloturi goale un `{}`, iar
-- `'{}' <@ '{}'` e adevarat: un cont care nu declara nimic si nu cere nimic
-- trece — starea in care se livreaza fiecare cont azi.
ALTER TABLE coa_template_account
    ADD CONSTRAINT coa_template_account_required_within_slots
    CHECK (required_dimensions <@ array_remove(
        ARRAY[slot_1_dimension, slot_2_dimension, slot_3_dimension, slot_4_dimension], NULL));

ALTER TABLE company_account
    ADD CONSTRAINT company_account_required_within_slots
    CHECK (required_dimensions <@ array_remove(
        ARRAY[slot_1_dimension, slot_2_dimension, slot_3_dimension, slot_4_dimension], NULL));
