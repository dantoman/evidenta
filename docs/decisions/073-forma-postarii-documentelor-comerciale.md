# ADR-073 — Forma postării pentru documentele comerciale: factura emisă, factura primită, încasarea, plata

- **Status:** **Acceptat** — **decizie de domeniu** contabil, în regimul
  [ADR-010](010-contabilul-practicant.md) sub [ADR-002](002-guvernanta-deciziilor.md).
  **Ce e forțat de act nu e alegere**; unde SNC lasă opțiuni, §9 enumeră **fiecare** implicit luat,
  cu declanșatorul care îl redeschide — proprietarul răstoarnă oricare citind o singură secțiune.
- **Data:** 2026-08-31
- **Decide:** proprietarul proiectului
- **Închide:** `F2.A0`
- **Afectează:** `accounting/posting` (familia `commercial`), `accounting/slots` (două roluri noi),
  `operations/sales`, `operations/purchases`, `operations/treasury` (nou), `F2.A1`–`F2.A5`
- **Legate:** [ADR-036](036-forma-postarii.md), [ADR-038](038-vocabularul-de-evenimente.md),
  [ADR-048](048-formula-ca-unitate.md), [ADR-051](051-chei-de-context-enumerate.md),
  [ADR-057](057-diferentele-realizate-la-decontare.md), [ADR-065](065-schema-salarizarii.md) §7.1

> **REZERVĂ NEATINSĂ (`OD-85`):** acest ADR se sprijină pe
> [ADR-065](065-schema-salarizarii.md) **doar pentru tiparul din §7.1** — destinația alege rolul —,
> nu pentru tabelul de tarife CAS unde stă rezerva pe anexa nr. 1. Nicio valoare din anexă nu apare
> aici.

> **REZERVĂ (`OD-83`):** motorul ramifică **doar pe capabilități**, deci statutul TVA al companiei
> n-are pe ce selecta un tratament. Acest ADR **nu** îl rezolvă: fixează forma **fără TVA** și
> înregistrează un singur tratament per eveniment. Tratamentul cu TVA e al pasului 6 și **nu poate fi
> înregistrat** până când `OD-83` nu spune pe ce se selectează.

## 1. Ce se decide, și ce anume nu era o alegere

Patru familii de evenimente, cu forma lor:

| Eveniment | Debit | Credit | Sumă |
|---|---|---|---|
| `sales.invoice_issued` | `CREANTE_COMERCIALE_{TARA\|STRAINATATE}` | `VENIT_{SERVICII\|MARFURI\|PRODUSE}` | totalul documentului |
| `purchases.invoice_received` | rolul de cheltuială după destinație (§4) | `DATORII_COMERCIALE_{TARA\|STRAINATATE}` | totalul documentului |
| `treasury.receipt_recorded` | `CASA_MDL` / `CONT_CURENT_MDL` | `CREANTE_COMERCIALE_{…}` | suma încasată |
| `treasury.payment_recorded` | `DATORII_COMERCIALE_{…}` | `CASA_MDL` / `CONT_CURENT_MDL` | suma plătită |

**Niciuna dintre cele patru corespondențe nu e o alegere.** Planul general de conturi
(Ordinul MF nr. 119/06.08.2013) impune contul; ce rămâne de decis e **care rol se cere**, iar asta e
formă de postare, deci cod (`R28`) — nu configurare, nu DSL, nu evaluator peste `payload`.

**Ce e alegere e enumerat în §9, nu presărat.**

## 2. Discriminatorii se cer, nu se deduc — tiparul lui ADR-057

Trei perechi de roluri se aleg după o proprietate care **nu e derivabilă din sistem**:

| Perechea | Discriminatorul | De unde vine |
|---|---|---|
| creanță / datorie **țară** vs **străinătate** | `partner_resident` | **de pe faptul economic**, obligatoriu |
| venit servicii / mărfuri / produse | `revenue_kind` | de pe documentul de vânzare |
| cheltuială după destinație | `cost_destination` | de pe documentul de achiziție |

**Primul e cel care contează, și e refuz, nu implicit.** `Partner` **nu are** câmp de rezidență —
măsurat, nu presupus. [ADR-057](057-diferentele-realizate-la-decontare.md) a stabilit tiparul pentru
exact această situație: discriminatorul se cere pe fapt și **se refuză dacă lipsește**, fiindcă un
implicit „rezident" ar posta creanțele față de nerezidenți pe contul de țară — echilibrat, `R11`
trece, și greșit în bilanț la fiecare raportare.

## 3. Venitul: trei feluri, dar pasul 5 postează doar unul

`revenue_kind` are vocabular închis în cod — `services`, `goods`, `products` —, iar handlerul cere
rolul corespunzător. **Dar postează numai `services`**, și refuză celelalte două cu cod stabil.

Motivul nu e prudență: la mărfuri și produse, recunoașterea venitului e **jumătatea** înregistrării.
Cealaltă e descărcarea de gestiune — `COST_MARFURI` contra `STOC_MARFURI` —, iar ea cere stocuri, care
sunt **F4**. Un handler care ar posta numai venitul ar produce o lună în care marja e egală cu cifra de
afaceri: echilibrată, plauzibilă, falsă.

> **Refuzul e cu cod, nu tăcut** (`C10`): `sales.cost_side_requires_inventory`.

## 4. Cheltuiala: destinația alege **rolul**, nu legarea

Tiparul e fixat de [ADR-065](065-schema-salarizarii.md) §7.1 și se aplică identic aici: `cost_destination`
are vocabular închis în cod, iar handlerul cere rolul corespunzător. Destinația **nu** condiționează ce
cont se leagă la un rol — alege **care rol** se cere.

| `cost_destination` | Rol | Cont | Denumirea din act |
|---|---|---|---|
| `administrative` | `CHELTUIELI_SERVICII_ADMINISTRATIVE` | **7135** | Cheltuieli privind serviciile cu destinaţie administrativă | **nou** |
| `commercial` | `ALTE_CHELTUIELI_DISTRIBUIRE` | **7129** | Alte cheltuieli de distribuire | **nou** |
| `production_direct` | `PRODUCTIE_DE_BAZA` | 811 | Activităţi de bază | **există** |
| `production_indirect` | `COSTURI_INDIRECTE_PRODUCTIE` | 821 | Costuri indirecte de producţie | **există** |

**Două roluri noi, nu patru**, și verificarea e cea pe care ADR-065 §7 a plătit-o o dată: un al doilea
rând cu un nume existent ar rupe provizionarea **oricărei** companii, prin constrângerea de excludere de
pe `(company, rol)`. Cele două destinații de producție refolosesc rolurile care există.

**De ce 7129 pentru serviciile comerciale, și de ce numele rolului nu spune „servicii":** 712 nu are
subcont de servicii — are personal (7121), amortizare (7122), ambalaje (7123), transport (7124),
publicitate (7125), garanție (7126), creanțe compromise (7127), returnări (7128). Un serviciu comercial
care nu e niciunul dintre acestea cade la **7129, „Alte cheltuieli de distribuire"**. Rolul poartă
numele contului, nu al intenției — principiul catalogului e *un singur răspuns corect per rol*, iar un
rol numit `CHELTUIELI_SERVICII_COMERCIALE` ar fi sugerat un subcont care nu există.

## 5. Încasarea și plata: contul de trezorerie e al instrumentului, nu al documentului

`CASA_MDL` sau `CONT_CURENT_MDL` după **unde** au intrat sau ieșit banii, purtat pe faptul economic ca
`treasury_account` cu vocabular închis: `cash`, `bank`. Valuta e a pasului următor
(`CASA_VALUTA`, `CONT_CURENT_VALUTA` există în catalog și nu se folosesc încă — o încasare în valută
deschide diferențele de curs, care sunt [ADR-057](057-diferentele-realizate-la-decontare.md) și au
handlerul lor).

**Ce nu face acest ADR:** nu leagă încasarea de **factura** pe care o stinge. Postarea nu are nevoie —
debit trezorerie, credit creanțe, indiferent care creanță. Legarea (*ce factură s-a stins*) e
decontarea, cu handlerul ei de diferențe deja livrat, și e `F2.A3`.

## 6. Avansul: rolurile există, evenimentul nu se înregistrează încă

`AVANS_PRIMIT_TARA` / `_STRAINATATE` sunt în catalog, iar `sales.document` are `nature = advance`.
**Nu se înregistrează un tratament pentru el aici**, și motivul e că avansul nu e o formă de postare
în plus, e o **legătură**: încasarea în avans creditează avansul, iar factura finală îl stinge contra
creanței. A doua jumătate e decontarea din §5, deci avansul intră odată cu ea (`F2.A3`).

**Consemnat ca decizie de evitat, nu ca observație:** a posta azi doar prima jumătate ar lăsa soldul de
avansuri să crească fără nimic care să-l stingă, la fiecare client, permanent.

## 7. Nota de credit / returul: document de vânzare cu natură retur

`F2.X2 (j)` s-a făcut: **Instrucțiunea OMF 118/2017 anexa nr. 2 tace** asupra returului și a
corectării — zero potriviri, re-verificat 2026-08-30. Deci actul nu alege în locul nostru și alegerea
e a produsului.

**Se ia înclinația proprietarului**, consemnată la descompunerea F2: **document de vânzare cu natură
retur**, nu `ReversalDocument`. Returul unei prestări are aceeași structură de linii și același ciclu de
viață ca o livrare; doar semnul diferă. `ReversalDocument` e pentru **anularea unei erori**, nu pentru
un eveniment economic nou.

**Nu se construiește aici** — `nature` primește a treia valoare la `F2.A1`, cu `RETUR_REDUCERI` (7128)
ca rol de contrapartidă. **Ce ar răsturna alegerea:** schema e-Factura, dacă permite o singură formă
(`V2`, `OD-24`). → `OD-110`.

## 8. Idempotența, cheia, și de ce nu e endpointul

`R19` cere cheia **pe evenimentul contabil**. Forma, aceeași pentru toate patru familiile:

```
<event_type>:<document_id>
```

Identitatea documentului plus tipul evenimentului — propunerea din `F2.A0`, adoptată. **Nu tranziția**,
și corecția merită scrisă: un document trece o singură dată în `posted`, deci tranziția n-adaugă nimic
la identitate; iar dacă vreodată adaugă (o repostare după storno), aceea e **alt eveniment**, cu alt
tip, nu aceeași cheie cu alt sufix.

## 9. Ce a fost alegere, enumerat — fiecare cu declanșatorul care îl redeschide

| # | Alegerea | Ce s-a luat | Ce ar răsturna-o |
|---|---|---|---|
| **A** | rolul de venit pentru servicii | `VENIT_SERVICII` (611) | — SNC nu lasă opțiune |
| **B** | mărfuri/produse postate sau refuzate | **refuzate**, cu cod, până la stocuri (F4) | livrarea F4 |
| **C** | contul serviciilor comerciale | **7129**, fiindcă 712 n-are subcont de servicii | apariția unui subcont în plan |
| **D** | discriminatorul de rezidență | **cerut pe fapt, refuzat dacă lipsește** | un câmp de rezidență pe `partner`, care ar face derivarea legitimă (`OD-111`) |
| **E** | avansul | **nu se postează încă** (§6) | `F2.A3`, decontarea |
| **F** | returul | document de vânzare cu natură retur (§7) | schema e-Factura (`OD-110`) |
| **G** | TVA | **fără**, un singur tratament înregistrat | `OD-83`, pe ce se selectează statutul TVA |

## 10. Consecințe

- **Devine posibil:** factura emisă și cea primită ajung în registru prin motor, ca orice alt efect
  (`R9`); încasarea și plata la fel. `F2.A1`, `F2.A2`, `F2.A4`, `F2.A5` au forma fixată.
- **Devine imposibil:** o a doua cale către ledger pentru documente comerciale; un cont literal într-un
  handler; o creanță față de un nerezident postată tăcut pe contul de țară.
- **De modificat ca urmare:** `roles_snc_2020.csv` (două roluri), `accounting/posting` (familia
  `commercial`), `sales.document` (`revenue_kind`), documentele de achiziție (`cost_destination`),
  modul nou `operations/treasury`.
- **Un gol reparat odată cu asta, fiindcă altfel nimic din cele de mai sus nu postează:**
  `install_default_bindings` **nu era apelat de nicăieri** în afara testelor — deci nicio companie
  creată prin produs n-avea legări de roluri. Se apelează la **instanțierea planului**, singurul moment
  în care conturile există.

## 11. Surse

- **Planul general de conturi**, Ordinul MF nr. 119 din 06.08.2013 — nomenclatorul în
  [`od-23-nomenclatorul-planului-de-conturi.md`](../_input/cercetare/od-23-nomenclatorul-planului-de-conturi.md);
  conturile 7129, 7135, 811, 821, 611, 221, 521, 241, 242 citite acolo.
- **SNC „Venituri"** pentru recunoașterea venitului din prestări; **SNC „Cheltuieli"** pentru
  clasificarea pe destinații — prin `od-22-planul-de-conturi.md`.
- **Instrucțiunea OMF nr. 118/2017 anexa nr. 2** — citită, tace asupra returului (`F2.X2 (j)`,
  `v1-factura-fiscala-omf-118-2017.md`).
- [ADR-036](036-forma-postarii.md) §5.1 (rolurile, nu conturile), [ADR-038](038-vocabularul-de-evenimente.md)
  §3 (numele în două segmente), [ADR-057](057-diferentele-realizate-la-decontare.md) (discriminatorul
  refuzat, nu presupus), [ADR-065](065-schema-salarizarii.md) §7.1 (destinația alege rolul).
