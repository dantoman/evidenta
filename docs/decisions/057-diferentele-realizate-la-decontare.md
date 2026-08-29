# ADR-057 — Diferențele de curs și de sumă realizate la decontare: termenul pe antet, discriminatorul fără implicit, trei perechi de conturi

- **Status:** Acceptat — decizie tehnică sub regimul [ADR-002](002-guvernanta-deciziilor.md), care
  implementează clasificarea `C4` aprobată de proprietar ([ADR-036](036-forma-postarii.md) §11) și
  instrucțiunea scrisă a sesiunii C4 (2026-08-30); **nu decide niciun tratament**: recunoașterea e
  determinată de standard, iar ce e alegere e numit ca atare
- **Data:** 2026-08-30
- **Decide:** proprietarul proiectului (F1.4.4, primul handler din ordinea fixată)
- **Închide:** — *(`DN-04` rămâne deschisă; nu blochează)*
- **Afectează:** `platform/documents` (`Document.rate_term`, migrarea `0003`; `open_draft`),
  `operations/sales`, `operations/purchases` (trecerea termenului), `accounting/posting/services/settlement.py`
  (nou), `accounting/slots/data/roles_snc_2020.csv` (patru roluri), `accounting/events` (două tipuri),
  `tests/isolation/test_settlement_differences.py`
- **Legate:** [`c4-diferente-de-curs.md`](../_input/cercetare/c4-diferente-de-curs.md), [ADR-039](039-valuta-si-perioade.md)
  (`DN-04`), [ADR-047](047-stampila-parametrului-la-postare.md) (ștampila), [ADR-048](048-formula-si-sloturile-tipizate.md),
  [ADR-055](055-precizia-cantitatii-e-a-unitatii.md) (implicitul care nu era regulă)

---

## 1. Context

C4 e primul handler nu din întâmplare: e singurul dintre cele cinci care produce formule **pe care nu
le cere nicio linie de document** — diferența apare din compararea a două momente, ziua recunoașterii
și ziua decontării. Dacă motorul poate emite asta, restul handlerelor sunt cazuri mai simple.

Precondiția, măsurată ieri la cererea proprietarului: antetul documentului avea `currency` și
`exchange_rate`, **nu și termenul contractual privind cursul** (pct. 19). Fără el, la decontare nu se
știe dacă apare o diferență sau niciuna (pct. 21).

Ce spune standardul, citit din textul consolidat (redacția OMF 48/2019, în vigoare 01.01.2020):
două noțiuni cu aceeași aritmetică, deosebite de **contraparte** (pct. 4, 17); trei momente de
măsurare (pct. 6); realizate la decontare (pct. 8); trei perechi de conturi, nu două; avansurile
excluse din reevaluare (pct. 11–12, 23); cursul contractual poate face ca diferența să nu apară
deloc (pct. 19, 21).

## 2. Opțiuni evaluate

### 2.1 Termenul pe antet și implicitul lui

1. **Fără implicit** — termenul obligatoriu la fiecare document, cum s-a făcut la `decimal_places`
   ([ADR-055](055-precizia-cantitatii-e-a-unitatii.md)). *Dezavantaj:* cere fiecărui document să
   declare ceva ce actul decide deja când contractul tace.
2. **Implicit `payment_date`** — *ales*. **De ce e sigur, spre deosebire de `default=0` la zecimale:**
   acolo implicitul acoperea o alegere care nu fusese făcută de nimeni; aici implicitul **este regula
   supletivă a actului** — pct. 6 și 8 recalculează la cursul din ziua achitării când contractul nu
   prevede altceva. Un document fără stipulație contractuală **chiar cade sub normă**. Livrarea și
   cursul fix sunt stipulații și se înscriu explicit. Diferența e scrisă pe câmp
   (`RateTerm`, în `platform/documents/models.py`), ca peste un an să nu fie citit ca al optulea caz.

### 2.2 Discriminatorul

1. **Implicit „nerezident"** sau **„valută"** — *respins*. Discriminatorul alege între două perechi
   de conturi care aterizează în linii diferite ale situației; un implicit oriunde în el e locul
   unde se strecoară următoarea alegere netăcută, și ar arăta rezonabil.
2. **Refuz** — *ales*. `partner_resident` (bool) și `contract_denomination` (`foreign_currency` /
   `conventional_units`) sunt obligatorii; lipsa lor e `posting.settlement_discriminator_missing`,
   refuzată **înainte** să existe un eveniment — e bug al apelantului, nu postare eșuată.

### 2.3 Unde stă calculul

1. **În serviciu**, handlerul primind diferența gata calculată. *Dezavantaj:* handlerul n-ar mai fi
   forma postării, ci un scriitor de linii; iar ce a stat calculul pe (scara, direcția) n-ar fi al
   handlerului.
2. **În handler, pur de registru** — *ales*. Handlerul citește faptul de decontare din payload și
   întoarce formule pe roluri; **nu citește registrul** (ADR-036 §5.1). Citește registrul **fiscal**
   — scara sumelor și direcția de rotunjire în vigoare la data decontării (R17, R18) — fiindcă
   diferența e prima sumă **derivată** pe care o produce motorul, iar reducerea ei la două zecimale
   e logică versionată, nu aritmetică. Ce a stat pe se **ștampilează** (ADR-047): C4 e primul
   handler care scrie o ștampilă de parametru.

## 3. Decizia

### 3.1 Antetul

`Document.rate_term`, vocabular închis din pct. 19 — `payment_date` (implicit, regula supletivă),
`delivery_date`, `fixed` — cu `CHECK` în bază, trecut prin `open_draft` și prin cele cinci deschideri
din vânzări și achiziții; **înghețat** odată cu restul antetului la validare (triggerul compară
rândul întreg, deci coloana nouă intră din oficiu).

### 3.2 Handlerul — `settlement.differences.v1`

Înregistrat pe două tipuri, `receivables.settlement_created` și `payables.settlement_created`
(Spec B §7.3 numea primul; al doilea e simetricul). Faptul de decontare (`SettlementFact`) e explicit
în fiecare câmp: identitatea decontării și a documentului, partea, moneda, suma în valută, cursul de
la emitere și cel de la decontare, data, termenul, discriminatorul, dacă decontează un avans, și —
opțional, **absent nu zero** — cursul băncii.

Ramurile, în ordinea în care se verifică:

- **termen `delivery_date` sau `fixed`** → nicio formulă (pct. 21: ambele părți recunosc la același
  curs) — eveniment `posted`, fără înregistrare; **caz testat, nu omisiune**;
- **decontează un avans** → nicio formulă (pct. 23: curs fixat la plată, exclus permanent);
- altfel `diff = suma × (curs_decontare − curs_emitere)`, redusă **o singură dată** la scara sumelor,
  cu direcția în vigoare; pe creanță pozitivul e favorabil, pe datorie negativul; perechea e **a
  contrapartei**: rezident → `DIFERENTA_SUMA_*` (6227/7225), nerezident → `DIFERENTA_CURS_*`
  (6226/7224); contul de contrapartidă e rolul creanței/datoriei din țară sau din străinătate, ales
  tot de rezidență;
- **ecartul băncii**, când `bank_rate` e dat: `suma × (curs_bancă − curs_BNM)`, perechea
  `ECART_CURS_BANCA_*` (6127/7147) contra **contului curent în lei** — rezultat **operațional**, nu
  financiar: confuzia cu prima pereche dă un raport greșit pe secțiuni cu totalul corect, invizibil
  în balanță;
- o diferență care **se rotunjește la zero** nu produce linie (invariantul 5).

Serviciul `post_settlement_differences` are forma din `manual` și `closing`: refuză bug-urile
apelantului înainte de eveniment; emite sub cheie de idempotență (`<tip>:<settlement_id>`); selectează
tratamentul după dată și profil; rulează handlerul; leagă rolurile (`bind_roles`); ștampilează
`accounting.amount_scale`; postează; marchează. A doua sosire a aceleiași decontări întoarce aceeași
înregistrare, `posted_now = False`.

### 3.3 Ce nu intră

**Reevaluarea la data raportării** — așteaptă Anexa 1 din SNC „Diferențe de curs valutar și de
sumă", autoritatea asupra liniilor de bilanț care se reevaluează, neextrasă. **Avansurile** rămân
excluse permanent. **`DN-04`** — care zi pentru `exchange_rate` pe antet — rămâne deschisă și nu
blochează: la decontare cursul e cel al zilei plății indiferent de răspuns.

## 4. Consecințe

- **Devine posibil:** primul handler computat există, cu ștampilă; modulul de decontări (F2,
  `banking`) are contractul pe care îl emite — `SettlementFact` — și n-are de calculat nimic;
  perechea a treia are rol și cont, deci situația pe secțiuni are unde să cadă corect.
- **Devine imposibil sau scump, asumat:** un apelant care nu știe rezidența partenerului nu poate
  deconta o creanță în valută — trebuie să afle, nu să presupună; un document cu termen
  neînscris cade sub regula supletivă, care e a actului, nu a noastră.
- **Ce se modifică:** patru roluri noi în catalog (`DIFERENTA_SUMA_FAVORABILA/NEFAVORABILA`,
  `ECART_CURS_BANCA_FAVORABIL/NEFAVORABIL`), numărul fixat la 45; `08-f1-backlog.md` F1.4.4 punctul 1;
  `PROGRESS.md`.
- **Ce se verifică automat:** `test_settlement_differences.py` — 1000 × (19,6234 − 19,5000) = 123,40
  o singură dată, cu ștampila; ambele sensuri pe creanță și pe datorie; perechea de sumă între
  rezidenți; ecartul băncii ca a treia pereche contra contului în lei, în ambele sensuri; `delivery_date`
  și `fixed` → eveniment fără înregistrare; avansul; rotunjirea la zero; discriminatorul refuzat
  înainte de eveniment; moneda funcțională refuzată; aceeași decontare de două ori → o înregistrare.
  `test_documents.py` — implicitul termenului, termenul înscris, un al patrulea refuzat, înghețarea.

## 5. Surse

- Instrucțiunea proprietarului, 2026-08-30 (sesiunea C4); răspunsul „la data achitării", 2026-08-29.
- SNC „Diferenţe de curs valutar şi de sumă", pct. 4, 6, 8, 11–12, 17, 19, 21, 23 —
  [`c4-diferente-de-curs.md`](../_input/cercetare/c4-diferente-de-curs.md), transcris din PDF-ul MF.
- Planul general de conturi — 6226/7224, 6227/7225, 6127/7147, 2211/2212, 5211/5212, 2421.
- [ADR-036](036-forma-postarii.md) §5.1, §11 (C4); [ADR-047](047-stampila-parametrului-la-postare.md);
  [ADR-055](055-precizia-cantitatii-e-a-unitatii.md) §2 (implicitul care nu era regulă); Spec B §1.4,
  §7.3; `CLAUDE.md` — `R9`, `R13`, `R15`, `R17`, `R18`, `C10`, `D6`.
