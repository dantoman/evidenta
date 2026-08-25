# ADR-002 — Guvernanța deciziilor: cine aprobă ce

- **Status:** Acceptat
- **Data:** 2026-08-24
- **Decide:** proprietarul proiectului
- **Închide:** `OD-33` din `000-open-decisions.md`
- **Afectează:** procesul de ADR, `CLAUDE.md`, orice regulă care spune „aprobat"

## Context

`OD-33` cerea să se stabilească cine aprobă un ADR, cine aprobă o excepție de la un invariant și
cine aprobă un plan de arhivare. Fiind nedecisă, a blocat de trei ori aceeași mișcare: o decizie
tehnică luată în conversație nu putea trece în `Acceptat`, deci regulile care decurg din ea nu
puteau intra în `CLAUDE.md`, deci sesiunea următoare le-ar fi redeschis.

Proiectul are un singur decident tehnic. Ceremonia de aprobare potrivită pentru o echipă de
douăzeci de oameni ar fi aici pur cost.

Există însă o clasă de decizii pe care decidentul tehnic **nu are cum** să le valideze, oricât de
convins ar fi: cele cu conținut contabil, fiscal sau juridic. `CLAUDE.md` §4 o spune deja pentru
regulile fiscale („nu se deduc din memorie"); ADR-ul de față extinde principiul la aprobare.
Contabilul practicant nu este confirmat încă (`OD-32`).

## Opțiuni evaluate

1. **Proprietarul aprobă tot.** *Avantaje:* zero fricțiune, nicio decizie nu stagnează.
   *Dezavantaje:* o cotă, un prag sau un termen greșit intră în `Acceptat` cu aceeași ușurință ca o
   alegere de bibliotecă, iar `Acceptat` devine un semnal fără conținut. *Cost de schimbare:* mare
   — decizii contabile greșite se descoperă la prima declarație, nu la review.
2. **Proprietarul aprobă, cu co-semnătură obligatorie pentru conținut contabil, fiscal sau
   juridic.** *Avantaje:* păstrează viteza acolo unde decizia e tehnică și pune o barieră exact
   unde competența lipsește; face vizibil, prin ADR-uri blocate în `Propus`, costul real al
   absenței contabilului. *Dezavantaje:* o parte din ADR-uri rămân `Propus` perioade lungi.
   *Cost de schimbare:* mic.
3. **Comitet sau consens de echipă.** *Avantaje:* niciunul la dimensiunea actuală.
   *Dezavantaje:* echipa nu există. *Cost de schimbare:* —

## Decizie

**Opțiunea 2.**

- **Aprobă:** proprietarul proiectului. Un ADR trece din `Propus` în `Acceptat` la confirmarea lui,
  consemnată în ADR prin `Status` și `Data`.
- **Excepția — co-semnătură.** Un ADR cu conținut **contabil, fiscal sau juridic** cere și semnătura
  contabilului practicant. Până când există unul (`OD-32`), astfel de ADR-uri rămân `Propus`
  indiferent de gradul de convingere. Aceeași regulă acoperă excepțiile de la invarianții din
  secțiunea 1.3 a lui `CLAUDE.md` și planurile de arhivare cerute de `C5`.
- **Criteriul de clasificare:** dacă ADR-ul afirmă ceva despre *cum funcționează contabilitatea,
  fiscalitatea sau dreptul* — cote, praguri, termene, tratament contabil, retenție legală, formate
  de raportare — este conținut contabil. Dacă afirmă ceva despre *cum e construit software-ul*, este
  tehnic. Ambiguitatea se rezolvă în favoarea co-semnăturii.
- **Regulile obligatorii din `CLAUDE.md` se adaugă exclusiv din ADR-uri `Acceptat`.** O regulă
  apărută direct în `CLAUDE.md`, fără ADR, nu are autoritate și se șterge la prima revizuire.

## Consecințe

- Devine posibil: închiderea deciziilor tehnice în ritmul conversației, fără ceremonie.
- Devine imposibil: strecurarea unei afirmații contabile într-un ADR tehnic ca să evite bariera.
- De modificat ca urmare: `OD-33` trece în secțiunea „Închise"; `ADR-001`, fiind pur tehnic, trece
  în `Acceptat`; `CLAUDE.md` primește secțiunea de convenții frontend care decurge din el.
- Efect secundar util: numărul de ADR-uri blocate în `Propus` din lipsa contabilului devine măsura
  vizibilă a riscului marcat **critic** în `OD-32`.
- Nu se verifică automat. Este regulă de proces, nu de cod.

## Surse

- `000-open-decisions.md`: `OD-32` (contabil practicant), `OD-33` (guvernanța).
- `CLAUDE.md` §1.3, §4, `C5`.
- `decisions/README.md` — „Când se scrie un ADR", „Ce nu se face".
- Conversație 2026-08-24.
