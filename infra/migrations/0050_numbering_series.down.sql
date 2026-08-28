-- Inversa lui 0050_numbering_series.up.sql (ADR-012).
--
-- Backfill-ul nu se inverseaza: coloana pe care a completat-o este stearsa de
-- migrarea Django care il inconjoara, deci nu exista stare de restaurat.
-- `FORCE ROW LEVEL SECURITY` e repus de fisierul forward inainte de a se
-- incheia, deci nici acolo nu ramane nimic de derulat.
--
-- Un fisier gol ar fi fost refuzat de C30; acesta spune de ce nu are continut.
SELECT 1;
