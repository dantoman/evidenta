# ADR-087 — Decontarea e o alocare, nu o postare; și stă într-un singur modul

- **Stare:** Acceptat — tehnic (arhitectură delegată); **latura contabilă nu se decide aici**
- **Data:** 2026-08-31
- **Decis de:** sesiunea de implementare, pe partea de structură; punctele de tratament rămân deschise
  și sunt enumerate în §5
- **Închide:** partea de plasare a lui `F2.A3` lăsată deschisă în `09-f2-backlog.md`
  (*„`operations/receivables`, `operations/payables` — sau un singur modul de decontări; ADR-ul lui
  `F2.A0` decide"*), pe care [ADR-073](073-forma-postarii-documentelor-comerciale.md) n-a atins-o
- **Deschide:** `OD-127`, `OD-128`
- **Atinge:** `operations/settlements` (modul nou), `infra/migrations/0074`
- **Legate:** [ADR-057](057-diferentele-realizate-la-decontare.md),
  [ADR-073](073-forma-postarii-documentelor-comerciale.md), Spec B §4.2, §10.1

> **REZERVĂ (`OD-83`), purtată mai departe din [ADR-073](073-forma-postarii-documentelor-comerciale.md):**
> motorul ramifică doar pe capabilități, deci statutul TVA al companiei n-are pe ce selecta un
> tratament. Aici rezerva se vede altfel decât la facturare, și **nu se stinge**: o decontare stinge
> soldul unei facturi **fără TVA**, fiindcă acela e singurul fel de factură pe care produsul îl emite.
> Când pasul 6 aduce tratamentul cu TVA, soldul deschis rămâne totalul documentului — decontarea nu se
> schimbă —, dar ajustarea bazei din `OD-128` se declanșează tot de aici. Rezerva iese odată cu
> `OD-83`, nu cu acest ADR. *(2026-09-02: ADR-089 aduce facturile cu TVA; soldul deschis rămâne
> totalul documentului, exact cum spune rândul acesta, și decontarea nu s-a atins. `OD-128` rămâne.
> Numit fără legătură, deliberat: gardianul rezervelor citește o legătură din antet ca dependență.)*

> **REZERVĂ NEATINSĂ (`OD-85`):** acest ADR se sprijină pe
> [ADR-057](057-diferentele-realizate-la-decontare.md) pentru forma faptului și pentru cele trei
> perechi de roluri, nu pentru tarife sau anexe. Nicio valoare fiscală nu apare aici.

## 1. Ce lipsea, măsurat

`accounting/posting/services/settlement.py` există din F1.4.4 și e complet pentru ce face: calculează
**diferențele realizate** și le postează, cu stampila de parametru și cele trei perechi de roluri din
ADR-057. Ce n-a existat niciodată e **faptul pe care îl consumă**: `SettlementFact` poartă un
`settlement_id`, iar nimic din produs nu scria vreodată rândul cu acel id.

Consecința, până azi: o factură se contabiliza, o încasare se contabiliza, soldul partenerului scădea
— și nimic nu spunea **care factură a fost stinsă**. Backlogul o numește exact: *„nu există entitate
de decontare, nici jurnal de solduri deschise"*.

## 2. Decontarea nu postează nimic, în cazul obișnuit

Aceasta e piesa care schimbă forma modulului, și e ușor de trasat greșit.

Încasarea a debitat trezoreria și a creditat creanțele **deja**, la contabilizarea ei (ADR-073 §5).
Alocarea ei pe o factură anume **nu mută niciun sold**: aceleași conturi, aceleași sume, aceeași
balanță înainte și după. Ce adaugă e răspunsul la *care creanță*.

Deci decontarea e o **alocare**, nu un efect financiar — iar `R9` nu e încălcat, fiindcă nu se scrie
nimic în registru.

**Prima formă a acestui ADR spunea că evenimentul se emite oricum. Motorul a refuzat-o, și refuzul e
mai bun decât ce scrisesem.** `contract_denomination` are exact două valori — `foreign_currency` și
`conventional_units`, cele două noțiuni pe care le numește standardul (pct. 4, 17) — și **niciuna nu
înseamnă „contractul e în lei"**. Nu e o scăpare de vocabular: evenimentul aparține **diferenței**, nu
alocării. Spec B §10.1 o spune din celălalt capăt — diferențele realizate se postează *ca eveniment
contabil propriu*.

Forma corectă, deci: o alocare în moneda funcțională se **înregistrează și se auditează**, și nu emite
nimic. Evenimentul apare când decontarea traversează valute, cu denominarea pe care contractul chiar o
are (`OD-127`). Ce postează atunci sunt **diferențele**, cu handlerul lor de la F1.4.4.

*Consemnat ca atare fiindcă e tiparul pe care registrul îl numește la `OD-66`: o eroare de încadrare
care s-ar fi implementat impecabil — un eveniment emis pentru fiecare potrivire, cu un discriminator
inventat ca să treacă de o verificare.*

## 3. Un singur modul, cu o coloană de parte

`operations/settlements`, o tabelă, coloana `side` în `('receivable','payable')` — aceeași formă ca
`treasury_document.direction`, și din același motiv: două aplicații Django peste o singură tabelă ar
duplica migrațiile, politica, serviciile și testele, ca să exprime o distincție care e o valoare.

**Cele două nume de eveniment rămân două** (`receivables.settlement_created`,
`payables.settlement_created`) și nu se unifică: acela e vocabularul contabil din ADR-038, fixat
înainte și consumat de handler; numele unui app nu-l comandă.

`receivables` și `payables` rămân chei separate în vocabularul de scope al angajamentelor
(ADR-019) — acolo descriu **ce deleagă un client unei firme**, ceea ce e o altă întrebare decât unde
stă codul.

## 4. Discriminatorii vin de pe documentul stins, nu de pe partener

`SettlementFact` cere `partner_resident` și `contract_denomination`. Backlogul lui `F2.A3` prevedea
pentru asta o **migrare aditivă pe `Partner`** (rezidența) și pe `Document` (denominarea).

Prima nu se mai face, și motivul e că [ADR-073](073-forma-postarii-documentelor-comerciale.md) §2 a
decis între timp altfel: rezidența e **de pe faptul economic**, purtată pe documentul comercial, tocmai
fiindcă `Partner` nu o are și un implicit ar posta greșit. Decontarea o citește de pe documentul pe
care îl stinge — unde a fost deja cerută, o singură dată, de la omul care știa.

A doua se amână cu cazul care o cere: denominarea contractului contează doar pentru **diferențele de
sumă**, care apar între rezidenți pe contracte în valută sau în unități convenționale. Cât timp
trezoreria e numai în monedă funcțională (ADR-073 §5), faptul poartă denominarea egală cu moneda și
handlerul nu are ce calcula. `OD-127`.

## 5. Ce **nu** se decide aici, și rămâne deschis

- **`OD-127` — decontarea în valută.** Cere trezoreria în valută, care e amânată deliberat: o încasare
  în valută deschide diferențele de curs, iar ele au handlerul lor. Când vine, faptul poartă cursurile
  reale și `contract_denomination` devine o coloană pe `Document`.
- **`OD-128` — ajustarea bazei TVA la contractul în valută decontat în lei**, art. 98 alin. (2). E
  **handler propriu**, nu diferență de curs, iar confuzia dintre ele produce o declarație greșită
  (backlog `F2.A3`, ADR-039 §3.3). Nu se scrie din memorie: cere textul articolului.
- **Avansul.** Rolurile există, `sales.document` are `nature = advance`, iar ADR-073 §6 refuză
  deliberat să posteze doar prima jumătate. Stingerea avansului e o decontare ca oricare alta ca
  formă, dar cere ca încasarea în avans să se posteze întâi — deci vine cu ea, nu aici.

## 6. Consecințe

- **Devine posibil:** *care factură a fost stinsă* — întrebarea pe care produsul n-o putea răspunde;
  soldurile deschise per document și per partener; decontarea parțială.
- **Devine imposibil:** o alocare peste ce a rămas de stins pe document, sau peste suma mișcării;
  aceeași decontare de două ori (`R19`, pe evenimentul contabil).
- **Rămâne cum era:** registrul. O alocare în moneda funcțională nu scrie nicio linie de jurnal, iar
  balanța e identică înainte și după — ceea ce e chiar proprietatea pe care un test o afirmă.
- **Ce se verifică automat:**
  1. o decontare integrală și una parțială lasă balanța neschimbată, la ban, **și nu emit niciun
     eveniment contabil** — două documente postate produc două evenimente, potrivirea lor niciunul;
  2. soldul deschis al documentului scade cu exact suma alocată;
  3. o alocare peste rest e refuzată, cu cod stabil;
  4. a doua alocare peste ce a rămas e refuzată — **plafonul e mecanismul**, nu idempotența:
     două alocări distincte sunt două fapte, iar ce le oprește să treacă de sold e restul;
  5. rezidența ajunge în fapt **de pe documentul stins**, nu dintr-un implicit.

## Surse

- Spec B §4.2 (*decontarea e entitate proprie în `receivables`, nu o coloană pe linia de jurnal*), §10.1.
- `_bootstrap/09-f2-backlog.md`, `F2.A3` — obiectivul, criteriile de terminare și golul măsurat.
- [ADR-057](057-diferentele-realizate-la-decontare.md) (`SettlementFact`, cele trei perechi de roluri),
  [ADR-073](073-forma-postarii-documentelor-comerciale.md) §2 și §5–6.
- Măsurat la 2026-08-31: `settlement.py` livrat și fără apelant; niciun rând purtând un `settlement_id`.
