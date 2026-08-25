# ADR-006 — Stornoul are două date distincte

- **Status:** Acceptat — decizie tehnică, sub regimul `ADR-002`
- **Data:** 2026-08-24
- **Decide:** proprietarul proiectului
- **Închide:** partea structurală a lui `DNB-09`. Politica de alegere a perioadei rămâne în
  [ADR-007](007-reversal-period.md), `Propus`
- **Afectează:** F1.2 (`journal_entry`), F1.5, F1.8, declarațiile rectificative din F2

## Context

`DNB-09` întreba în ce perioadă se înregistrează stornoul. Analizând opțiunile a ieșit la iveală
ceva independent de răspuns: **modelul curent nu poate exprima corecția, oricare ar fi politica.**

`journal_entry` are o singură dată — `accounting_date`. Pentru o înregistrare obișnuită ea răspunde
la două întrebări deodată: *unde se postează* și *la ce perioadă se referă*. Pentru un storno, cele
două întrebări au răspunsuri diferite ori de câte ori corecția nu cade în perioada originală.

Consecința practică: fără distincție, **declarația rectificativă nu se poate genera**, pentru că nu
se știe ce raportare a fost afectată. Se poate afla numai urmărind `reverses_entry_id` până la
înregistrarea originală și citind perioada ei — ceea ce funcționează pentru un storno simplu, dar
nu pentru un lanț de corecții și nici pentru înregistrări de ajustare care corectează o perioadă
fără să storneze o înregistrare anume.

## Opțiuni evaluate

1. **O singură dată, perioada corectată dedusă prin `reverses_entry_id`.** Fără schimbare de schemă.
   Nu acoperă ajustările care nu stornează o înregistrare anume; interogarea „ce corecții afectează
   perioada X" devine o traversare recursivă pe cea mai mare tabelă din sistem.
2. **Două date pe înregistrare:** `accounting_date` (unde se postează) și o referință explicită la
   perioada corectată. O coloană și un index; interogarea devine directă.
3. **Tabelă separată de corecții**, care leagă înregistrarea de corecție de perioada afectată.
   Normalizează un caz rar, dar adaugă un `JOIN` pe fiecare raport care trebuie să știe dacă o
   perioadă a fost corectată.

## Decizie

**Opțiunea 2.** Pe `journal_entry`:

| Câmp | Tip | Semnificație |
|---|---|---|
| `accounting_date` | date | **unde se postează** — determină perioada în care intră înregistrarea |
| `corrects_period_id` | uuid NULL, REFERENCES `period` | **la ce perioadă se referă corecția** |

Reguli:

- `corrects_period_id IS NULL` pentru înregistrările obișnuite.
- `corrects_period_id IS NOT NULL` este obligatoriu când `entry_type IN ('reversal','adjustment')`
  și perioada corectată diferă de cea în care se postează.
- `CHECK (corrects_period_id IS NULL OR entry_type IN ('reversal','adjustment'))`.
- Index `(company_id, corrects_period_id) WHERE corrects_period_id IS NOT NULL` — susține
  întrebarea „ce corecții afectează perioada X", care este exact interogarea din care se generează
  declarația rectificativă.

## Consecințe

**Devine posibil:**

- generarea declarației rectificative pornind de la perioada afectată, nu de la lanțul de stornouri
- raportul „perioada X a fost corectată ulterior, iată cu ce" — necesar pentru drill-down pe o
  perioadă închisă, care altfel arată o stare care nu mai e adevărată
- ajustări care corectează o perioadă fără să storneze o înregistrare anume

**Devine obligatoriu:**

- fiecare raport pe perioadă închisă trebuie să declare explicit dacă include sau exclude corecțiile
  ulterioare. Ambele vederi sunt legitime; **absența alegerii** este defectul. Regula intră în
  F1.8, la rapoartele contabile

**Ce trebuie modificat:**

- Spec B §1.2 — câmpul și constrângerile
- Spec B §9 — structura stornoului
- backlog F1.2 — criteriul de terminare include indexul și constrângerea

**Ce se verifică automat:**

- un storno postat într-o perioadă diferită de cea originală are `corrects_period_id` setat
- interogarea „corecții care afectează perioada X" folosește indexul dedicat, nu o traversare
- `accounting_date` și perioada corectată sunt tratate distinct în teste — un test care le
  confundă trece și pentru cazul simplu, și ascunde exact defectul pe care ADR-ul îl previne

## Surse

- Spec B §9.3 (`DNB-09`), §1.2
- `_input/evidenta-implementation-spec.md` §1.2, invariantul 12
