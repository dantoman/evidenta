# ADR-097 — Valuta: cursul are o ușă, decontarea în lei emite faptul, reevaluarea e un handler

- **Stare:** Acceptat — tehnic (arhitectură delegată); **decizie de domeniu** pe forma postării
  reevaluării, cu actul citat; proprietarul confirmă sau răstoarnă
- **Data:** 2026-09-03
- **Decis de:** sesiunea de implementare (pasul `5e` din `_bootstrap/14-planul-golurilor.md`), sub
  instrucțiunea proprietarului de a lua deciziile și a le consemna cu implicitul lor reversibil
- **Închide:** `OD-127` (decontarea în valută, denominarea pe document); construiește `F2.A9` fără
  conectorul BNM (`OD-76` rămâne) și **`A10`** (reevaluarea la data raportării)
- **Nu închide:** `OD-128` (ajustarea bazei TVA, art. 98 alin. (2) — handler propriu, textul necitit),
  `OD-76` (conectorul BNM), `DN-04` (care zi pentru curs pe antet — se ia aici **implicitul
  reversibil**, nu decizia)
- **Atinge:** `accounting/currency` (ușa `P-3`, modelul reevaluării, migrarea `0002`,
  `infra/migrations/0079`), `accounting/posting/services/revaluation.py` (nou),
  `accounting/posting/services/commercial.py` (conversia), `platform/documents`
  (`contract_denomination`, migrarea `0004`), `operations/settlements` (alocarea în valută, migrarea
  `0002`, furnizorul de elemente monetare), `operations/sales`, `operations/purchases`,
  `frontend` (valuta pe formulare, ecranul „Reevaluare valutară")
- **Legate:** [ADR-039](039-valuta-si-perioade.md) (`DN-04`, §3.2),
  [ADR-057](057-diferentele-realizate-la-decontare.md) (faptul de decontare, cele trei perechi),
  [ADR-087](087-decontarea-e-o-alocare.md) (alocarea), [ADR-049](049-rolul-de-date-de-referinta.md)
  (ușa privilegiată), Spec B §7

> **REZERVĂ (`OD-83`), purtată mai departe din [ADR-087](087-decontarea-e-o-alocare.md):** motorul
> ramifică doar pe capabilități; nimic de aici nu selectează un tratament după statutul fiscal —
> reevaluarea are **un singur** `HandlerVersion`, de la 01.01.2020. Rezerva iese cu `OD-83`/`OD-130`,
> nu cu acest ADR.

> **REZERVĂ NEATINSĂ (`OD-85`):** acest ADR se sprijină pe ADR-087 și ADR-057 pentru forma faptului
> și pentru perechile de roluri, nu pentru tarife sau anexe. Nicio valoare fiscală nu apare aici;
> cursurile din teste sunt fixturi (cele din ADR-057), nu cursuri publicate.

## 1. Ce lipsea, măsurat

Planul golurilor, rândul 9: *„alocarea refuză valuta (`allocation.py`); niciun endpoint de curs;
handlerul de diferențe fără apelant; reevaluarea declarată absentă"*. Măsurat înainte de a scrie:

- `ExchangeRate` există din F0.9, `rate_on` refuză ziua fără curs, dar **nimic nu scria tabela**:
  politica de scriere pentru `evidenta_refdata` e din `0060`, comanda nu exista. `P-3` era un cod în
  enumerare fără niciun rând în `privileged_access_log`.
- `open_draft` cerea `exchange_rate` explicit pentru orice document în altă valută și nu-l căuta
  nicăieri (ADR-039 `DN-04` deschisă); `recognise_sale`/`recognise_purchase` refuzau
  `currency != functional`.
- `allocate` refuza orice document sau mișcare în afara monedei funcționale; `SettlementFact` cerea
  `contract_denomination`, iar `Document` n-avea coloana.
- `accounting.revaluation_calculated` era numit în Spec B §7.3 și nicăieri altundeva.

## 2. Opțiuni evaluate

### 2.1 Cum ajunge cursul în tabelă

1. **Endpoint pe consolă** (`P-3` prin procesul web, ADR-091). *Respins aici:* consola e a altei
   sesiuni; ușa de bază trebuie să existe indiferent de ecran.
2. **Comandă de management din fișier CSV, sub rolul de date de referință** — *ales.* Exact forma
   lui `load_fiscal_parameters` (`P-4`): fișier, `privileged_run`, un rând de jurnal pe rulare,
   idempotentă pe cheia naturală. Conectorul BNM (`OD-76`) va alimenta același serviciu.

**Ce se refuză:** o valoare diferită pentru aceeași zi și același tip (`currency.rate_conflict`).
Nu se suprascrie: o înregistrare postată stă pe cursul de atunci (`R10` prin analogie). Corecția e
un rând nou de tip `manual`, cu sursa. `contractual` nu se încarcă din fișier — e stipulație de
document (`rate_term = fixed`), nu curs al unei zile.

### 2.2 Care zi dă cursul de pe antet (`DN-04`)

1. **Data obligației fiscale privind TVA** (art. 97 alin. (6), prin art. 108). *Plauzibil pentru
   TVA, dar **necitit**: nici art. 97 alin. (6), nici art. 108 nu au fișier de cercetare — ADR-039 §3.2
   le afirmă, iar `c4-diferente-de-curs.md` §„Ce nu s-a putut verifica" spune că textul primar nu a fost
   citit (`OD-132`); data obligației nu e o coloană a documentului.
2. **Data documentului** — *ales ca implicit reversibil.* Pentru livrarea din ziua facturii cele două
   coincid; când nu coincid, apelantul poate da cursul explicit (contractul îl poate fixa). Nu
   închide `DN-04`: o închide citirea art. 108, iar atunci rezolvarea se mută pe o dată calculată, nu
   pe una presupusă. Rezolvarea stă în `operations` (`sales`, `purchases`), nu în nucleul de
   documente: `platform` nu importă `accounting`, iar cursurile sunt ale lui `accounting`.

Linia de jurnal poartă `rate_date = document_date` pe documentele în valută; pe cele în lei rămâne
`accounting_date`, cum era.

### 2.3 Unde stă denominarea

`OD-127` întreba: pe document sau pe contractul din spate. **Pe document**, nullable, cu `CHECK`:
`NULL` exact când documentul e în moneda funcțională, obligatorie altfel, refuzată pe un document în
lei (`documents.contract_denomination_required` / `_invalid`). Nu există entitate „contract"; când va
exista, coloana se copiază de pe ea la deschidere, cum se copiază azi la conversie și la storno.
Fără implicit, din motivul ADR-057 §2.2: valoarea alege perechea de conturi.

### 2.4 Cum se decontează în lei un document în valută

1. **Suma în valută dată explicit de apelant** (din extras). Lasă un rest în lei pe creanță când
   suma nu e produsul exact al cursului — restul ar fi ecartul băncii, iar a treia pereche din ADR-057
   e contra **contului în lei**, corect doar când valuta a intrat într-un cont în valută și a fost
   vândută de acolo. Cu mișcarea deja contabilizată în lei pentru ce a creditat banca, perechea aceea
   ar număra banca de două ori. *Respins pentru pasul acesta.*
2. **Suma în valută derivată la cursul oficial al zilei plății** — *ales.* SNC „Diferențe de curs
   valutar și de sumă" pct. 8 și pct. 19 sub 1: achitarea se înregistrează la cursul oficial al zilei
   achitării. Leii mișcării valorează, în valuta documentului, `amount / rate_on(currency, ziua)`,
   redus o dată la scara în vigoare cu regula în vigoare (`R17`). Faptul poartă `bank_rate = None`.
   Contractele în unități convenționale plătite la cursul zilei dau produsul exact; o plată „rotundă"
   în lei lasă un rest de rotunjire de cel mult o jumătate de ban în valută, consemnat ca limită
   (§5). **Reversibil:** când trezoreria mișcă valută (5c), mișcarea poartă suma în valută și
   `bank_rate`, iar a treia pereche se aplică neschimbată.

Soldurile deschise se țin **în valuta documentului**: `Settlement` primește `currency`,
`amount_currency`, `settlement_rate` (toate `NULL` sau toate setate — `CHECK`), iar
`allocated_to` însumează `COALESCE(amount_currency, amount)`.

**Cursul de emitere din fapt e cursul purtat, nu al facturii**, când o reevaluare a restatat soldul
între timp (pct. 15, Exemplul 3) — `carrying_rate_of(document, before=ziua)`.

### 2.5 Reevaluarea — perimetru și formă

Forma postării, din act (`_input/cercetare/f2-x2-...` Partea II, §8–§9, redacția OMF 48/2019 în
vigoare de la 01.01.2020):

- **Perimetrul:** elementele monetare în valută — creanțe și datorii, fără avansuri (pct. 11);
  contractele între rezidenți **nu** se recalculează (pct. 22). Deci: exact soldurile al căror
  partener nu e rezident — același discriminator pe care ADR-057 îl citește pentru perechea de
  conturi, citit invers. Casa și banca în valută intră în același perimetru (pct. 11, Anexa 1 rândul
  1.1) și **nu există** azi — trezoreria mișcă doar lei; ecranul o spune.
- **Cursul:** cel oficial al zilei de raportare (pct. 6 sub 3); lunar, perioada produsului (pct. 13).
  Absent → refuz, nu cel mai apropiat.
- **Sensul** (pct. 9–10, Anexa 1): creanță cu curs crescut → `Dt 2212 / Ct 6226` *(majorare
  concomitentă a creanțelor și veniturilor curente)*; scăzut → `Dt 7224 / Ct 2212`; datorie invers.
  Rolurile `CREANTE_COMERCIALE_STRAINATATE`, `DATORII_COMERCIALE_STRAINATATE`,
  `DIFERENTA_CURS_FAVORABILA`, `DIFERENTA_CURS_NEFAVORABILA`, partenerul ca dimensiune.
- **Baza următoarei diferențe e cursul reevaluat** (pct. 15, Exemplul 3): `revaluation_item` reține
  `rate_after`, iar decontarea și reevaluarea următoare pornesc de acolo.
- **Data efectivă (`R17`):** handlerul `revaluation.monetary_items.v1` e înregistrat de la
  **2020-01-01** — redacția care scoate avansurile dintre elementele monetare. O reevaluare datată
  înainte n-are tratament, adică refuz, nu redacția 2013 presupusă.

Alternativa — **reversarea la începutul perioadei următoare** (Spec B §7.3, „dacă politica o cere")
— *nu se ia*: cu baza purtată înainte, nu e nevoie de storno, iar un storno automat ar fi a doua
politică. Rămâne reversibilă ca storno obișnuit (`R14`): cât stornoul stă, cursul reevaluării nu mai
duce mai departe (`carrying_rate_of` citește `reversal_of_entry`).

**Idempotentă pe (companie, dată):** cheia evenimentului
`accounting.revaluation_calculated:<company>:<as_of>`, `UNIQUE (company, as_of)` pe `revaluation`;
a doua rulare întoarce prima, `posted_now = False`. O reevaluare care n-a găsit nimic e tot răspunsul
zilei (limită în §5).

### 2.6 Cum află `accounting` ce e deschis

Graful merge într-un sens: `accounting` nu importă `operations`. **Registru de furnizori**
(`currency.services.monetary_items`), în care `operations/settlements` se înregistrează la
`AppConfig.ready()` — inversiunea din ADR-038, aplicată încă o dată. Furnizorul spune fapte (sold
deschis, rezidență, denominare, curs de recunoaștere); regula pct. 11/22 se aplică o singură dată, în
serviciul de reevaluare.

## 3. Decizia

Cele de mai sus, în cod: comanda `load_exchange_rates` (`P-3`); `contract_denomination` pe
`Document`; `open_sale`/`open_purchase` cu valută, denominare și cursul zilei documentului;
`recognise_sale`/`recognise_return`/`recognise_purchase` produc formule cu `currency`,
`amount_currency`, `exchange_rate`, `rate_date`, leii derivați o dată la scara în vigoare, cu
ștampila `accounting.amount_scale` pe înregistrare (ADR-047); `allocate` emite
`receivables.settlement_created` / `payables.settlement_created` cu `SettlementFact` complet;
`revalue_monetary_items(company, as_of)` și `POST /api/v1/accounting/currency/companies/<id>/revaluations`
cu `Idempotency-Key` (`C9`); `GET .../rates?currency=&on=`; ecranul „Reevaluare valutară" sub
Contabilitate; valuta și denominarea pe formularele de facturi, cursul afișat de la server.

TVA pe un document în valută: pentru export către nerezident regimul e scutit cu drept de deducere,
deci nu există linie de TVA; pentru un rezident facturat în unități convenționale TVA se calculează
pe linie **în valuta documentului** și se transformă în lei la cursul antetului, ca netul. Ajustarea
bazei la decontare (art. 98 alin. (2)) rămâne `OD-128`.

## 4. Consecințe

- **Devine posibil:** factura în EUR/USD la nerezident și în unități convenționale la rezident;
  decontarea lor în lei cu diferența realizată pe perechea corectă; reevaluarea lunară a creanțelor
  și datoriilor în valută; `P-3` are rânduri în jurnal.
- **Devine imposibil sau scump, asumat:** ecartul băncii nu se poate posta din alocare până la 5c;
  un document în valută deschis înaintea coloanei (fără denominare) nu se decontează în valută și nu
  se reevaluează — refuz cu nume, nu implicit.
- **Ce se verifică automat:** `tests/isolation/test_foreign_currency.py` — ușa scrie sub rol cu rând
  de jurnal, e idempotentă, refuză schimbarea unei valori; ziua fără curs refuzată; 1000 EUR la
  19,5000 = 19 500,00 pe 2212 cu cele patru elemente pe linie și ștampila; decontarea la 19,6234 →
  123,40 pe 2212/6226 și creanța la zero în ambele monede; rezidentul în u.c. → 2211/6227 și nimic la
  raportare; jumătatea deschisă reevaluată la 19,7000 → 100,00, a doua rulare nimic, decontarea din
  februarie la 19,8000 → **50,00 de la cursul reevaluat**, 2212 exact zero; alt tenant nu vede nimic.

## 5. Limite consemnate, cu declanșator

| # | Limita | Implicit reversibil | Se ridică |
|---|---|---|---|
| 1 | Suma în valută a unei decontări e derivată la cursul BNM; o plată în lei care nu e produsul exact lasă pe creanță un rest de rotunjire de cel mult ½ ban × curs, nepostat | rest neexplicat pe cont, vizibil în fișă | 5c: mișcarea în valută poartă suma și `bank_rate`; a treia pereche |
| 2 | O reevaluare fără nimic de postat blochează re-rularea pe aceeași dată; un document antedatat postat ulterior nu mai intră în ea | se reevaluează la data următoare | acțiune de „înlocuire" pe reevaluare, când cineva o cere |
| 3 | Casa și banca în valută nu sunt în perimetru | spus pe ecran | 5c înregistrează al doilea furnizor |
| 4 | Cursul de pe antet e al zilei documentului, nu al obligației fiscale | apelantul poate da cursul | `DN-04`, după citirea art. 108 (`OD-132`) |
| 5 | Nota de credit în valută trece prin aceeași conversie; nu e testată separat | — | primul caz real |

## Surse

- SNC „Diferenţe de curs valutar şi de sumă", pct. 4, 6, 8–15, 17–22, Anexa 1 — transcris în
  [`f2-x2-snc-situatii-financiare-si-diferente-de-curs.md`](../_input/cercetare/f2-x2-snc-situatii-financiare-si-diferente-de-curs.md)
  Partea II, redacția OMF 48/2019 și cea din 2013 (pentru `R17`).
- Legea nr. 287/2017, art. 7 alin. (2) — contabilitatea în valută se ține și în lei, și în valută
  (Spec B §7.1).
- Codul fiscal, art. 97 alin. (6), art. 98 alin. (2), art. 108 — **niciunul citit din text** (ADR-039
  §3.2–3.3 le afirmă fără fișier de cercetare; `c4-diferente-de-curs.md`: „textul primar nu a fost
  citit"); `OD-132`. Regula implementată e convenția reversibilă a zilei documentului, nu articolul.
- Planul general de conturi — 2211/2212, 5211/5212, 6226/7224, 6227/7225 (ADR-057, catalogul de roluri).
- `CLAUDE.md` — `R9`, `R10`, `R13`, `R14`, `R15`, `R17`, `R19`, `R28`, `C9`, `C10`, `C12`, `D2`, `D6`;
  ADR-049 (`P-3`), ADR-057, ADR-087 §5, Spec B §7.
