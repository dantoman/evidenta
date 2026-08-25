-- Cursuri valutare — Spec B §7.2, cale privilegiata P-3.
--
-- Globala, ca si parametrii fiscali, si din acelasi motiv: cursul oficial al
-- unei zile e acelasi pentru toti. Un tenant care ar putea sa-l scrie ar putea
-- schimba cat a valorat o factura — pentru toti ceilalti tenanti din instalare.
--
-- Citirea e libera fiindca o inregistrare postata pastreaza cursul la care a
-- fost facuta (R10), iar clientul trebuie sa poata vedea care a fost.

ALTER TABLE exchange_rate ALTER COLUMN currency  TYPE varchar(3) COLLATE "C";
ALTER TABLE exchange_rate ALTER COLUMN rate_type TYPE text      COLLATE "C";

ALTER TABLE exchange_rate ENABLE ROW LEVEL SECURITY;
ALTER TABLE exchange_rate FORCE  ROW LEVEL SECURITY;

CREATE POLICY exchange_rate_read ON exchange_rate
    FOR SELECT TO evidenta_app USING (true);

-- REVOKE explicit: privilegiile implicite din 0001_roles.sql acorda
-- INSERT/UPDATE/DELETE pentru orice tabela creata de owner, deci fara linia asta
-- scrierea ar fi oprita doar de absenta unei politici — adica de o omisiune.
-- Vezi OD-47.

GRANT  SELECT                 ON exchange_rate TO evidenta_app;
REVOKE INSERT, UPDATE, DELETE ON exchange_rate FROM evidenta_app;
GRANT  SELECT                 ON exchange_rate TO evidenta_rls;
