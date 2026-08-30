-- CUATM si CAEM pe companie — codurile pe care le poarta antetul oricarei dari
-- de seama statutare.
--
-- Autoritate:  CLAUDE.md C34; docs/decisions/015-colatie-icu.md
--
-- Coduri, nu denumiri: `COLLATE "C"`. Fara ea, orice raport ordonat dupa CAEM
-- iese sortat lingvistic, tacit — si CAEM se compara caracter cu caracter, ca
-- IDNO.
--
-- Nullable, si asta e starea onesta: niciun clasificator (CUATM sau CAEM) nu e in
-- acest repo. Randul exista, valoarea vine cand o introduce cineva, iar declaratia
-- generata intre timp SPUNE ca lipseste in loc sa inventeze un cod.

ALTER TABLE company ALTER COLUMN cuatm_code TYPE text COLLATE "C";
ALTER TABLE company ALTER COLUMN caem_code  TYPE text COLLATE "C";
