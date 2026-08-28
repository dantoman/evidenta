-- =============================================================================
-- Seriile de documente: regim si valabilitate (ADR-022, extins)
--
-- Autoritate:  docs/decisions/022-numerotare-sabloane.md
--              CLAUDE.md R2 (FORCE ROW LEVEL SECURITY), C30
--
-- Doua regimuri paralele, ambele necesare:
--
--   own       contorul aplicatiei genereaza numarul
--   external  identificatorul VINE din afara — schimbul e-Factura (Ordinul SFS
--             185/2023) sau un diapazon `art. 118²` consumat prin `strictforms`
--
-- Sablonul devine astfel „seria in vigoare la o data", nu „seria companiei":
-- unicitatea peste tot timpul ar fi facut imposibila schimbarea seriei, iar
-- absenta ei ar fi lasat doua serii sa raspunda pentru aceeasi zi. De aceea
-- constrangerea de neintrepatrundere, nu cele doua unicitati partiale.
-- =============================================================================

-- --- backfill: sabloanele existente sunt valabile de cand au fost create -----
--
-- `valid_from` se adauga NOT NULL, deci randurile existente au nevoie de o
-- valoare inainte. Si aici e capcana, platita o data pe baza de dezvoltare:
--
--   `FORCE ROW LEVEL SECURITY` se aplica SI proprietarului tabelei, iar politica
--   lui `numbering_template` e scrisa `TO evidenta_app`. Deci `evidenta_owner`
--   nu vede niciun rand: un `UPDATE` simplu atinge zero randuri **si reuseste**,
--   iar `SET NOT NULL` de dupa el scaneaza tabela FIZIC, gaseste randurile pe
--   care UPDATE-ul nu le-a vazut, si cade. Mai rau: un `SELECT count(*)` rulat
--   ca owner raspunde tot zero, deci masuratoarea care ar fi trebuit sa previna
--   asta o confirma.
--
-- `NO FORCE` scoate proprietarul de sub politici cat tine tranzactia migrarii, si
-- se pune la loc imediat. Nu o politica de scriere ca in `0044`: aceea ramane in
-- baza dupa ce nevoia a trecut, iar aici nevoia e o singura instructiune.
-- `ALTER TABLE` ia oricum ACCESS EXCLUSIVE, deci fereastra nu e observabila de
-- nimeni.

ALTER TABLE numbering_template NO FORCE ROW LEVEL SECURITY;

UPDATE numbering_template
   SET valid_from = created_at::date
 WHERE valid_from IS NULL;

ALTER TABLE numbering_template FORCE ROW LEVEL SECURITY;
