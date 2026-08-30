# ADR-059 — Linia poartă data înregistrării și scara sumei se impune în bază

- **Status:** **Propus** — răspunsul la întrebarea de model (§2) e **raportat**, nu decis: proprietarul a
  cerut „nu decide — raportează"; codul de aici e implementat pe răspunsul găsit („nu există motiv
  contabil") și pe instrucțiunea „impune structural în loc să verifici" (2026-08-30), iar trecerea în
  `Acceptat` e confirmarea proprietarului că răspunsul e cel corect. Decizie tehnică sub regimul
  [ADR-002](002-guvernanta-deciziilor.md)
- **Data:** 2026-08-30
- **Decide:** proprietarul proiectului
- **Închide:** —
- **Afectează:** `journal_line` (trigger, CHECK), `journal_formula` (CHECK), invariantul 3 al
  motorului (`posting.invariants`), nota manuală (`posting.services.manual`), rapoartele F1.8
- **Legate:** [ADR-039](039-valuta-si-perioade.md) §9, [ADR-032](032-cheia-de-partitionare.md),
  [ADR-037](037-conventii-de-platforma.md) §3.2, [ADR-048](048-formula-si-sloturile-tipizate.md),
  [ADR-053](053-tinta-de-performanta.md)

## 1. Context

Revizuirea contabilă a rapoartelor F1.8 a găsit trei avertismente cu o singură rădăcină: fișa
contului data un rând după linia cea mai timpurie, registrul și drill-down-ul după antet, iar Cartea
Mare putea tăia o notă în două la marginea ferestrei. Toate trei există fiindcă motorul cerea liniilor
doar **aceeași perioadă** cu antetul, iar nota manuală lăsa o linie să poarte altă zi din aceeași lună
(`ManualLine.accounting_date`, suprascriibil per linie).

Un al patrulea punct, marcat decizie deschisă: `amount_scale` e două zecimale (ADR-037 §3.2, aprobat),
`journal_line.debit/credit` și `journal_formula.amount` sunt `numeric(20,4)` fără nicio constrângere
la două. Azi nu e defect. Devine unul în ziua în care se scrie o sumă cu patru zecimale: exporturile
rotunjesc rândurile și totalurile independent, coloana nu mai dă totalul, și nimic nu semnalează —
spre deosebire de `unassigned`, care e o diferență cinstită între două interogări. A zecea apariție a
familiei „proprietate presupusă în amonte, neimpusă în schemă, consumator în aval care se sparge tăcut".

## 2. Întrebarea de model, pusă înainte de orice constrângere

**Are divergența de dată pe linii un motiv contabil?** Nu. ADR-039 §9 definește
`accounting_date` ca *data postării* — „unde intră în registru" — și o dă liniei fiindcă linia e
tabela partiționată (ADR-032), nu fiindcă o linie s-ar posta în ziua ei. Data economică — când s-a
produs faptul — are coloana ei, `document_date`, care rămâne a liniei. O înregistrare contabilă are o
dată; două date pe aceeași înregistrare nu înseamnă nimic în niciun registru pe care îl citește un
control. Permisiunea era un rest al proiectării linie-cu-linie, nu o cerință.

## 3. Opțiuni evaluate

1. **Reconciliere în rapoarte** — fiecare raport alege data liniei sau a antetului și spune care.
   *Dezavantaj:* trei rapoarte, trei alegeri, și registrul rămâne capabil să conțină ce niciunul nu
   poate reprezenta consecvent. *Cost:* crește cu fiecare raport.
2. **Invariantul în motor, atât** — refuz cu cod, fără nimic în bază. *Dezavantaj:* importul 1C și
   migrările de date nu trec prin motor; exact acolo apar rândurile care nu respectă ce presupune tot
   restul. Aceeași obiecție pe care Spec B §1.6 o face verificării echilibrului doar în serviciu.
3. **Invariantul în motor și în bază; scara la fel** — *aleasă*.

## 4. Decizia

1. **O linie poartă data înregistrării ei.** Invariantul 3 devine egalitate, nu fereastră:
   `posting.line_date_differs` în motor; `journal_line_carries_the_entry_date` (`BEFORE INSERT`,
   `0062`) în bază, a doua barieră, ca `journal_entry_needs_open_period`. Nota manuală refuză la
   payload o linie care numește altă `accounting_date` decât a notei; `document_date` rămâne liber.
2. **Suma postată are două zecimale, în bază.** `journal_line_amount_scale`
   (`debit = round(debit, 2) AND credit = round(credit, 2)`) și `journal_formula_amount_scale`.
   Coloana rămâne `numeric(20,4)` — lățimea de stocare din Spec B §1.3 nu se schimbă; ce se scrie în
   ea poartă două. Nota manuală refuză a treia zecimală cu cod, înaintea bazei.
3. **Când `accounting.amount_scale` se schimbă, se schimbă și constrângerea** — într-o migrare, care
   e chiar momentul în care cineva se uită la rândurile existente. Faptul că parametrul e
   `provisional` nu amână constrângerea: convenția e aprobată (ADR-037 §3.2), iar o proprietate pe
   care rapoartele o presupun se impune acolo unde se scrie, nu se verifică acolo unde se citește.

## 5. Consecințe

- **Devine posibil:** fișa, registrul, drill-down-ul și Cartea Mare spun aceeași zi pentru același
  document, prin construcție; exportul rotunjește rânduri care sunt deja la scara afișată, deci
  coloana dă totalul.
- **Devine imposibil, asumat:** o notă manuală cu linii pe zile diferite din aceeași lună — se scrie
  ca două note; o sumă cu trei sau patru zecimale în registru — o valoare pe care niciun act nu o
  prescrie și pe care ADR-037 a închis-o.
- **Ce se modifică:** `posting.invariants` (`MixedPeriodError` → `LineDateDiffersError`),
  `posting.services.manual` (`SCALE = 2`, refuzul datei), `ledger.models` (două `CheckConstraint`),
  `0062_line_date_and_scale` (trigger), testele care afirmau permisiunea veche.
- **Ce se verifică automat:** `test_posting_invariants` — o linie cu altă zi din aceeași lună e
  refuzată; `test_manual_entry` — a treia zecimală e refuzată cu cod; `test_reports` — triggerul și
  CHECK-urile refuză pe rândurile scrise pe lângă motor; rotația `0062` în `test_reverse_sql`.

## 6. Surse

- Revizuirea `accounting-reviewer` a F1.8 și instrucțiunea proprietarului, 2026-08-30.
- [ADR-039](039-valuta-si-perioade.md) §9 (`accounting_date` = data postării), [ADR-032](032-cheia-de-partitionare.md),
  [ADR-037](037-conventii-de-platforma.md) §3.2 (două zecimale la sume, aprobat), Spec B §1.3, §1.6.
- `CLAUDE.md` — `R10`, `R11`, `R12`, `C5`, `C30`.
