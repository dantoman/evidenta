-- Tipurile de raport de munca — vocabular global, doar-citire (ADR-071).
--
-- Trei valori, exact cele pe care le distinge prima liniuta de la pct. 1.1 al
-- anexei nr. 1 la Legea nr. 489/1999: contract individual de munca, raporturi de
-- serviciu in baza actului administrativ, contract civil de executare de lucrari
-- sau prestare de servicii. Nu e configurare per tenant: un tenant nu poate avea
-- alte tipuri de raport decat altul in interiorul aceleiasi jurisdictii.
--
-- Excepția de la R1 este din clasa care NU largeste accesul la date (ADR-072
-- §2): tabela nu are proprietar, aplicatia o citeste, scrie doar rolul de
-- migrare. `permission` este precedentul exact, din propriul fisier de exceptii.
--
-- Politica de scriere a owner-ului nu e optionala, si prima redactie a acestui
-- fisier n-o avea. Argumentul era ca insamantarea trece oricum prin usa unica,
-- care suspenda FORCE in tranzactia migrarii — deci politica permanenta ar fi
-- exceptia care cere motiv propriu (OD-94, OD-95). Gardianul
-- `test_reference_load_policy` a masurat altceva: sub FORCE, un privilegiu fara
-- politica NU vede nimic, deci `writer_role = evidenta_owner` ar fi promis o cale
-- de scriere care nu exista. `permission` are exact aceasta politica, din acelasi
-- motiv. Declaratia si baza spun acum acelasi lucru.

ALTER TABLE employment_relationship_type
    ALTER COLUMN code TYPE text COLLATE "C";

-- --- Politica: citire globala, scriere prin nicio politica -------------------

ALTER TABLE employment_relationship_type ENABLE ROW LEVEL SECURITY;
ALTER TABLE employment_relationship_type FORCE  ROW LEVEL SECURITY;

CREATE POLICY employment_relationship_type_read ON employment_relationship_type
    FOR SELECT TO evidenta_app
    USING (true);

CREATE POLICY employment_relationship_type_write ON employment_relationship_type
    FOR ALL TO evidenta_owner
    USING      (true)
    WITH CHECK (true);

-- --- Privilegii --------------------------------------------------------------
--
-- REVOKE explicit, nu absenta unui GRANT: privilegiile implicite din
-- 0001_roles.sql acorda INSERT/UPDATE/DELETE pentru orice tabela creata de
-- owner, deci fara linia de mai jos scrierea ar fi oprita doar de lipsa unei
-- politici — adica de o omisiune. Vezi OD-47 si migrarea 0047, care a reparat
-- exact aceasta forma pe o alta tabela globala.

GRANT  SELECT                            ON employment_relationship_type TO evidenta_app;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE  ON employment_relationship_type FROM evidenta_app;

GRANT  SELECT ON employment_relationship_type TO evidenta_rls;
