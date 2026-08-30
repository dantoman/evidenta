# ADR-069 — Populația declarației nominale nu e mulțimea angajaților

- **Status:** **Acceptat** — **decizie de domeniu** fiscal, semnată de proprietar în rol de contabil
  practicant ([ADR-010](010-contabilul-practicant.md), sub [ADR-002](002-guvernanta-deciziilor.md))
- **Data:** 2026-08-30
- **Decide:** proprietarul proiectului
- **Amendează:** [ADR-065](065-schema-salarizarii.md) §4, [ADR-068](068-anexa-citita-categoria-e-a-raportului.md) §5
- **Afectează:** `F2.B1`, `F2.B2`, `F2.C2`; `OD-91` primeşte consecinţa de model
- **Legate:** [ADR-068](068-anexa-citita-categoria-e-a-raportului.md), [ADR-065](065-schema-salarizarii.md)

> **REZERVĂ (`OD-85`):** valorile pct. 1.5, 1.8 şi 1.9 din anexa nr. 1 rămân rezervate — vezi ADR-068
> §7. Corpul legii, citit aici în redacţia LP318/29.12.2025, e consolidat şi nu e atins de rezervă.

## 1. Ce spune legea

**Art. 19 alin. (7) teza a doua, verbatim:**

> *„În raport cu veniturile realizate de angajaţi şi/sau de alte persoane fizice în baza contractelor
> civile (…) contribuţiile de asigurări sociale se datorează conform prevederilor prezentei legi."*

Coroborat cu **art. 5 alin. (1)**, **art. 8** şi **art. 20 alin. (7)**: prestatorul pe contract civil e
**persoană asigurată**, are **cont personal**, şi apare **nominal** în declaraţie.

## 2. Consecinţa: „persoane asigurate" nu e submulţime a lui „angajaţi"

> **Dacă declaraţia nominală se construieşte din angajaţi, prestatorul e invizibil — şi declaraţia se
> validează, incompletă.**

Modul de eşec e cel care nu se vede: nu e o eroare la depunere, e un **rând care lipseşte** dintr-o
declaraţie altfel corectă. Nimic din partea noastră nu are de unde şti că lipseşte, fiindcă întrebarea
pusă tabelei a fost *„care sunt angajaţii"*, iar răspunsul a fost corect la ea.

**Sprijin structural, din formular, nu din raţionament:** coloana 5 din IALS21 e **codul sursei de
venit per rând**, nu per contribuabil, iar antetul **n-are categorie de plătitor**. Declaraţia
statutară n-a fost niciodată proiectată nici pe companie, nici pe angajat — e proiectată pe **rând de
venit**. Ceea ce mută reformularea lui `OD-81` din *corecţie juridică* în **constrângere a ieşirii**.

**Amendament la ADR-065 §4:** `employee` rămâne ce e — persoana angajată de companie, la nivelul
companiei. Ce se schimbă e că **declaraţia nominală nu se rădăcinează pe ea.** Constructorul
declaraţiei se scrie peste o populaţie de **raporturi asigurate**, nu peste tabela de angajaţi. Până
când `OD-91` decide unde locuiesc contractele civile, populaţia are un singur membru — raportul de
muncă — **dar interfaţa e cea largă**, fiindcă lărgirea ulterioară a unei interogări scrise pe
`employee` nu e o extindere, e o rescriere a fiecărui apelant.

## 3. Efectul opus, şi e cel periculos: art. 22 **nu** se aplică pe contracte civile

Art. 22 alin. (1) spune **„pentru fiecare salariat"**. Invariantul bazei minime — baza nu poate fi sub
salariul minim lunar pe ţară, proporţional timpului lucrat; la timp parţial contribuţia nu sub 25% din
cea la salariul minim — **e al raportului de muncă, nu al oricărei baze CAS.**

[ADR-068](068-anexa-citita-categoria-e-a-raportului.md) §5 a purtat cuvântul „salariat" din act, dar
**n-a spus nicăieri că invariantul se opreşte acolo.** Se spune acum, fiindcă implementarea evidentă e
şi cea greşită:

> **Implementat ca verificare pe orice bază CAS, invariantul umflă rândurile contractelor civile la
> salariul minim.** Rezultatul e o **datorie reală mărită tăcut** — şi *perfect echilibrată*: `R11`
> trece, înregistrarea se postează, niciun test de sold n-o vede. Se descoperă la o reconciliere cu
> CNAS, adică luni mai târziu, pe bani viraţi în plus.

**Amendament la ADR-068 §5:** invariantul poartă un **domeniu explicit** — se aplică raporturilor de
muncă, se refuză celorlalte. **Testul cerut la `F2.B2`:** o bază CAS de pe contract civil sub salariul
minim **rămâne** sub salariul minim.

## 4. Consecinţe

- **Devine posibil:** o declaraţie nominală care poate deveni completă fără rescrierea apelanţilor.
- **Devine imposibil:** un invariant de bază minimă aplicat orbeşte pe orice bază CAS.
- **De modificat ca urmare:** `F2.B1` — constructorul declaraţiei pe populaţie, nu pe `employee`;
  `F2.B2` — domeniul invariantului plus testul; `F2.C2` — completitudinea declaraţiei nominale;
  `OD-91` primeşte consecinţa de model, şi rămâne deschisă pentru **unde** locuiesc contractele civile.
- **Nu se decide aici** unde locuiesc — asta e `OD-91`. Se decide doar că populaţia nu e cea a
  angajaţilor, şi că invariantul nu se aplică peste ea.

## 5. Surse

- Legea nr. 489/1999, **redacţia consolidată la LP318 din 29.12.2025, în vigoare 01.07.2026** — deci
  în vigoare azi: art. 5 alin. (1), art. 8, **art. 19 alin. (7) teza a doua** (verbatim, §1), art. 20
  alin. (7), art. 22 alin. (1). Text integral, obţinut de proprietar 2026-08-30.
- Ordinul Ministerului Finanţelor nr. 95/2020, formularul IALS21 — coloana 5 şi antetul; redacţiile
  OMF nr. 103 din 17.09.2024 şi OMF nr. 59 din 04.05.2026 (în vigoare 08.05.2026), amândouă în text
  integral, obţinute de proprietar 2026-08-30.
- [ADR-065](065-schema-salarizarii.md) §4, [ADR-068](068-anexa-citita-categoria-e-a-raportului.md) §5.
