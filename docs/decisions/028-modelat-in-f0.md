# ADR-028 — Ce înseamnă „modelat în F0", și unde locuiesc modelele care nu se construiesc încă

- **Stare:** Acceptat
- **Data:** 2026-08-25
- **Context:** F0.7.5 (`Warehouse`), blocată de `OD-11`; conflictul `X-5`
- **Închide:** `OD-11`
- **Nu închide:** `DNB-02` (dimensiuni definite de utilizator) — rămâne deschisă, vezi §5

## Problema, așa cum era formulată

`OD-11` întreabă unde locuiesc modelele „modelate în F0, implementate mai târziu", cu trei variante:
app creat devreme cu doar modelul, model găzduit într-un app părinte, sau amânare cu reducerea lui
`F0.7`. Se aplică la ~15 module. `F0.7.5` cere modelul `Warehouse` în F0; harta îi dă Faza F4.

## Ce s-a găsit

**Decizia este deja luată, într-o regulă care are prioritate.** `CLAUDE.md` §4:

> Nu se creează app-uri Django goale pentru module din faze viitoare. „Modelat în F0" înseamnă că
> structura din faza curentă nu face imposibil modulul viitor, nu că app-ul există acum.

Fișierul acela își declară singur autoritatea: „Regulile de mai jos nu sunt recomandări." Deci
varianta (A) — app creat devreme cu doar modelul — este exclusă, iar (B) — model găzduit într-un app
părinte — este aceeași lucrare sub alt nume: un `Warehouse` în `masterdata/items` ar fi un model al
unui modul de F4 aflat în app-ul altui modul, adică exact acumularea pe care `C1` o interzice.

Rămâne (C), și nu ca ultimă opțiune: **este ce spune regula.**

## Decizia

`OD-11` se închide cu răspunsul pe care `CLAUDE.md` §4 îl dă deja. Consecințele, explicit:

1. **Nu se creează `masterdata/warehouses` în F0.** Nici `masterdata/dimensions`. Nici alt app
   pentru un modul de fază viitoare.
2. **„Modelat în F0" este o obligație negativă, nu una pozitivă.** Nu cere să scrii ceva; cere ca
   nimic din ce scrii să nu facă modulul viitor imposibil sau scump. Se **verifică**, nu se
   construiește.
3. **`F0.7.5` nu este muncă de model, este o verificare.** Criteriul „modelul există și trece suita
   2" din backlog contrazice `CLAUDE.md` §4 și se retrage. Ce rămâne este întrebarea la care F0 chiar
   trebuie să răspundă: *ce, din schema F0, ar face un `Warehouse` viitor imposibil sau costisitor?*
4. **`X-5` se rezolvă în favoarea hărții.** `warehouses` este F4, `dimensions` este F1. Sarcina
   `F0.7` cerea altceva; harta câștigă, fiindcă e susținută de o regulă, iar backlogul nu.

## Verificarea, făcută acum

Ce ar putea face un modul viitor imposibil sau scump nu e „lipsa unei coloane" — coloanele se adaugă,
`C5` cere migrații aditive. Sunt trei lucruri, și toate trei sunt curate:

| Risc | Stare |
|---|---|
| O tabelă append-only de volum mare ar avea nevoie de o cheie străină **către** depozit | `journal_line` nu există încă (F1.2); când există, `warehouse_id` este cheie **ieșind**, nu intrând, deci `R21` nu se opune |
| Coloana de partiționare ar trebui adăugată ulterior | `R22` e deja impusă pe tabelele append-only existente; un modul nou își aduce propriile coloane |
| Un identificator ar avea tipul greșit | `C6` fixează `UUID` pentru entitățile expuse extern — `Warehouse` va fi una — și `bigint` doar pentru tabelele append-only enumerate |

Măsurat pe schema curentă: **nicio tabelă din F0 nu referă un depozit, și niciuna n-ar trebui să
piardă o coloană ca să poată referi unul.** `Item` nu ține stoc; stocul este F4.

## Ce nu are încă verificare mecanică

Regula §4 nu are gardian. Un app gol pentru o fază viitoare ar trece astăzi de toate suitele:
gardianul de dependențe îl raportează `D0` doar dacă stratul lui nu e declarat, iar
`masterdata/warehouses` **ar fi** într-un strat declarat.

Se adaugă odată cu acest ADR: `backend/tests/architecture/test_no_empty_apps.py`. Verifică forma pe
care regula o interzice — un app instalat care nu definește niciun model și nu are niciun modul de
serviciu, view sau task. Nu e o dovadă completă că regula se respectă; este dovada că forma exactă
pe care o interzice nu poate apărea tăcut.
