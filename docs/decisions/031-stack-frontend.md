# ADR-031 — Stack-ul frontend peste React

- **Stare:** Acceptat
- **Data:** 2026-08-25
- **Context:** F0.10.3 — scheletul frontend
- **Închide:** `OD-19`
- **Nu închide:** `OD-35` *(scara de densitate)*. `C21` rămâne activă: spațierea nouă **se ridică,
  nu se inventează.**
- **Decis de:** proprietar

## Ce era deja fixat

`OD-19` intra în această decizie deja restrânsă. Grila de date este `ADR-001` — `DataGrid` și
`EntryGrid`, peste `@tanstack/react-table`, cu import direct interzis prin ESLint (`C16`).
Componentele sunt `ADR-009` — shadcn **copiat**, nu dependență (`C23`). Rămâneau starea, HTTP-ul,
rutarea, i18n și formatarea pentru RM.

## Decizia

```
@tanstack/react-query   starea de server
react-router            rutare
fetch + înveliș subțire HTTP; ridică erori după codul stabil din C10
Intl (ro-MD)            un singur modul de formatare (C18)
fișiere de resurse      șiruri, fără bibliotecă i18n (C32, ADR-014)
```

**Fără bibliotecă de stare globală.** Nu din minimalism: într-un ERP contabil aproape toată starea
**este stare de server** — solduri, documente, jurnale, nomenclatoare. Un store global devine a doua
sursă de adevăr pentru aceleași date, iar cele două diverg exact în ecranele unde diferența se
citește ca un sold greșit. `react-query` deja ține cache-ul, invalidarea și retry-ul; ce rămâne
—filtrul curent al unei grile, pasul unui formular — este stare locală de componentă.

Dacă apare stare globală reală, se adaugă atunci, cu un caz concret. Ordinea contează: nevoia
întâi, biblioteca după.

**`fetch`, nu axios.** Învelișul are un singur lucru de făcut care contează: să transforme un
răspuns de eroare în o excepție care poartă `code`-ul stabil din `C10`, nu mesajul. Un client care
ar ramifica pe text s-ar rupe la prima reformulare, iar reformulările sunt cel mai ieftin lucru din
produs. Asta e vreo treizeci de linii; o dependență în plus n-ar scurta-o.

**`Intl`, într-un singur modul.** `C18` cere formatarea numerică și monetară printr-un singur loc,
și spune de ce: acesta este strat de **afișare**, iar precizia și rotunjirea de calcul stau pe
server (vezi și `ADR-029`, `F0.9`). `Intl.NumberFormat('ro-MD')` acoperă separatorii și moneda fără
bibliotecă. Cifrele tabulare din `C27` sunt token, aplicat de grilă.

**Fișiere de resurse, fără bibliotecă i18n.** `C32` cere șirurile în fișiere de resurse **de la
primul ecran** — iar `ADR-014` amână rusa ca decizie de produs, nu o exclude. Un fișier de resurse
costă nimic acum și face ca „adăugăm rusa" să coste o traducere. O bibliotecă i18n cu plurale,
interpolare și încărcare pe rută rezolvă probleme pe care nu le avem încă; se adaugă când există al
doilea limbaj real, nu înainte.

**`react-router`, nu TanStack Router.** Ambele funcționează. `react-router` s-a ales pentru că
rutarea aici este simplă — subdomeniul decide tenantul (`C8`), deci nicio rută nu poartă vreodată un
identificator de tenant — iar avantajul principal al alternativei, rutele tipate cu încărcare de
date, se suprapune peste ce face deja `react-query`.

## Ce rămâne interzis, ca înainte

- niciun ecran nu importă `@tanstack/react-table` direct (`C16`);
- nu apare o a treia componentă de grilă (`C17`);
- totalurile vin de la server (`C19`), exporturile se generează pe server (`C20`), documentele
  tipărite nu se randează din React (`C22`);
- CSS scris de mână doar în `DataGrid` și `EntryGrid` (`C25`);
- **spațierea nouă se ridică, nu se inventează** — `OD-35` e deschisă, iar `C21` e activă de acum.
