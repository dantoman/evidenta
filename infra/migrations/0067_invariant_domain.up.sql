-- Domeniul unui invariant de calcul — o MULTIME de tipuri, nu un tip (ADR-071 §7.1).
--
-- Art. 22 alin. (1) din Legea nr. 489/1999 spune „pentru fiecare salariat", iar
-- persoana numita prin act administrativ ESTE salariat pentru el. Deci invariantul
-- bazei minime acopera `employment_contract` SI `service_relationship`, si NU
-- acopera `civil_contract`.
--
-- O coloana `FK` unica poate spune „acest invariant se aplica tipului X". Nu poate
-- spune „tipurilor X si Y". Scris asa, art. 22 s-ar lega de un tip, celalalt ar
-- scapa, iar rezultatul ar fi contributie sub minim — perfect echilibrata, `R11`
-- trece, niciun test de sold n-o vede. Exact defectul pe care ADR-071 il previne,
-- reintrat prin cardinalitate in loc de prin vocabular (OD-106).
--
-- Excepția de la R1 e din clasa care NU largeste accesul (ADR-072 §2).

ALTER TABLE calculation_invariant_domain
    ALTER COLUMN invariant_key TYPE text COLLATE "C";

ALTER TABLE calculation_invariant_domain ENABLE ROW LEVEL SECURITY;
ALTER TABLE calculation_invariant_domain FORCE  ROW LEVEL SECURITY;

CREATE POLICY calculation_invariant_domain_read ON calculation_invariant_domain
    FOR SELECT TO evidenta_app
    USING (true);

-- Aceeasi politica de scriere pentru owner ca la tabela pe care o refera, si din
-- acelasi motiv masurat: sub FORCE, un privilegiu FARA politica nu vede nimic,
-- deci `writer_role = evidenta_owner` ar declara o cale de scriere inexistenta.
CREATE POLICY calculation_invariant_domain_write ON calculation_invariant_domain
    FOR ALL TO evidenta_owner
    USING      (true)
    WITH CHECK (true);

GRANT  SELECT                            ON calculation_invariant_domain TO evidenta_app;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE  ON calculation_invariant_domain FROM evidenta_app;
GRANT  SELECT                            ON calculation_invariant_domain TO evidenta_rls;
