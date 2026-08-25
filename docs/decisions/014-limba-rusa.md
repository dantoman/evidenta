# ADR-014 — Limba rusă: interfața se amână cu hedge, datele de referință rămân deschise

- **Status:** Acceptat — decizie de produs, fără conținut contabil
- **Data:** 2026-08-24
- **Decide:** proprietarul proiectului
- **Închide:** `DN-01` (Spec A §11) și `OD-13` **în partea de interfață**. Partea de date de
  referință rămâne deschisă, cu termen în F1
- **Afectează:** F0.7 *(nu îl mai blochează)*, F0.10.3, F1.1 (planul de conturi)

## Context

`DN-01` fusese ridicată ca blocantă pentru F0.7, cu argumentul că denumirile contabile ar avea
nevoie de traduceri stocate, nu doar de fișiere de resurse. Argumentul confunda două cerințe
diferite:

- **(a) Tenantul lucrează în rusă.** Interfața în rusă; denumirile de articole și parteneri le
  tastează el în rusă, în același câmp. Un singur limbaj de lucru, al lui.
- **(b) Ieșire bilingvă.** Același articol apare în română pe un document și în rusă pe altul.

**(a)** este aproape sigur ce cere piața. **(b)** este rar — companii cu clientelă mixtă care vor
factura în limba clientului.

Sub (a), „adăugăm rusa mai târziu" este într-adevăr ieftin: traducere de interfață plus o setare de
limbă pe tenant. **Nicio schimbare de schemă.** Escaladarea inițială a fost greșită.

## Decizie

### Datele introduse de tenant: valoare unică

Articole, parteneri, angajați, conturi create de companie. Ce a tastat utilizatorul, în limba lui.
Partenerii și angajații au oricum denumiri juridice — valoare unică indiferent de limbă.

### Datele de referință livrate de noi: formă cu cheie de limbă

Planul de conturi SNC, unitățile de măsură, codurile fiscale, categoriile. Aici bilingvismul este
inerent chiar sub (a): un contabil care lucrează în rusă vrea denumirile conturilor în rusă, iar
**noi** le furnizăm, nu el.

Denumirea are formă cu cheie de limbă de la început, chiar dacă azi se populează doar `ro`.

**Planul de conturi este cazul scump**, pentru că se instanțiază per companie: dacă instanța
stochează denumirea ca valoare unică și se adaugă rusa peste doi ani, trebuie propagat în fiecare
companie existentă — exact problema din `DNB-03`, pe un al doilea front.

Decizia efectivă de formă (coloană `jsonb`, tabelă de traduceri, sau coloane per limbă) se ia în
**F1.1**, când se proiectează `coa_template_account` și `company_account`. Nu în F0: în F0 nu există
nicio tabelă de date de referință livrate de noi.

### Trei lucruri care se fac acum, cu cost zero

Nu sunt i18n. Devin scumpe dacă lipsesc.

1. **Șirurile de interfață stau în fișiere de resurse de la primul ecran**, niciodată în componente.
   S-ar face oricum pentru consecvență; aici e și hedge-ul. Fără el, „adăugăm rusa" înseamnă
   parcurgerea a 200 de componente. → `C32`, F0.10.3.
2. **Setarea de limbă există pe tenant și pe utilizator din F0**, chiar dacă are o singură valoare
   posibilă. Este un câmp, nu o funcționalitate. → **deja există**: `tenant.default_locale` și
   `user.locale`, Spec A §1.1 și §1.5. Nimic de făcut.
3. **Colația și căutarea.** Ridicată aici, dar s-a dovedit a fi o problemă distinctă și mai gravă
   decât i18n — vezi [ADR-015](015-colatie-icu.md).

## Ce rămâne deschis

| Ce | Unde | Termen |
|---|---|---|
| Forma denumirilor pentru datele de referință livrate de noi | `DN-01`, restrânsă | F1.1 |
| **(b) Ieșire bilingvă** — factura în limba clientului | `OD-38`, **nou** | nedeterminat |

`OD-38` este **decizie nouă, nu extensie a acesteia.** Merită ținută separat tocmai ca să nu fie
confundată cu „am rezolvat rusa": (b) cere ca fiecare articol să aibă denumire în două limbi
simultan, ceea ce (a) nu cere niciodată.

## Consecințe

- **`DN-01` nu mai blochează F0.7 și nici F0.10.3.** F0.10.3 primește `C32` ca cerință, nu ca
  decizie de așteptat.
- Registrul: `OD-13` se restrânge; apare `OD-38`.
- Spec A §11: `DN-01` trece la „închisă în partea de interfață, deschisă pentru datele de referință".
- Spec B §2: `coa_template_account.name_ro` și `company_account.name_ro` se marchează ca formă
  provizorie, de fixat la F1.1 împreună cu decizia de aici.

## Surse

- Spec A §11 (`DN-01`), §1.1, §1.5
- `000-open-decisions.md`: `OD-13`
- `_input/evidenta-implementation-spec.md` §2.5 — convenția de limbă
