# ADR-067 — Amendament la ADR-065: contractul de muncă e cap de serie, nu stare

- **Status:** **Acceptat** — **decizie de domeniu** juridic, semnată de proprietar în rol de contabil
  practicant ([ADR-010](010-contabilul-practicant.md), sub [ADR-002](002-guvernanta-deciziilor.md))
- **Data:** 2026-08-30
- **Decide:** proprietarul proiectului
- **Amendează:** [ADR-065](065-schema-salarizarii.md) §4 și §11 — restul rămâne neschimbat
- **Închide:** —
- **Afectează:** `operations/payroll` (`employment_contract`), `F2.B1`
- **Legate:** [ADR-065](065-schema-salarizarii.md), [ADR-066](066-rezerva-e-decizie-deschisa.md)
  (regula care a cerut ca declanșatorul `F2.X2 (k)` să fie urmărit)

> **REZERVĂ NEATINSĂ (`OD-85`):** acest amendament atinge §4 și §11 din ADR-065 — nu tabelul de
> tarife CAS, unde stă rezerva pe anexa nr. 1 la Legea nr. 489/1999.

## 1. Ce se schimbă

ADR-065 a fixat `employment_contract` ca **entitate cu stare** — salariul, timpul de muncă, data
începerii și a încetării, funcția, destinația costului — și a consemnat explicit că lista e *derivată
din ce consumă calculul, nu transcrisă dintr-un act*, cu declanșator `F2.X2 (k)`.

Declanșatorul a fost tras. Cercetarea
([`f2-x2-k-contractul-si-irm19.md`](../_input/cercetare/f2-x2-k-contractul-si-irm19.md)) a găsit că
**orice schimbare a oricărei clauze din art. 49 alin. (1) din Codul muncii cere act adițional
semnat**, anexat la contract și parte integrantă din el.

> **Deci contractul nu e o stare care se actualizează. E capul unei serii.** Un
> `employment_contract` scris pe loc peste valoarea veche **nu poate demonstra conformitatea**: nu
> poate arăta ce clauză era în vigoare la o dată trecută, nici că schimbarea a fost consimțită.

**Forma:** `employment_contract` poartă clauzele la semnare; `employment_contract_amendment` poartă,
per act adițional, ce s-a schimbat și de când. „Ce era în vigoare la data D" se citește parcurgând
seria — nu dintr-o coloană.

## 2. De ce e amendament și nu sarcină — regula, de folosit de acum înainte

> **O sarcină poate adăuga câmpuri unei entități pe care ADR-ul o descrie. Nu poate introduce o
> entitate pe care ADR-ul nu o cunoaște — cu atât mai puțin când aceasta schimbă natura uneia
> existente.**

Cele două constatări ale aceleiași cercetări se despart exact pe linia asta, și e util că se despart:

- **Data și numărul ordinului angajatorului** — de care curge termenul de 10 zile lucrătoare al
  IRM19 — sunt **câmpuri** pe o entitate care se construiește oricum. Intră în `F2.B1` ca cerință a
  sarcinii. ADR-065 §11 numise declanșatorul; se completează, nu se contrazice.
- **Istoricul de acte adiționale** e **entitate nouă**, iar efectul ei e că schimbă ce spunea ADR-065
  despre contract. Aici se oprește ce poate face o sarcină.

## 3. A patra apariție a aceluiași tipar

Contractul devine a patra stare datată descoperită independent, după scutirile de impozit (ADR-065
§5), capabilitatea cu dată efectivă (`R25`) și categoria de plătitor CAS (ADR-065 §3.1).

**Nu se generalizează aici** — regula implicită de proiectare e deschisă ca `OD-89`, împreună cu
`OD-83`, al cărui caz e unul particular al aceleiași proprietăți. Acest ADR schimbă o entitate, nu
instituie o convenție.

## 4. Consecințe

- **Devine posibil:** răspunsul la „ce clauză era în vigoare în martie", care e ce cere `R18` de la
  orice recalculare a unei luni trecute, și ce cere art. 49 de la o dovadă de conformitate.
- **Devine imposibil:** un contract actualizat pe loc.
- **De modificat ca urmare:** `F2.B1` primește entitatea și câmpurile ordinului; ADR-065 §4 și §11 se
  citesc prin acest amendament.
- **Nu se schimbă** nimic altceva din ADR-065 — nici asimetria din §2, nici forma postării din §8,
  nici rolurile din §7.

## 5. Surse

- Codul muncii nr. 154/2003 **art. 49 alin. (1)**, cele 19 clauze, și modelul de contract din
  Convenția colectivă (nivel național) nr. 4/2005 pct. 20–21 — prin
  [`f2-x2-k-contractul-si-irm19.md`](../_input/cercetare/f2-x2-k-contractul-si-irm19.md) §2.2, §3.2,
  §4.3. **Textul art. 49 vine dintr-o consolidare terță oprită în 2019**, cu lit. i) semnalată ca
  schimbată ulterior și actul modificator neidentificat; consolidarea e citată ca atare în dosar.
- [ADR-065](065-schema-salarizarii.md) §4, §11.
- Instrucțiunea proprietarului, 2026-08-30.
