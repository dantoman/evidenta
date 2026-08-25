# ADR-029 — Dimensiunile analitice: listă închisă plus cinci sloturi generice

- **Stare:** Acceptat
- **Data:** 2026-08-25
- **Context:** F0.7.6 — dimensiunile se consemnează înainte ca linia de jurnal să existe
- **Închide:** `DNB-02` (Spec B §1.7)
- **Decis de:** proprietar

## Problema

Spec B §1.7 pune zece dimensiuni ca **coloane** pe `journal_line`, nu ca tabelă separată, cu
motivul scris acolo: indexarea directă — `(company_id, partner_id, accounting_date)` **este** indexul
care produce fișa partenerului — și evitarea unui `JOIN` pe cea mai mare tabelă din sistem. Prețul
declarat: zece coloane majoritar `NULL` și **o listă închisă**.

Lista închisă e problema. Un client care vrea „filială" sau „linie de business" ca axă de raportare
nu are unde. Spec B enumeră trei variante; `DNB-02` întreabă care.

## Ce s-a respins, și de ce

**(A) Lista rămâne închisă, cererile se rezolvă prin subconturi.** Este soluția clasică din 1C și
are avantajul real că e familiară contabilului venit de acolo. Se respinge pentru un motiv care nu e
estetic: **două axe simultane produc produsul cartezian al conturilor.** „Filială × centru de cost"
peste zece conturi de creanțe înseamnă un plan de conturi care crește multiplicativ, iar fiecare
companie își inventează propria convenție de codificare. Peste doi ani, două companii ale aceluiași
holding nu mai pot fi consolidate fără o hartă scrisă de mână.

**(B) `jsonb custom_dimensions`, indexabil `GIN`.** Flexibilă fără limită de sloturi, și respinsă
pentru exact ce spune Spec B: **nu se poate impune nici obligativitatea, nici integritatea.**
Mecanismul de obligativitate există deja și stă pe cont — `company_account.required_dimensions`
(§2.4), iar postarea într-un cont care cere `partner` fără `partner_id` este refuzată de motor.
Într-un `jsonb`, „contul 2114 cere filiala" nu se mai poate impune în bază, iar `balti` și `Balti`
devin două filiale. Într-un sistem unde `R11` și `R12` se impun în bază tocmai fiindcă serviciul
poate fi ocolit, o dimensiune apărată doar de cod este o dimensiune neapărată.

## Decizia

**(C) Lista închisă rămâne, și se adaugă cinci sloturi generice.**

```
journal_line
    partner_id, item_id, employee_id, contract_id, warehouse_id,
    project_id, department_id, cost_center_id, asset_id,
    production_order_id                      -- lista închisă, uuid NULL
    dim_1_id … dim_5_id                      -- sloturi generice, uuid NULL
```

Semnificația sloturilor se configurează **per companie**:

```
company_dimension
    (company_id, slot)              slot ∈ {1..5}
    name                            „Filială", „Linie de business"
    value_source                    de unde vin valorile permise
    UNIQUE (company_id, slot)
    UNIQUE (company_id, name)
```

Trei consecințe care fac varianta să funcționeze:

1. **Obligativitatea se impune la fel ca la restul.** `company_account.required_dimensions` numește
   un slot ca pe orice altă dimensiune; motorul refuză postarea fără el. Nimic nou de inventat.
2. **Indexarea este normală.** `(company_id, dim_1_id, accounting_date)` e un index B-tree obișnuit,
   ca cel de partener. Fără `GIN`, fără operatori de containment în planul de execuție al celei mai
   mari tabele din sistem.
3. **Obiecția din Spec B — „rapoartele devin ilizibile fără metadate" — cade**, fiindcă tabela de
   metadate nu e un cost adăugat de varianta asta: interfața are nevoie de ea oricum, ca să pună o
   etichetă pe o coloană și o listă de valori într-un câmp.

## Ce rămâne cunoscut și acceptat

**Cinci sloturi sunt o limită, nu o soluție generală.** Al șaselea client care cere o a șasea axă
proprie va cere o migrare. Este alegerea deliberată: limita e vizibilă și numărabilă, spre deosebire
de `jsonb`, unde limita nu există și în schimb dispare obligativitatea.

**Numărul cinci nu e măsurat.** Nu există încă un client real cu cerințe de dimensiuni proprii, deci
nu e nici o distribuție de citit. Se ridică la prima companie care cere a șasea, nu se ajustează
preventiv.

## Ce nu se construiește acum

Nimic. `F0.7.6` este **consemnare, nu implementare** — linia de jurnal se creează la `F1.2`, iar
`company_dimension` odată cu ea. Ce face acest ADR este să fixeze forma înainte ca prima linie să
existe, fiindcă `journal_line` este tabelă append-only de volum mare (`R21`) și adăugarea unei
coloane pe ea, mai târziu, nu mai e o migrare ieftină.
