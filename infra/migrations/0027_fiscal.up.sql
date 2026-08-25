-- Parametri fiscali si registrul de selectie a logicii — R15, R17, R18.
--
-- Cele trei tabele sunt globale si citibile de oricine, scriibile de nimeni prin
-- calea obisnuita. Motivul nu e comoditatea: cota de TVA nu apartine unui tenant.
-- Daca ar apartine, doi tenanti ar putea calcula aceeasi perioada diferit, si
-- amandoi ar avea dreptate dupa propria baza. Scrierea trece prin calea
-- privilegiata P-4, jurnalizata.
--
-- Citirea este deschisa deliberat, si nu doar pentru calcul: un tenant care
-- recalculeaza o perioada din 2026 in 2030 trebuie sa poata vedea sub ce act
-- normativ s-a calculat. Un parametru fara sursa vizibila e un numar pe care
-- nimeni nu-l poate apara in fata unui control.

ALTER TABLE fiscal_parameter_source ALTER COLUMN act_number              TYPE text COLLATE "C";
ALTER TABLE fiscal_parameter_source ALTER COLUMN official_gazette_number TYPE text COLLATE "C";
ALTER TABLE fiscal_parameter       ALTER COLUMN parameter_key            TYPE text COLLATE "C";
ALTER TABLE fiscal_logic_version   ALTER COLUMN logic_key                TYPE text COLLATE "C";
ALTER TABLE fiscal_logic_version   ALTER COLUMN version                  TYPE text COLLATE "C";
ALTER TABLE fiscal_logic_version   ALTER COLUMN implementation_ref       TYPE text COLLATE "C";

-- --- Politici: citire globala, scriere doar prin P-4 -------------------------

ALTER TABLE fiscal_parameter_source ENABLE ROW LEVEL SECURITY;
ALTER TABLE fiscal_parameter_source FORCE  ROW LEVEL SECURITY;
CREATE POLICY fiscal_parameter_source_read ON fiscal_parameter_source
    FOR SELECT TO evidenta_app USING (true);

ALTER TABLE fiscal_parameter ENABLE ROW LEVEL SECURITY;
ALTER TABLE fiscal_parameter FORCE  ROW LEVEL SECURITY;
CREATE POLICY fiscal_parameter_read ON fiscal_parameter
    FOR SELECT TO evidenta_app USING (true);

ALTER TABLE fiscal_logic_version ENABLE ROW LEVEL SECURITY;
ALTER TABLE fiscal_logic_version FORCE  ROW LEVEL SECURITY;
CREATE POLICY fiscal_logic_version_read ON fiscal_logic_version
    FOR SELECT TO evidenta_app USING (true);

-- --- Un singur parametru in vigoare la o data --------------------------------
--
-- Rezolvarea refuza doua potriviri, si asta e corect ca ultima linie. Dar un
-- refuz la calcul inseamna ca eroarea de configurare a ajuns pana la utilizator:
-- se descopera la inchiderea lunii, de cineva care nu poate s-o repare. Baza o
-- respinge la INSERT, cand inca e in mainile celui care a introdus-o.
--
-- `COALESCE(scope_ref, uuid_nil)` pentru ca doua randuri globale au amandoua
-- `scope_ref` NULL, iar NULL <> NULL: un EXCLUDE pe coloana nuda nu s-ar
-- declansa niciodata exact in cazul cel mai frecvent.
--
-- Doar peste randurile `active`. Un draft pentru anul viitor trebuie sa poata sta
-- alaturi de valoarea in vigoare — asta e chiar felul in care se pregateste o
-- schimbare de cota inainte sa intre in vigoare.

CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE fiscal_parameter
    ADD CONSTRAINT fiscal_parameter_no_overlap
    EXCLUDE USING gist (
        parameter_key WITH =,
        (COALESCE(scope_ref, '00000000-0000-0000-0000-000000000000'::uuid)) WITH =,
        daterange(valid_from, valid_to, '[)') WITH &&
    ) WHERE (status = 'active');

ALTER TABLE fiscal_logic_version
    ADD CONSTRAINT fiscal_logic_version_no_overlap
    EXCLUDE USING gist (
        logic_key WITH =,
        daterange(valid_from, valid_to, '[)') WITH &&
    ) WHERE (status = 'active');

-- --- Privilegii --------------------------------------------------------------
--
-- REVOKE explicit: privilegiile implicite din 0001_roles.sql acorda
-- INSERT/UPDATE/DELETE pentru orice tabela creata de owner, deci fara linia asta
-- scrierea ar fi oprita doar de absenta unei politici — adica de o omisiune.
-- Vezi OD-47.

GRANT  SELECT                   ON fiscal_parameter_source TO evidenta_app;
REVOKE INSERT, UPDATE, DELETE   ON fiscal_parameter_source FROM evidenta_app;
GRANT  SELECT                   ON fiscal_parameter        TO evidenta_app;
REVOKE INSERT, UPDATE, DELETE   ON fiscal_parameter        FROM evidenta_app;
GRANT  SELECT                   ON fiscal_logic_version    TO evidenta_app;
REVOKE INSERT, UPDATE, DELETE   ON fiscal_logic_version    FROM evidenta_app;

GRANT SELECT ON fiscal_parameter_source TO evidenta_rls;
GRANT SELECT ON fiscal_parameter        TO evidenta_rls;
GRANT SELECT ON fiscal_logic_version    TO evidenta_rls;
