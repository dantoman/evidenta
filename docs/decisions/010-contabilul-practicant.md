# ADR-010 — Contabilul practicant: rolul este acoperit de proprietar

- **Status:** Acceptat — 2026-08-24
- **Data:** 2026-08-24
- **Decide:** proprietarul proiectului, în ambele roluri
- **Închide:** `OD-32` din `000-open-decisions.md`
- **Afectează:** `ADR-002` (efect secundar, nu conținut), `OD-06`, `OD-22`, `OD-23`, corpusul de
  regresie fiscală, registrul de riscuri

## Context

`OD-32` era marcată **critic** în registrul de riscuri: „condiție de start", neconfirmată. A apărut
de trei ori în aceeași conversație, sub trei forme — validarea valorilor fiscale, aprobarea
ADR-urilor cu conținut contabil, și alimentarea corpusului de regresie.

Proprietarul proiectului acoperă rolul.

## Opțiuni evaluate

1. **Proprietarul acoperă rolul.** *Avantaje:* elimină cel mai scump element deschis din registru;
   competența contabilă și cea tehnică stau în aceeași persoană, deci nu se pierde nimic la
   traducere. *Dezavantaje:* co-semnătura din `ADR-002` nu mai este o verificare independentă —
   aceeași persoană semnează ambele roluri. *Cost de schimbare:* mic — un al doilea contabil se
   poate adăuga oricând, iar `ADR-002` îl acomodează fără modificare.
2. **Contabil extern, sub contract, ca al doilea semnatar.** *Avantaje:* păstrează verificarea
   independentă. *Dezavantaje:* cost și latență pe fiecare decizie contabilă, într-o fază în care
   deciziile contabile sunt dese. *Cost de schimbare:* —

## Decizie

**Opțiunea 1.** Rolul de contabil practicant din `ADR-002` este acoperit de proprietarul
proiectului. ADR-urile cu conținut contabil, fiscal sau juridic nu mai stau blocate în `Propus`.

`ADR-002` **nu este înlocuit.** Decizia lui — proprietarul aprobă, conținutul contabil cere
semnătura contabilului practicant — rămâne validă și corectă. Ce se schimbă este o *constatare* din
secțiunea lui de consecințe, nu o regulă. Dacă mâine apare un al doilea contabil, `ADR-002` se
aplică neschimbat.

**Instrumentul de risc se înlocuiește.** `ADR-002` observa că numărul de ADR-uri blocate în `Propus`
este măsura vizibilă a riscului contabil. Cu rolurile colapsate, contorul acela returnează zero
permanent și nu mai semnalează nimic. Nu este o problemă de guvernanță — este un instrument care nu
mai măsoară ce trebuia.

Înlocuitorul este **corpusul de regresie fiscală** (`C14`, F1.10). El face mecanic ce făcea a doua
semnătură: verifică rezultatul contra unui adevăr cunoscut. Condiția este să fie alimentat cu
**cazuri reale, cu rezultat verificat** — declarații efectiv depuse, calcule salariale efectiv
plătite, balanțe efectiv închise. Cazuri construite din raționament propriu nu au această
proprietate: reproduc exact înțelegerea care ar trebui verificată.

**Măsura de risc devine acoperirea corpusului de regresie**, nu numărul de ADR-uri în `Propus`.

## Consecințe

- Devine posibil: închiderea deciziilor care așteptau expertiză contabilă — `OD-06`, `OD-22`
  (valorile fiscale efective), `OD-23` (planul de conturi SNC), `DNB-05`, `DNB-07`, `DNB-09`,
  `DN-22` / `OD-21` (retenția). Devin **răspunzabile**, nu răspunse: fiecare cere în continuare
  ADR-ul ei, cu actul normativ citat. `CLAUDE.md` §4 — „nu se deduc reguli fiscale din memorie" —
  se aplică neschimbat, iar acum se aplică proprietarului în rol de contabil.
- Se pierde: verificarea independentă pe conținut contabil. Aceasta este consecința reală a
  deciziei și motivul pentru care instrumentul de risc trebuie să existe în altă parte.
- De modificat ca urmare: `OD-32` trece în „Închise"; rândul de blocaj din `docs/PROGRESS.md` se
  schimbă din „ADR-uri în `Propus`" în „acoperirea corpusului de regresie".
- Rămân externe, indiferent de cine e contabil, pentru că nu țin de expertiză ci de ce validează
  instituțiile:
  - **`DNB-08`** — rotunjirea TVA. Blocată pe schema XML a e-Facturii. O diferență de un ban față de
    validatorul SFS respinge factura, oricât de corectă ar fi contabil.
    > **Reconciliere, 2026-08-29.** Rândul de mai sus e din 2026-08-24 și nu mai descrie blocajul:
    > [ADR-037](037-conventii-de-platforma.md) §0 a fixat structura (linia e autoritativă), iar din
    > cele patru sarcini de verificare doar `V2` — schema XML — depinde de SFS și condiționează
    > testul de acceptanță, nu codul. Ce rămâne e `V1`, Ordinul MF 118/2017, document public. Nu
    > se editează decizia; se corectează ce afirma despre lume — inclusiv „singurul element extern
    > pe drumul critic" de mai jos, care rămâne adevărat doar pentru formatele declarațiilor.
  - **Formatele declarațiilor** — SFS, CNAS, CNAM (`OD-24`, `OD-25`). Se citesc, nu se deduc.
  - Ambele se deblochează prin aceeași acțiune: semnătură electronică, entitate de test, acces în
    e-Factura, ghidul de integrare. **Acesta este acum singurul element extern pe drumul critic.**

## Surse

- `decisions/002-guvernanta-deciziilor.md` §Decizie, §Consecințe.
- `000-open-decisions.md`: `OD-32`, `OD-22`, `OD-23`, `OD-24`, `OD-25`.
- `CLAUDE.md` `C14`, §4.
- Conversație 2026-08-24.
