# ADR-037 — Convenții de platformă: rotunjire, zecimale, granularitatea postării

- **Status:** **Parțial decis** (2026-08-28) — §3.1 și forma rotunjirii sunt fixate de proprietar și
  implementate; rămâne blocat pe `V1` *(precizia prescrisă pe formular)* și pe `V2`–`V4`. Excepția:
  §4 nu depinde de verificare
- **Data:** 2026-08-25; §3.1 decisă 2026-08-28
- **Decide:** proprietarul proiectului
- **Închide:** `DNB-08` (Spec B §7.2, §11) — partea de precizie și rotunjire, la deblocare
- **Afectează:** Posting Engine (F1.4), milestone-ul F1 (balanță verificabilă la leu contra 1C),
  importatorul 1C (F1.9), `OD-24` (accesul SFS)

---

## 0. Decizia din 2026-08-28 — linia este autoritativă

**Consemnare, nu decizie nouă.** Proprietarul a fixat regula prin instrucțiune scrisă; sesiunea de
implementare a scris-o în cod și o consemnează aici, ca `ADR-002` să nu rămână cu o decizie luată și
neconsemnată.

> TVA se calculează și se rotunjește **pe fiecare linie**. Totalul documentului se obține prin
> **sumarea liniilor**, niciodată prin recalculare pe bază de total.

**Ce închide.** §3.1 — baza de calcul a TVA — și, prin consecință, cea mai mare parte din §3.3.
Divergența pe care §3.3 o descria (diferența dintre suma liniilor și totalul recalculat) **nu mai
poate exista**: nu există două calcule concurente. Ce rămâne din §3.3 e o convenție pură — direcția
la echidistanță — și ea nu se alege în cod: `accounting.currency.money.IMPLEMENTATIONS` conține
**ambele** direcții (`half_up`, `half_even`), iar care rulează e un rând în `fiscal_logic_version`,
selectat după data efectivă. Prezența amândurora nu e o alegere între ele.

**Ce rămâne deschis, și e singurul lucru care mai blochează calculul unei linii.** §3.2 — numărul de
zecimale. Ipoteza de lucru a proprietarului: **patru la prețul unitar, două la sume**. Este
**parametru fiscal** (`R15`), nu constantă: `accounting.amount_scale` și
`accounting.unit_price_scale`, rezolvate după dată. Dacă Instrucțiunea prescrie altceva, se ajustează
parametrul, nu structura.

**Ce s-a putut și ce nu s-a putut citi din sursă primară, 2026-08-28.** Identitatea actului, citată
verbatim într-un document al Ministerului Finanțelor: *Ordinul ministrului finanțelor nr. 118 din 28
august 2017 (Monitorul Oficial al Republicii Moldova, 2017, nr. 340-351, art. 1750)*. Textul
consolidat al Instrucțiunii **nu** s-a putut citi: `legis.md` întoarce 403 pe PDF și pe pagina de
rezultate, `sfs.md` întoarce 403, `contabilsef.md` cere abonament. Deci **niciun punct al
Instrucțiunii nu a fost citit prescriind zecimale** — `V1` rămâne de făcut, iar precizia intră cu
`source_confidence = provisional` când va exista o cale de scriere.

**Al doilea blocaj, găsit la implementare și nou pe acest drum: `OD-67`.** `fiscal_parameter` are
politică doar de **citire** (`0027_fiscal.up.sql`); nu există cale prin care precizia să fie
încărcată, în afară de superuser. Mecanismul e complet și **inert**. Aceeași familie ca `0044`, care
a trebuit să adauge o politică de scriere pentru planul de conturi — și aceeași familie ca CI-ul
legat și nepornit.

**Atenție la o coliziune de numere care poate produce o citare greșită:** *OMF 118 din 28.08.2017*
(factura fiscală, MO 2017 nr. 340-351 art. 1750) și *OMF 118 din 06.08.2013* (SNC) sunt acte
diferite cu același număr. Exact motivul pentru care `FiscalParameterSource.act_date` face parte din
identitate.

---

## 1. De ce e un ADR separat

Există o categorie de comportamente pe care contabilii le percep ca „așa se face", dar care nu sunt
nici lege, nici politică contabilă. Legea tace asupra lor sau le determină implicit prin formularul
tipizat. Ele există pentru că cineva a scris cândva o implementare într-un fel.

**Criteriul de separare față de politica contabilă** (stratul 3 din
[ADR-036](036-forma-postarii.md) §7):

> Dacă schimbarea ar trebui consemnată în documentul de politică contabilă al companiei, aprobat
> prin ordin intern — e politică. Dacă nu — e convenție de platformă.

Rotunjirea TVA nu se consemnează nicăieri, nu se aprobă prin ordin, nu e o alegere pe care o
entitate o *face*. E o convenție de calcul. Prin urmare nu aparține ecranului de politici contabile.

Aceste convenții se decid **o dată, în cod, deliberat**, aliniate la 1C acolo unde nu contravin
legii — nu accidental, ca efect secundar al implementării.

### 1.1 Ce e deja fixat și nu se redeschide aici

Spec B §7.2 fixează trei lucruri fără risc, independent de ghidul SFS. Rămân în vigoare:

1. **`numeric` cu scală explicită, niciodată `float`.** `float` face ca aceeași balanță să dea
   rezultate diferite după ordinea de agregare.
2. **Calculele intermediare pe linie se fac la precizie mai mare decât cea de postare.** Rotunjirea
   se aplică o singură dată, la producerea liniei de jurnal.
3. **Rotunjirea este logică fiscală versionată, nu funcție utilitară.** Trăiește în
   `fiscal_logic_version`, cu `logic_key` propriu, selectată după data efectivă a perioadei (`R17`,
   `R18`). O funcție `round_money()` într-un modul de utilitare este exact forma în care o regulă
   fiscală ajunge nemarcată în cod.

ADR-ul de față decide **valorile și axele** rămase, nu mecanismul.

---

## 2. De ce blochează milestone-ul F1

Milestone F1: *balanță corectă, verificabilă la leu contra unei balanțe 1C reale.*

**Politica contabilă nu va strica acest test.** Cu aceeași metodă de cost se obțin aceleași sume
mari.

**Rotunjirea îl va strica.** Rezultatul va fi o balanță corectă în structură, cu diferențe de bani
pe zeci de conturi — și zile pierdute căutând un bug de postare care nu există, când de fapt e o
convenție de rotunjire diferită.

Fenomenul a fost deja observat la reconcilierea de facturi AvaCore–1C. Acolo era supărător. Într-un
test de acceptanță „la leu", e blocant.

**Concluzie operațională: aceste convenții trebuie fixate ÎNAINTE de implementarea Posting Engine,
nu după.**

---

## 3. Axele de decizie

### 3.1 Baza de calcul a TVA

TVA-ul documentului se obține prin:

- **(a)** însumarea TVA calculat pe fiecare linie, sau
- **(b)** aplicarea cotei pe baza impozabilă totală a documentului

Diferența se manifestă ca discrepanță de 1–2 bani, care crește cu numărul de poziții.

**Observație verificată:** dezvoltatorii 1C nu tratează asta ca preferință liberă. Își justifică
alegerea prin lege — în context rusesc, temeiul fiind că TVA se calculează pe fiecare tip de bun,
deci suma corectă e cea obținută prin însumarea TVA-ului de pe linii. Un utilizator care cere
explicit varianta (b) în 1C:UT nu primește o setare, ci explicația că totalurile sunt suma liniilor.

⚠️ Temeiul legal moldovenesc trebuie verificat separat. Analogia cu Rusia nu constituie argument.

### 3.2 Numărul de zecimale

Axe distincte:

- zecimale la prețul unitar
- zecimale la valoarea liniei
- zecimale la valorile totale ale documentului

**Observație din practica regională:** pe factură, singura valoare care poate avea mai mult de două
zecimale este de regulă prețul unitar; restul valorilor se trec cu două zecimale. Aceasta e practica
documentată de furnizori de facturare din România, nu o regulă moldovenească confirmată.

### 3.3 Direcția de rotunjire la echidistanță

Când a treia/a cincea zecimală e exact 5, rotunjirea se face în sus sau în jos.

**Observație verificată:** aceasta este axa pe care produsele reale chiar expun o setare. Un
furnizor românesc de facturare oferă în „Setări avansate" alegerea între rotunjire în sus și în jos
pentru zecimale echidistante — dar o oferă explicit ca soluție la o problemă concretă: când prețul
unitar are patru zecimale echidistante, apare o diferență de un ban între totalul liniilor și
totalul facturii, iar diferența crește cu numărul de poziții.

Aceasta e un plasture pentru un simptom, nu o alegere contabilă.

### 3.4 Granularitatea postării

Un document produce:

- **(a)** o postare consolidată, sau
- **(b)** o postare per linie de document

Invizibil în balanță. **Vizibil în Cartea Mare și în fișa contului** — deci vizibil în comparația cu
1C dacă testul de acceptanță coboară sub nivelul balanței.

### 3.5 Granularitatea analitică

Structura de dimensiuni pe care se ține analitica unui cont — câte niveluri, în ce ordine.
Echivalentul „subconto" din 1C.

Legea cere anumite detalieri, dar forma concretă e alegere de platformă.

> **Reconciliere.** Versiunea originală a acestui paragraf trimitea la „DNB-04 §4.2: setul de chei
> de context e închis, definit în cod". Afirmația nu mai există în forma curentă a deciziei:
> [ADR-036](036-forma-postarii.md) §6.3 lasă subconturile definibile de client, în limita din
> [ADR-029](029-dimensiuni-analitice.md) — zece dimensiuni din lista închisă plus cinci sloturi
> generice per companie. Mulțimea **cheilor de context pentru legarea condiționată rol → cont** este
> altceva și rămâne deschisă ca `OD-55`. Această axă nu se decide aici; e menționată doar ca să nu
> fie confundată cu rotunjirea.

### 3.6 Momentul postării și anularea

- Când se consideră un document postat
- Ce se întâmplă la anulare (storno, în conformitate cu registrul append-only, `R10`)
- Dacă anularea produce o postare inversă sau marchează postarea originală

Ultima variantă e exclusă de `R10`.

> **Reconciliere.** „Rămâne de fixat forma exactă a stornoului" e adevărat doar pe jumătate:
> [ADR-006](006-reversal-two-dates.md) (`Acceptat`) fixează deja structura — stornoul are două date
> distincte — iar [ADR-007](007-reversal-period.md) (`Propus`, trei întrebări nerăspunse) ține
> partea de politică: perioada în care se postează. Ce rămâne cu adevărat aici este **momentul
> postării** unui document, nu forma stornoului. Stările perioadei peste care cade acel moment sunt fixate
> de [ADR-039](039-valuta-si-perioade.md) (`open` / `closed` / `locked`).

---

## 4. Principiul care se aplică indiferent de rezultatul verificării

> **Suma postată este autoritativă, nu recalculată.**

Documentul stochează sumele efective pe linie și pe total. Nimic nu se recalculează la afișare, la
tipărire, la generarea rapoartelor sau la reprocesare.

### 4.1 Ce rezolvă

**Importul din 1C.** Importatorul preia sumele exact cum sunt în sursă, chiar dacă motorul nostru
le-ar fi calculat cu un ban diferit, și le marchează ca provenite din import. Istoricul migrat rămâne
fidel la ban; documentele noi folosesc convenția noastră unică; registrul rămâne coerent. Fără
setare per tenant, fără fragmentare a definiției corectitudinii.

**Schimbările viitoare de convenție.** Dacă peste trei ani o convenție se schimbă legal, documentele
vechi rămân exact cum au fost postate — pentru că nimic nu le recalculează niciodată.

### 4.2 Această parte nu e blocată

§4 nu afirmă nimic despre contabilitate sau fiscalitate: spune că sistemul nu recalculează ce a
postat. E decizie tehnică, în sensul [ADR-002](002-guvernanta-deciziilor.md), și poate trece în
`Acceptat` separat de restul ADR-ului. **Trebuie implementată de la început**, altfel §6.2 („ușa
rămâne deschisă") devine falsă: fără sume autoritative, orice schimbare ulterioară de convenție
rescrie tăcut istoricul.

---

## 5. Sarcini de verificare — precondiție pentru deblocare

| # | Sarcină | Sursă | Răspunde la |
|---|---|---|---|
| `V1` | Citește formularul tipizat al facturii fiscale și anexele | Ordinul Ministerului Finanțelor nr. 118 din 28.08.2017, Anexele 1 și 1a | §3.1, §3.2 — coloane și precizie |
| `V2` | Obține și citește schema XML e-Factura | Specificația SFS / Regulamentul aprobat prin Ordinul SFS nr. 317/2020 și modificările ulterioare | §3.1, §3.2 — dacă validatorul impune coerență linie↔total |
| `V3` | Verifică regimul de rotunjire în Codul fiscal și practica generalizată SFS | sfs.md — baza generalizată a practicii fiscale | §3.1 — temei legal moldovenesc |
| `V4` | Obține 3–5 facturi reale cu multe linii și TVA, ca **export, nu PDF** | Contabilul care furnizează balanța 1C | §3.1–3.3 — deducerea convențiilor efective 1C Moldova |

**Estimare `V1`–`V3`: o oră.** Documentele sunt necesare oricum pentru F2; deschiderea lor acum
răspunde gratuit la această întrebare.

**`V4` se cere în același pachet cu balanța 1C.** Același efort de solicitare, rezultat suplimentar.
Vezi §7.

*Notă:* `DNB-08` era înregistrată ca blocată pe ghidul de integrare SFS (`OD-24` — semnătură
electronică, entitate de test, acces). `V1` și `V3` **nu** depind de acel acces: sunt documente
publice. Ce depinde de `OD-24` e `V2`.

---

## 6. Opțiuni evaluate, condiționat de verificare

### 6.1 Dacă legea determină convenția

Convenția devine categoria „determinat de lege". Nu apare în niciun ecran de setări. Nu e
negociabilă. Discuția se închide. *Cost de schimbare:* niciunul — nu e alegerea noastră.

### 6.2 Dacă legea permite ambele variante

**(A) O setare per tenant.** *Avantaje:* acoperă orice preferință de migrare. *Dezavantaje:* fiecare
test de acceptanță al motorului se dublează; milestone-ul F1 devine „balanță verificabilă la leu, în
funcție de o setare"; fiecare tichet de suport capătă o variabilă în plus înainte de orice
diagnostic; și, cel mai grav, **două tenanturi cu aceleași documente produc registre diferite** —
ceea ce face imposibilă reproducerea deterministă a unui bug raportat. Într-un registru append-only,
o convenție de calcul care variază per tenant nu e o setare: e o furcă în definiția corectitudinii.
*Cost de schimbare:* mare și crescător — se scoate greu după ce există registre.

**(B) O singură convenție în motor** — *propusă*. *Avantaje:* beneficiul unei setări e practic nul
(nimeni nu alege un software contabil după cum rotunjește; niciun contabil nu deschide ecranul de
setări gândind „aici vreau pe linie"), iar costul de mai sus dispare. *Dezavantaje:* un client venit
din 1C cu altă convenție vede diferențe de bani pe documentele **noi** — pe cele importate nu, prin
§4. *Cost de schimbare:* **mic, cu o condiție** — setarea se poate adăuga ulterior, cu teste
dedicate, **dacă** §4 e implementat de la început. Spre deosebire de multe alte decizii din acest
proiect, aceasta nu e cu sens unic.

**Propunere: (B).**

### 6.3 Alinierea implicitului

Indiferent de rezultat, valoarea aleasă se aliniază la comportamentul 1C Moldova în limitele legii —
același principiu ca la [ADR-036](036-forma-postarii.md) §7.3: mulțimea din lege, implicitul din 1C.

⚠️ Notă: configurația moldovenească a 1C e realizată de parteneri locali, care modifică configurația.
Dacă acolo există o setare de rotunjire, ea e o modificare de fork local, nu comportament de
platformă 1C. Faptul nu schimbă concluzia, dar schimbă interpretarea: nu constituie dovadă că „așa
se face standard".

---

## 7. Dependența externă critică

Milestone-ul F1 cere o balanță 1C reală. Nu se poate simula, forța sau ocoli.

**Pachetul necesar, cerut într-o singură solicitare:**

1. Balanța de verificare pentru cel puțin o lună închisă
2. Documentele primare care au produs-o — fără ele există doar un număr țintă și nicio cale spre el
3. 3–5 facturi cu multe linii și TVA, **ca export, nu ca PDF** (sarcina `V4`)
4. Cartea Mare sau fișa a 2–3 conturi, dacă testul coboară sub nivelul balanței (§3.4)
5. Disponibilitatea contabilului de a răspunde la întrebări de clarificare

**Aceasta este singura poziție de pe drumul critic al F1 cu termen lung și dependență externă. Ar
trebui inițiată imediat, în paralel cu orice altceva.** Dacă se blochează, se blochează întregul
milestone, indiferent de calitatea codului.

*Legat:* `OD-30` (firma de contabilitate colaboratoare) și `OD-28` (versiunile 1C și metoda de
extragere) cer același interlocutor. Se cer împreună.

---

## 8. Consecințe

### 8.1 Ce devine posibil

- Milestone-ul F1 capătă un criteriu de acceptanță fără variabile ascunse.
- Importul din 1C păstrează istoricul fidel la ban, fără să fragmenteze definiția corectitudinii
  pentru documentele noi (§4).
- Un bug raportat de un tenant se reproduce la altul.

### 8.2 Ce devine imposibil sau scump

- Un client care ține la convenția lui de rotunjire nu o primește ca setare. Diferența apare doar pe
  documentele noi.
- Adăugarea ulterioară a unei setări cere teste dedicate pe toate cazurile, nu doar pe cel nou.

### 8.3 Ce trebuie modificat ca urmare

- **Sarcină în backlogul F1, înainte de implementarea Posting Engine:** fixarea acestor convenții ca
  ADR `Acceptat`, cu teste care demonstrează echivalența la ban pe cazuri reale extrase din pachetul
  §7. Fără sarcina asta, milestone-ul F1 se sprijină pe o presupunere nescrisă.
- Spec B §7.2 primește valorile la deblocare; invarianții de acolo rămân neschimbați.
- `DNB-08` se restrânge în registru: `V1` și `V3` nu depind de `OD-24`.

### 8.4 Ce se verifică automat

La implementare: corpusul de regresie fiscală (`C14`), cu cazurile din pachetul §7 ca intrări reale.
Convenția fiind logică fiscală versionată (§1.1), testul de repostare din Spec B §3.4 — eveniment
din 2026 repostat în 2028 → aceleași linii — o acoperă implicit.

---

## 9. Surse

- `docs/specs/spec-b-accounting.md` §7.2 (`DNB-08`, invarianții deja fixați), §7.4, §11.
- [ADR-036](036-forma-postarii.md) §7.2 (criteriul politică vs. convenție), §7.3, §6.3.
- [ADR-006](006-reversal-two-dates.md), [ADR-007](007-reversal-period.md) — forma stornoului (§3.6).
- [ADR-002](002-guvernanta-deciziilor.md) — de ce §4 se poate accepta separat de restul.
- `CLAUDE.md` — `R10`, `R17`, `R18`, `C14`, §4.
- Ordinul Ministerului Finanțelor nr. 118 din 28.08.2017 — **de citit** (`V1`). Nu a fost consultat.
- Specificația XML e-Factura / Ordinul SFS nr. 317/2020 — **de obținut** (`V2`).
- Observații de produs: comportamentul 1C:UT la totalurile de document; setarea de rotunjire la
  echidistanță a unui furnizor românesc de facturare. Ambele sunt indicii de practică, nu temei
  legal moldovenesc.
- Reconciliere AvaCore–1C, unde fenomenul a fost observat prima oară.
- Conversație 2026-08-25.
