# ADR-063 — Coliziunea se decide după cine garantează cheia; UID-ul SFS e idempotență, nu deduplicare

- **Status:** **Acceptat** — decizie tehnică sub regimul [ADR-002](002-guvernanta-deciziilor.md).
  Premisa de practică din §3 (seria reluată la an nou, referința bancară goală) e a proprietarului în
  rol de contabil practicant ([ADR-010](010-contabilul-practicant.md))
- **Data:** 2026-08-30
- **Decide:** proprietarul proiectului
- **Închide:** `DNB-11` din `../specs/spec-b-accounting.md` §10.2
- **Afectează:** `F2.A2` (`purchase_document`), `F2.A4` (linia de extras), `F2.A7` (importul
  e-Factura), `F2.B4` (rularea de salarii), `F2.A1` (factura emisă)
- **Legate:** [ADR-022](022-numerotare.md), [ADR-038](038-vocabularul-de-evenimente.md), `R19`, `R20`

## 1. Context

Spec B §10.2 propune cinci chei naturale de business și pune, pentru fiecare, aceeași întrebare: ce
face sistemul la coliziune — **refuz**, sau **semnalare ca posibil duplicat, cu decizie umană**.
Specul observă că a doua e mai realistă, dar cere o stare pe document și un flux de rezolvare.

**Nu e o întrebare, sunt cinci.** Rămân cinci și aici; ce le ordonează e o singură axă.

## 2. Corecție la Spec B §10.2: tabelul amestecă doi invarianți

Rândul `Document e-Factura → (company_id, sfs_document_uid)` **nu e deduplicare**. Același UID de
două ori înseamnă **același document**, nu două documente de comparat — deci `R19` (idempotență), nu
`R20` (deduplicare). Sunt invarianți diferiți, cu locuri diferite: `R19` stă pe evenimentul contabil,
`R20` pe documentul sursă.

Cazul real de deduplicare al e-Facturii — *aceeași factură ajunge prin e-Factura și e introdusă
manual* — e prins de cheia **documentului furnizorului**, nu de UID. Docstring-ul lui
`purchase_document` spune deja distincția corect, în cod; tabelul specului o pierde.

**Consemnat ca fapt, nu ca interpretare:** Spec B §10.2 pune într-un singur tabel două întrebări
care se rezolvă în două locuri. Rândul UID-ului migrează la idempotență.

## 3. Axa: cine garantează cheia

Nu „cât de probabilă e coliziunea", ci **cine răspunde pentru unicitate**. Consecința e directă: o
coliziune pe o cheie pe care o garantăm noi e un **defect al nostru** și trebuie să cadă; una pe o
cheie garantată de un terț poate fi **legitimă** și nu are voie să blocheze introducerea.

Premisele de practică, ale proprietarului: un furnizor poate relua seria la an nou; o bancă poate
trimite referință goală sau reciclată.

## 4. Decizie

| Tip de document | Cheia | Cine garantează | La coliziune |
|---|---|---|---|
| Factură emisă | `(company_id, document_type, series, number)` | **noi** — numerotarea, [ADR-022](022-numerotare.md) | **refuz** |
| Rulare de salarii | `(company_id, period_id, run_type)` | **noi** | **refuz** |
| Document furnizor | cheia implementată, §5 | furnizorul | **„suspectat duplicat", decizie umană** |
| Linie de extras bancar | `(company_id, bank_account_id, statement_date, bank_reference)` | banca | **„suspectat duplicat", decizie umană** |
| Document e-Factura | `(company_id, sfs_document_uid)` | SFS | **nu e cheie de deduplicare** — `R19`, a doua sosire a aceluiași UID e același document |

Semnalarea cere o stare pe document (`suspected_duplicate`) și un flux de rezolvare, cum spune
specul. Ambele se construiesc în sarcina care ajunge prima la o cheie garantată extern.

## 5. Refuzul e implicitul reversibil, și de aceea `DNB-11` blochează mai puțin decât părea

**Asimetria decide ordinea de construcție:**

- **refuz → semnalare e ușor:** se scoate un `UNIQUE`, o migrare.
- **semnalare → refuz e greu:** până atunci tabela poate ține deja rânduri care încalcă
  constrângerea, iar `UNIQUE` nu se mai poate adăuga fără rezolvare manuală, rând cu rând.

Deci, **până când fiecare sarcină ajunge la cheia ei, refuzul rămâne implicitul** — direcția din care
se poate ieși. `F2.A4` și `F2.A7` se construiesc cu `UNIQUE` și se relaxează la semnalare când
sarcina lor ajunge acolo; nu așteaptă. Costul acceptat: primul extras real poate fi neimportabil
până la relaxare — ceea ce nu e pe drumul critic, fiindcă extrasul real e blocat oricum pe `OD-27`.

**Măsurat la 2026-08-30, cu o diferență de consemnat:** `purchase_document` refuză azi, prin
`UNIQUE (company, partner_id, supplier_document_number, supplier_document_date)`. Cheia
**implementată nu e cea propusă în Spec B**: folosește `partner_id` în loc de `supplier_idno` și
n-are `series`. Rămâne cum e până la `F2.A2`, care o mută la semnalare și decide atunci dacă seria
furnizorului e o coloană proprie.

## 6. Consecințe

- **Devine posibil:** `F2.A4` și `F2.A7` pot începe fără să aștepte decizia pe cheia lor — implicitul
  e numit și e cel reversibil.
- **Devine imposibil:** o coliziune tăcută pe o cheie pe care o garantăm noi; și adăugarea unei stări
  `suspected_duplicate` fără flux de rezolvare, fiindcă o stare fără ieșire e un document blocat.
- **De modificat ca urmare:** `DNB-11` trece în „Închise"; Spec B §10.2 primește corecția din §2;
  `09-f2-backlog.md` — `F2.A4`, `F2.A7` și tabelul de blocaje.
- **Se verifică, per sarcină:** același extras de două ori → zero linii noi (`R20`); același document
  furnizor pe două căi → un document, cu semnalare; același `sfs_document_uid` de două ori → aceeași
  înregistrare, prin idempotență (`R19`).

## 7. Surse

- `../specs/spec-b-accounting.md` §10.2 (cele cinci chei propuse, `DNB-11`).
- `CLAUDE.md` `R19`, `R20`; [ADR-022](022-numerotare.md) (numerotarea garantată de noi).
- Măsurat în cod la 2026-08-30: `operations/purchases/models.py` (`UNIQUE` pe cheia furnizorului,
  cu docstring-ul care distinge corect `R19` de `R20`).
- Practica din RM (seria reluată la an nou, referința bancară goală): proprietarul, în rol de
  contabil practicant, 2026-08-30.
