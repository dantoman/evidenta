# ADR-007 — Perioada în care se postează stornoul

- **Status:** **Propus** — dar **nu** din lipsa unui contabil: `OD-32` s-a închis prin
  [ADR-010](010-contabilul-practicant.md). Rămâne propus pentru că cele trei întrebări de mai jos
  nu au încă răspuns. Sunt acum întrebări către proprietar, în rolul de contabil practicant
- **Data:** 2026-08-24
- **Propune:** proprietarul proiectului
- **Închide, la acceptare:** `DNB-09` (Spec B §9.3)
- **Afectează:** F1.2, F1.5, F1.8, declarațiile rectificative din F2

## Context

O eroare descoperită azi poate privi o perioadă deschisă sau una închisă. Unde se înregistrează
corecția determină ce arată rapoartele istorice și ce se depune la instituții.

Partea structurală — stornoul are nevoie de două date distincte — este independentă de răspuns și a
fost acceptată separat, în [ADR-006](006-reversal-two-dates.md). ADR-ul de față decide **doar
politica**.

## Opțiuni evaluate

1. **Întotdeauna în perioada înregistrării originale.** Istoria devine corectă „ca și cum". Cere
   redeschiderea perioadei dacă e închisă și schimbă rapoarte deja depuse.
2. **Întotdeauna în perioada curentă deschisă**, cu referință la cea originală. Nu atinge nimic
   depus. Perioada curentă conține corecții ale trecutului, ceea ce e normal contabil.
3. **După starea perioadei:** în cea originală dacă e deschisă, altfel în cea curentă. Cel mai
   apropiat de practică; același gest produce rezultate diferite după o stare pe care utilizatorul
   nu o are mereu în față.

## Decizie propusă

**Opțiunea 3**, pentru că este în mare parte determinată de invarianții deja acceptați:

| Situație | Unde se postează | `corrects_period_id` |
|---|---|---|
| Eroare descoperită în perioadă **deschisă**, aferentă acelei perioade | aceeași perioadă | `NULL` |
| Eroare descoperită după **închiderea** perioadei | perioada curentă deschisă | perioada originală |

Justificarea celui de-al doilea rând nu este o preferință: invariantul 12 interzice postarea într-o
perioadă închisă, iar refuzul se face la nivel de motor, nu de interfață. Stornoul nu este o
excepție de la R12 — dacă ar fi, R12 nu ar mai însemna nimic.

Pentru ca „același gest, rezultate diferite" să nu surprindă, interfața arată **înainte de
confirmare** în ce perioadă va intra corecția și de ce.

## Cele trei întrebări care țin ADR-ul în `Propus`

Niciuna nu se deduce din documentele de intrare și niciuna nu se ghicește. Toate trei sunt
răspunsabile acum, de proprietar în rolul de contabil practicant:

1. **Permite practica din Republica Moldova redeschiderea unei perioade închise înainte de
   depunerea declarației aferente?** Dacă da, apare un al treilea caz — „închisă, dar nedeclarată" —
   care s-ar posta în perioada originală după redeschidere. Mecanismul de redeschidere există deja
   (Spec B §6.2, cu permisiune specială și urmă în audit); întrebarea este dacă e legitim să fie
   folosit astfel.
2. **După depunerea declarației, corecția impune obligatoriu declarație rectificativă**, sau există
   un prag sub care se corectează în perioada curentă fără rectificare?
3. **Stornoul unei perioade `locked`** — starea folosită după depunerea situațiilor financiare
   anuale — urmează aceeași regulă, sau are tratament propriu?


## Consecințe la acceptare

- **De modificat:** Spec B §9.3 înlocuiește blocul `DNB-09`; backlog F1.2 și F1.5 primesc criteriul
  de terminare corespunzător.
- **Se verifică automat:** storno în perioadă deschisă → aceeași perioadă, `corrects_period_id`
  `NULL`; storno după închidere → perioada curentă, `corrects_period_id` setat; încercarea de a
  posta un storno direct într-o perioadă închisă → refuzată de motor (R12), nu redirecționată tăcut.
- **Până la acceptare:** F1.2 poate fi implementat pe baza lui ADR-006 (structura), fără politica
  de aici. Serviciul care alege perioada rămâne nescris.

## Surse

- Spec B §9.3 (`DNB-09`), §6.2
- `CLAUDE.md` R12, R14
- [ADR-006](006-reversal-two-dates.md), [ADR-002](002-guvernanta-deciziilor.md)
