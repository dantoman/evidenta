-- Inversul lui 0029_exchange_rate.up.sql. Tabela e stearsa de migrarea Django;
-- aici se desface doar ce a adaugat SQL-ul manual.

DROP POLICY IF EXISTS exchange_rate_read ON exchange_rate;

ALTER TABLE exchange_rate NO FORCE ROW LEVEL SECURITY;
ALTER TABLE exchange_rate DISABLE  ROW LEVEL SECURITY;
