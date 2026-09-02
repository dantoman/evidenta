# ADR-090 — Registrele TVA se citesc pe perioada fiscală și sunt egale cu registrul contabil

- **Stare:** Acceptat — tehnic (arhitectură delegată), pe **varianta reversibilă** (lista de deblocare
  §B5); **forma prescrisă a registrelor (art. 118) rămâne necitită** și nu se pretinde aici
- **Data:** 2026-09-02
- **Decis de:** sesiunea de implementare (`evidenta-5f`); proprietarul confirmă sau răstoarnă alegerile
  din §4, fiecare cu declanșatorul ei
- **Închide:** partea structurală a registrelor din `F2.A6` — registrele pe `VatPeriod`, ușa perioadelor
  fiscale TVA, criteriul *„registrele dau, pe o lună, aceleași totaluri ca fișa conturilor
  `TVA_COLECTATA` / `TVA_DEDUCTIBILA`"* — bifat în test pentru ambele părți
- **Nu închide, deliberat:** forma prescrisă (art. 118, `F2.X2 (c)`); declarația (Ordinul IFPS
  1164/2012, text necitit); proratarea (art. 102 alin. (4)); radierea cu perioada ei finală (serviciul
  există, ușa nu); `OD-130`
- **Deschide:** `OD-132`
- **Atinge:** `accounting/periods` (ușa `vat-periods`; `open_vat_periods` cere înregistrare),
  `operations/tax` (`services/vat_register.py`, ruta `vat/…/registers/<side>`),
  `platform/documents` (`confirmed_of_types`, `vat_breakdown_of_many`, **`services/csv.py`** — scriitorul
  CSV, mutat din `accounting/ledger`), `accounting/events` (`posted_payloads_of`), `operations/sales` și
  `operations/purchases` (`details_of`), `platform/tenancy` (`registered_for_vat_over`), ecranul
  *Registrele TVA*, fișa companiei (perioadele)
- **Legate:** [ADR-039](039-valuta-si-perioade.md) §7 și §9, [ADR-088](088-statutul-fiscal-e-datat-si-stampilat.md),
  [ADR-089](089-tva-pe-documentele-comerciale.md)

> **REZERVĂ (`OD-83`), purtată din [ADR-089](089-tva-pe-documentele-comerciale.md):** motorul selectează
> tratamentul doar pe capabilități. Registrul **nu** rezolvă nimic pe statut: citește ce a înregistrat
> motorul (`vat_deductible` de pe eveniment) și nu-l re-derivează. Rezerva iese cu `OD-130`.

> **REZERVĂ (`OD-22`), purtată din ADR-089:** nicio cotă aici. Registrul afișează cota **de pe linie**,
> cum a fost rezolvată la data documentului; cât timp cotele sunt `draft`, documentele cu TVA nu există,
> iar registrul e egal cu un registru contabil gol pe 5344 — corect, nu util.

## 1. Ce se decide: forma registrului

**Registrul se citește pe perioada fiscală TVA** (`VatPeriod`, ADR-039 §7), nu pe luna contabilă. În
99% din luni coincid; la radiere nu, iar un registru cheiat pe containerul greșit e neraportabil exact
atunci. Apelantul numește **o zi**, `vat_period_for` găsește perioada sau refuză
(`periods.vat_period_not_found`) — niciodată un registru gol care s-ar citi ca „nu s-a vândut nimic".

| Rândul | Ce e | De unde |
|---|---|---|
| documentele | cele **postate** ale familiei (`types_owned_by(side)`), plasate după **data documentului** în perioadă | `platform.documents` — `posted_of_types` |
| și cele validate, nepostate | **numărate**, nu listate: `unposted` | `confirmed_of_types` (nou) |
| contrapartea | denumirea **legală** (`C39`) | `masterdata.partners.legal_names_for` |
| feliile de TVA | pe `(regim, cheie, cotă)`, din linii | `vat_breakdown_of_many` (nou) |
| felul (livrări) | factură / notă de credit; **nota de credit cu semn negativ** | `sales.details_of` (nou) |
| identitatea furnizorului (procurări) | numărul și data de pe hârtie, lângă ale noastre | `purchases.details_of` (nou) |
| deductibilitatea (procurări) | **din evenimentul postat**, `vat_deductible` (ADR-089) — `True` în 2252, `False` în cost, `None` dacă evenimentul a fost scris înaintea câmpului | `accounting.events.posted_payloads_of` (nou) |

**Criteriul lui `F2.A6`, măsurat:** total TVA livrări = rulaj net 5344 (credit − debit) pe lună; total
TVA procurări − TVA nedeductibilă = rulaj 2252. Ambele în `test_vat_registers.py`, cu notă de credit și
cu o achiziție de dinaintea înregistrării în același registru.

**Nu citește nicio tabelă a altui modul** — settlements a plătit lecția asta (ADR-087). Ce lipsea a
devenit serviciu public în modulul care ține tabela: două primitive în nucleul documentelor, câte un
`details_of` în vânzări și achiziții, un cititor de payload în `accounting.events` — singura suprafață
contabilă pe care un modul operațional o poate citi (`D3`).

## 2. Exportul, și scriitorul CSV coborât în nucleu

O linie **per document și cotă** — așa se citește un registru și așa i se verifică de mână totalurile pe
cote —, totaluri pe regim și un total la sfârșit, `ro-MD`, context românesc explicit (`C38`), denumirea
legală. Fișierul se numește `registrul-livrarilor-AAAA-LL.csv` / `registrul-procurarilor-…`.

**Scriitorul stătea în `accounting/ledger/services/export.py`**, pe care `operations/tax` nu-l poate
importa (`D3`). Două scriitoare care coincid până le editează cineva pe una e exact defectul din `C20`,
deci scriitorul a coborât în `platform/documents/services/csv.py` — stratul pe care îl pot folosi
amândouă —, iar `export.py` păstrează doar forma rapoartelor lui. Gardianul limbii documentelor
(`test_document_language.py`) rămâne pe el.

## 3. Perioada fiscală TVA cere înregistrare, și are ușă

`open_vat_periods` refuza până azi doar ferestre care nu erau luni întregi; **nu putea** verifica
înregistrarea, fiindcă `tenancy` nu publica niciun accesor de TVA — modulul o spunea în docstring. De la
ADR-088 publică, iar de azi fiecare lună deschisă trebuie să **atingă** o înregistrare
(`registered_for_vat_over`, suprapunere, nu includere: o lună în care compania a fost plătitor o singură
zi e o lună pe care declară) sau e refuzată cu `periods.vat_period_without_registration`. Ușa:
`GET/POST /api/v1/accounting/periods/companies/<id>/vat-periods`, cu ambele margini numite de apelant
— nu se deduce nimic din înregistrare pe server; fișa companiei propune anul și luna înregistrării.

**Radierea rămâne fără ușă**, deliberat: `close_vat_registration` (art. 114 alin. (2)) există din
F1.5.3 și e testat; consumatorul lui e declarația finală, care nu există.

## 4. Ce a fost alegere, enumerat — fiecare cu declanșatorul care o redeschide

| # | Alegerea | Ce s-a luat | Ce ar răsturna-o |
|---|---|---|---|
| **A** | data pe care un document intră în perioadă | **data documentului** — data pe care o poartă factura, nu data postării (ADR-039 §9 le desparte deliberat); un registru pe data contabilă ar muta o factură în luna în care a fost tastată | art. 108 citit (data obligației fiscale: livrarea, factura, plata) → `OD-132` |
| **B** | ce documente | **postate**, plus numărul celor validate-nepostate | un registru care trebuie să listeze și nepostatele — atunci coloana de stare, nu alt registru |
| **C** | nota de credit | **cu semn negativ**, în registrul livrărilor | forma prescrisă cu coloană separată de ajustări |
| **D** | deductibilitatea | **din evenimentul înregistrat**, nu re-derivată din statutul de azi | `OD-130`; sau un act care leagă deducerea de altă zi decât cea a ștampilei (`OD-131`) |
| **E** | perioada și înregistrarea | **suprapunere**, nu includere; luna cu o zi ca plătitor se declară | textul art. 114/112 despre prima perioadă la înregistrarea în cursul lunii (ADR-039 §7 o lasă deschisă) |
| **F** | exportul | **o linie per cotă**, totaluri pe regim | forma prescrisă |
| **G** | numele | *Registrele TVA*, cu subtitlul *nu este forma prescrisă* | citirea art. 118 și a formularului — atunci coloanele devin cele prescrise, iar numele devine *Registrul de evidență a livrărilor* |

## 5. Ce **nu** se decide aici

- Forma prescrisă a registrelor (art. 118) și a declarației (Ordinul IFPS 1164/2012, în redacția
  OSFS 20/2023) — textele necitite, `F2.X2 (c)`.
- Proratarea; dreptul de deducere pe scutiri (art. 103 / 104) — vocabularul le distinge, registrul le
  afișează pe regim, nimic nu le consumă.
- `OD-128` — ajustarea bazei la contractul în valută; nu apare, fiindcă nu există documente în valută.
- Ce se întâmplă cu documentele **anulate** după postare — nu există anulare după postare azi
  (stornoul e al registrului contabil); când va exista, registrul le va citi tot din stare.

## 6. Consecințe

- **Devine posibil:** o companie înregistrată își deschide perioadele de pe fișă și citește, pe fiecare
  lună, ce a livrat și ce a procurat cu TVA-ul pe cote — egal cu registrul contabil, cu numărul
  documentelor care încă nu sunt în el.
- **Devine imposibil:** o perioadă TVA pe o lună fără înregistrare; un registru gol care ascunde lipsa
  perioadei; două scriitoare CSV.
- **De modificat ca urmare:** enumerat la *Atinge*. `test_vat_period.py` primește înregistrarea în
  fixture — testele lui deschideau perioade pentru o companie care n-a fost niciodată plătitor, ceea ce
  de azi e refuz.
- **Măsurat pe baza de dezvoltare, 2026-09-02:** zero perioade TVA, zero înregistrări; ecranul nou e
  gol pe toate companiile demo și **spune de ce** (perioadele se deschid din fișa companiei, după
  înregistrare).

## Surse

- **Codul fiscal, Titlul III** — art. 114 (perioada fiscală; alin. (2) radierea), art. 118 (registrele
  de evidență a livrărilor și procurărilor — **conținutul necitit**, doar existența obligației, prin
  ADR-039 §7 și `od-22-tva.md`); art. 108 **necitit** (`OD-132`).
- ADR-039 §7 (perioada TVA ≠ perioada contabilă), §9 (documentul întârziat și cele trei date).
- ADR-089 §1 (forma postării cu TVA — ce anume adună registrul), ADR-088 (ștampila statutului).
- Măsurat: `backend/tests/isolation/test_vat_registers.py`, 6 teste sub rolul aplicației;
  `test_vat_period.py` +1.
