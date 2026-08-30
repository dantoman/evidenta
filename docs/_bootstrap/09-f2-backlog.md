# 09 — Backlog F2: Primul produs vandabil

- **Data:** 2026-08-30 (sesiunea `evidenta-87`)
- **Sursa ordinii:** `_input/evidenta-implementation-spec.md` §6 „FAZA 2", master planul V2 §10
  „Faza 2" și Amendamentul 1 §C.2 (două fluxuri paralele), §C.3 (rularea în paralel e funcție de
  produs), §D.1 (Compliance Admin). Harta modulelor: spec §4.1, `00-inventory.md` §2.5–2.7.
- **Obiectivul fazei:** *o companie de servicii cu angajați poate abandona complet 1C.* Primul release
  comercial.
- **Regula de dimensionare:** aceeași ca la F1 — o sarcină care atinge mai mult de un modul, sau care
  nu poate fi verificată printr-un criteriu clar, este prea mare. Fiecare sarcină încape într-o
  sesiune; unde nu încape, spune că e mai multe sesiuni și în ce ordine.
- **Statut:** scris **înaintea** închiderii criteriului de ieșire din F1 (trei din cinci puncte
  stau pe F1.10, corpusul — vezi `08-f1-backlog.md`). `CLAUDE.md` §4: *nu se scriu module din F2+
  înainte de criteriul de ieșire din faza curentă.* Acest document nu e modul: e descompunerea.
  Ce poate începe înainte de F1.10 și ce nu — §„Ce poate începe", explicit.

## Cum se citește o sarcină

Aceeași formă ca la F0 și F1 — `Obiectiv`, `Depinde de`, `Review`, `Terminat`, `Blocat de` — plus
**Definition of Done** (spec §7), care se aplică peste criteriul propriu: zero CRITICAL de la agenții
invocați, ambele suite de izolare verzi, test de lanț complet pentru fiecare efect financiar (`C12`),
test de idempotență pentru fiecare operațiune retriabilă, nicio decizie deschisă închisă tacit.

**Lista de blocaje se curăță** — regula învățată la F0, plătită iar la F1: din zece sarcini ale F1, cinci
erau blocate pe lucruri care nu se rezolvă scriind cod; patru s-au închis într-o zi, prin instrucțiune
scrisă, iar una (F1.5.4) era blocată pe o definiție greșită (`08`, §„Ce poate începe"). §„Tabelul de blocaje" e tabelul care se
verifică, nu se citește; când o decizie se închide, rândul se taie **în același commit**.

## Ce s-a schimbat față de F1, ca metodă

**1. F2 nu are specificație proprie.** F1 avea schema fixată de patru ADR-uri înainte de backlog
(ADR-036, 038, 039, 029) și Spec B în spate. Pentru F2, spec-ul de implementare dă „structură și
obiective" (antetul lui, rândul 5), iar ce e fixat stă împrăștiat: Spec B §4 (forma mapării document → postare, șase
exemple în cuvinte), §10.2 (cheile de deduplicare, ca **propuneri**, `DNB-11`), §5.2 (registrul de
logică, cu `regression_case_set` obligatoriu), §8.1 (setul „Angajați" din solduri); ADR-039 §3.3
(art. 98 alin. (2) e ajustare de bază TVA, nu diferență de curs — F2), §7 (perioada TVA e luna, și
**nu** e perioada contabilă; neregulată la radiere), §7.1 (termenele sunt parametri), §9 (linia de
salariu are două date: perioada de muncă și data de angajament); ADR-057 (`SettlementFact`, contractul
pe care `banking` îl emite). **Consecință:** fiecare flux își fixează schema printr-un ADR scris
înaintea codului — `F2.A0`, `F2.B0` — cu Planul general de conturi citat, exact cum `C1`–`C5` au cerut
SNC citat. Backlogul implementează ADR-urile; nu le redeschide.

**2. Două fluxuri paralele, un punct de convergență.** Amendamentul §C.2: Commercial/Tax (A) și
Payroll (B) merg în paralel după stabilizarea F1 și converg în raportarea statutară (C). În checkout
partajat asta înseamnă cel mult două sesiuni de implementare simultan, plus una pe C/P; regula din
`PROGRESS.md` rămâne: `git commit -- <căi>`, niciodată `add` urmat de `commit`.

**3. Blocajele externe se despart de construcție** — principiul din ADR-054 — motorul se validează separat
de cititorul de format — aplicat de la început, nu descoperit la sfârșit, și **extins aici** la
transport: **cititorul și transportul sunt adaptoare înlocuibile; modelul intern se construiește și
se testează primul.** Se aplică la extrasele bancare (`OD-27`), e-Factura (`OD-24`),
CNAS/CNAM/BNS (`OD-25`), canalul de depunere al declarațiilor SFS (**nou, `OD-75`** — nu e acoperit
de `OD-24`, care e strict e-Factura) și exportul de salarii din 1C pentru rularea în paralel (familia
`OD-28`). Un blocaj extern blochează **bifa finală** a sarcinii, nu sarcina.

**4. Valorile fiscale se încarcă `draft`, cu `confidence = provisional`; `active` e actul
proprietarului.** `OD-22`: niciun citat nu vine din textul legii, numerele de Monitorul Oficial lipsesc
pentru actele modificatoare, deci în baza de dezvoltare nimic nu trece `active` fără decizia lui.
**Măsurat:** `resolve_parameter` filtrează `status = active` — un rând `draft` nu e întors niciodată;
`provisional` e încredere (ADR-046), ortogonală statutului. Deci rândurile se încarcă `draft` (`F2.X1`),
testele le activează în baza de test cu identitatea de probă — exact drumul celor trei convenții de
precizie, `draft` → `active` cu `provisional` pe rând — iar producția așteaptă aprobarea. **Ce nu se
face:** o cotă scrisă în test „ca să meargă" — testul încarcă și activează rândul, apoi îl citește, ca
producția.

**5. Actele neobținute se citesc înainte de cod, nu se deduc.** `CLAUDE.md` §4: *nu se deduc reguli
fiscale, praguri, cote, termene sau formate de raportare din memorie.* Pentru F2 lipsesc mai multe
acte decât pentru F1 (vezi `F2.X2`); sarcina de cercetare precede sarcina de implementare, cu
fișier în `_input/cercetare/` și proveniența pe fiecare cifră, ca la `od-22-*.md`.

**6. Tăcerea actului e convenție de platformă, `provisional`, pe rând** (ADR-037 §0, ADR-055). Unde
formularul nu prescrie — de exemplu forma fluturașului — alegerea se scrie ca atare, nu se ridică la
rang de normă.

**7. Layout-ul e `operations/<modul>`.** Harta din spec §4.1 pune `tax/`, `payroll/`, `statutory/`,
`efactura/`, `banking/` la nivelul întâi; contractul de dependențe (`infra/modules/dependencies.toml`)
presupune `backend/evidenta/<strat>/<modul>/`, numește deja `evidenta.operations.tax` și
`evidenta.operations.payroll` în `D4`, iar `sales` și `purchases` stau în `operations/`. Un pachet la
nivelul întâi nedeclarat e `D0`. **`integrations/` (BNM, SFS, bănci) n-are strat** — nu e `platform`
(ar importa `operations` pentru payload), nu e `operations` (e canal, nu modul) — **nou, `OD-76`**,
de închis prin ADR înainte de primul conector; primul e BNM (`F2.A9`).

---

## F2.0 — Ce a fost „modelat" pentru F2, verificat

ADR-028: *„modelat în F0" e o obligație negativă — se verifică, nu se construiește.* Verificat pe
schema și codul din `HEAD` la 2026-08-30 — `f797799`, după commiturile C5 și F1.8 ale sesiunilor paralele. ✓ = există și e folosibil; **gol** = lipsește și are sarcină mai jos.

| Precondiție | Unde | Stare |
|---|---|---|
| Statutul de plătitor TVA al companiei, cu dată efectivă (Spec A §1.2) | `platform/tenancy` — `company_vat_registration` | ✓ |
| Statutul de plătitor TVA al partenerului | `masterdata/partners` — `partner_vat_registration`, `is_vat_registered(partner_id, on)` | ✓ |
| Antetul documentului: `currency`, `exchange_rate`, `rate_term` (pct. 19), `partner_id`, `document_date` / `accounting_date` | `platform/documents` — `Document` | ✓ |
| Tranziția `confirmed → posted` a documentului | `DocumentState.POSTED` e declarată și **nicio cale n-o atinge** (docstring-ul modelului o spune) | **gol → `F2.A1`** (prima folosire; refolosită de toate) |
| Linia de document: `net_amount`, `vat_regime_code`, `vat_rate_key`, `vat_rate`, `vat_amount`, `CHECK total = net + vat` | `platform/documents` — `DocumentLine` | ✓ |
| Documente comerciale ca tipuri înregistrate | `operations/sales` (`sales.document` cu `nature` ∈ delivery/advance, `sales.proforma`, `sales.order`), `operations/purchases` (`purchases.document`, `purchases.order`) — servicii `open_sale`, `open_purchase`, `convert_to_*` | ✓ **doar cochilii**: fără rută HTTP, fără serializatoare, **niciun `emit()`** |
| Deduplicarea facturii primite (Spec B §10.2, `R20`) | `purchase_document` — `UNIQUE (company, partner_id, supplier_document_number, supplier_document_date)` | ✓ (un prim răspuns la `DNB-11`, pentru un singur tip) |
| Vocabularul `source_module` | `accounting/events` — `sales`, `purchases`, `payroll`, `banking`, `assets`, `migration`, `manual`, `periods`, `production` (C5, migrarea `0003`) | ✓ |
| Contractul de înregistrare a evenimentelor (ADR-038): `register(EventType(...))` la nivel de modul, în serviciile modulului, importate din `ready()` (ADR-038 §5: nu în `AppConfig.ready()`) | `accounting/events/registry.py` — 8 tipuri azi | ✓ |
| Selecția tratamentului după capabilități (`R26`) | `accounting/events/registry.py` — `HandlerVersion.requires`; selecția în `posting/resolution.py` (`selected_treatment`); **niciun handler nu-l folosește** | ✓ mecanism, **neexersat → `F2.A2`** |
| Rolurile de cont pentru comerț: `VENIT_SERVICII`, `TVA_COLECTATA`, `TVA_DEDUCTIBILA`, `CREANTE_COMERCIALE_*`, `DATORII_COMERCIALE_*`, `AVANS_*`, `CASA_*`, `CONT_CURENT_*`, `DIFERENTA_*`, `ECART_CURS_BANCA_*` | `accounting/slots/data/roles_snc_2020.csv` — 46 după C5 | ✓ |
| Rolurile de cont pentru salarii (datorii salariale, CAS, CNAM) și pentru imobilizări corporale | catalog: doar `IMPOZIT_VENIT_SALARIU` (5342), `AMORTIZARE_IMOB_NECORPORALE` (113), `IESIRE_IMOBILIZARI_NECORPORALE` (7211) | **gol → `F2.B0`, `F2.A8`** (date din Planul general de conturi, act în repo) |
| Dimensiunile `employee_id`, `asset_id` pe linie (Spec B §1.7) | `journal_line` — coloane există, `NULL`, comentate `# F2` | ✓ |
| Decontarea (diferențele realizate) | `posting/services/settlement.py` — `settlement.differences.v1` pe `receivables.settlement_created` / `payables.settlement_created`, `SOURCE_MODULE = "banking"` | ✓ handlerul; **nu există entitate de decontare**, nici jurnal de solduri deschise → `F2.A3` |
| Rezidența partenerului și denominarea contractului — discriminatorul din ADR-057, *refuzat, nu presupus* | `Partner` are `kind` (legal_entity/individual), `idno`, `idnp`, **nimic despre rezidență**; `Document` n-are denominarea (valută / unități convenționale) | **gol → `F2.A3`** (migrare aditivă; forma o decide `F2.A0`) |
| Contul de creanță/datorie per partener și companie | `company_partner.receivable_account_code` / `payable_account_code` — **fără serviciu, fără rută** (`partners/services/directory.py`: nimic la F1 nu-l citește) | ✓ coloane; serviciul → `F2.A3` |
| Parametrii TVA | rezolvatorul `fiscal/parameters/services/vat.py` (`vat_rate`, `vat_regimes`, `assert_regime`) există; **niciun rând `vat.*` în niciun fișier de date** — `Item.vat_rate_key` și `DocumentLine.vat_regime_code` arată spre un vocabular fără rânduri | **gol → `F2.X1`** |
| Perioada fiscală TVA, distinctă de cea contabilă (ADR-039 §7) | `accounting/periods` — `VatPeriod`, `open_vat_periods`, `periods.vat_registration_already_closed` | ✓ |
| Cursul BNM ca tabelă globală | `accounting/currency` — `exchange_rate` (în `exceptions.toml`), `rate_on`, `latest_before`, `history` | ✓ tabela; **niciun conector** (`integrations/bnm` e F1 pe hartă și nu există) → `F2.A9` |
| Cele șase seturi de solduri inițiale (Spec B §8.1) | `accounting/opening` — GL, creanțe, datorii, stocuri, active, **`opening_balance_payroll_cumulative`** | ✓ toate; setul de salarii poartă **forma** lui `OD-04` și refuză conținutul (`code` neinterpretat, fără CHECK — docstring-ul spune de ce) |
| Capabilitatea ca entitate cu inițializare (`R25`) | `platform/capabilities` — `CapabilityActivation`, `initialisation_state`, `initialisation_ref`; `capability_key` e **text liber** (`DN-10` deschisă); `COMPLIANCE_CAPABILITIES = (vat, efactura, statutory_reporting)` nu se termină niciodată (`R24`, CHECK în bază) | ✓ structura; **`payroll` nu există ca rând sau cheie declarată** (apare doar ca exemplu în docstring-uri) → `F2.P3` |
| Registrul de logică fiscală, selectat după dată (`R17`, ADR-044) | `resolve_logic(logic_key, effective_date)`; două chei azi (`accounting.money_rounding`, `production.overhead_absorption` din C5) | ✓ (`OD-72` **neatinsă**: C5 a adăugat a doua *cheie*, cu o singură versiune — declanșatorul e a doua *versiune* a aceleiași chei, ADR-058 §4; prima versiune nouă a unei chei existente o va atinge, probabil în F2, la TVA sau la salarii) |
| Calea de scriere a datelor de referință (`P-4`, `P-10`) | `load_fiscal_parameters`, `activate_fiscal_parameters --approver`, `privileged_access_log`, registrul de acte (`platform/legislation`, `register_act`) | ✓ |
| Ștampila de parametru la postare (ADR-047) | `entry_parameter_stamp`, scrisă prima dată de C4 | ✓ |
| Antetul înregistrării cu `rule_ref`, `fiscal_effective_date`, `chart_template_id` (ADR-048 §3.3); linia poartă **data înregistrării** și **cel mult două zecimale** (ADR-059, `Propus`, așteaptă proprietarul) — motorul refuză întâi (`posting.line_date_differs`, `posting.manual_payload_malformed`), baza al doilea (`ledger/0004`, `infra/migrations/0062`) | `post_entry` / `reverse_entry` le cer | ✓ — fiecare handler F2 trece prin `post_formulas` și le moștenește, nu le reimplementează |
| Formularele contabile în română, fără limba activă (`C38`, ADR-033) | `platform/documents/formatting.py` (`decimal_ro`, `date_ro`; ro-MD fix) + `tests/architecture/test_document_language.py` (trei teste; al treilea: exportul în română oricare ar fi limba activă) — comise cu F1.8 (`f797799`) | ✓ |
| Pipeline de documente tipărite (`C22`) | **nu există** — niciun PDF generat server-side | **gol → `F2.P1`** (`OD-74`) |
| Utilizatorii de sistem (Spec A §3.4: `system:bnm`, `system:efactura`) | **nu există** (ADR-049 §7, `OD-71`) | **gol → `F2.P2`** |
| Corpusul de regresie (`C14`) | **nu există**: niciun director `corpus/`, marker `fiscal_regression` declarat și nefolosit; `regression_case_set` e coloană obligatorie cu două valori care arată spre nimic | **F1.10** — al F1, precondiție a tot ce urmează |
| Grilele | `DataGrid` există și servește F1.8, cu golurile numite (virtualizare, configurație per utilizator — F1.G1 **nebifată** în `PROGRESS.md`); `EntryGrid` livrat (F1.G2, `f797799`) | ✓; golurile `DataGrid` se plătesc la primul ecran F2 care le cere |
| Ecrane F2 | niciunul: rutele existente sunt companii, parteneri, plan de conturi, cont, note, balanță, registru, șabloane, solduri | **gol → `F2.G`** |

**Ce nu s-a verificat, fiindcă nu se poate încă:** performanța pe volum a fluxurilor noi (ADR-053 dă
praguri **propuse**, neconfirmate) și structurile pe care le va ridica un extras real — ambele se refac
pe date reale la primul pilot.

---

## Flux A — Commercial / Tax

### F2.A0 — Forma postării pentru documentele comerciale (ADR)

- **Obiectiv:** un ADR per familie de handlere, scris **înaintea** codului familiei, în sesiunea care
  o construiește: factura de vânzare (servicii; cu și fără TVA), factura de achiziție (servicii /
  cheltuieli; **fără** stocuri — F4), încasarea/plata (bancă, casă), avansul, nota de credit.
  Fiecare: evenimentul (`<modul>.<acțiune>`, două segmente — ADR-038 §3), rolurile cerute,
  condițiile (statutul TVA al companiei **la `accounting_date`**, Spec B §4.2 — nu un `if`),
  `required_capabilities`, invarianții suplimentari. Conturile se citesc din Planul general de
  conturi (`_input/cercetare/od-22-planul-de-conturi.md`, `od-23-*.md`) și intră în catalog ca
  **date**; ce SNC lasă la alegere e clasificarea proprietarului, ca la ADR-036 §11.
- **Întrebări pe care ADR-ul trebuie să le răspundă, nu să le ocolească:** (1) nota de credit / returul
  e `ReversalDocument` (există, `create_reversal`) sau un document de vânzare cu semn? — OMF 118/2017 e
  citit (`V1`), dar întrebarea *ce document se emite la retur* nu s-a pus; (2) avansul: `sales.document`
  cu `nature = advance` există — postarea lui (rolurile `AVANS_*` există) și legătura cu factura
  finală; (3) ce cheie de idempotență poartă evenimentul (`R19`: pe eveniment, nu pe endpoint) —
  propunere: identitatea documentului plus tranziția.
- **Depinde de:** F1.4.4 (contractele: `Formula`, `bind_roles`, ștampila), F1.10 (criteriul de ieșire).
- **Review:** `accounting-reviewer`, `fiscal-reviewer`.
- **Terminat:** ADR `Acceptat`, rolurile noi în catalog cu actul citat, `08`/`09` și registrul curate.
- **Blocat de:** — *(nimic extern; e lectura actelor din repo și decizia proprietarului unde actul lasă opțiuni)*.

### F2.A1 — Vânzări: de la document la înregistrare

- **Obiectiv:** factura de vânzare de servicii ajunge în registru. Rută HTTP pentru
  `open_sale` / linii / `validate` (numărul se alocă la validare — există); **TVA pe linie**, prin
  logica fiscală selectată după `accounting_date` (`vat.calculate_output` — Spec B §4.1; linia e
  autoritativă, ADR-037; `line_amounts` primește cota ca argument, iar rândul ei vine din `vat_rate(<cheie>, on)`, care refuză fără parametri); tranziția `confirmed →
  posted` = `emit(sales.invoice_issued)` + handler din `F2.A0`, în aceeași tranzacție, cu
  `Idempotency-Key` (`C9`); a doua postare a aceluiași document → aceeași înregistrare. Două
  tratamente pentru aceeași factură: companie plătitoare / neplătitoare de TVA — **a doua e
  absența liniei, prin condiție, nu prin `if`**. Ecranul (`F2.G`), factura tipărită (`F2.P1`).
- **Depinde de:** F2.A0, F2.X1 (rânduri `vat.*` provizorii), F1.G2 (`EntryGrid`).
- **Review:** `accounting-reviewer`, `fiscal-reviewer`, `tenancy-guard`.
- **Terminat:** test de lanț complet (`C12`) cu conturi și sume: factură → eveniment → înregistrare →
  linii, cu `partner_id` pe linia de creanțe (obligatorie pe cont, Spec B §1.7); același test pentru
  compania neînregistrată; idempotența; ștampila parametrului TVA pe înregistrare (ADR-047).
- **Blocat de:** `F2.A0`; valorile `active` — `OD-22` (bifa finală, nu construcția).

### F2.A2 — Achiziții: factura furnizorului

- **Obiectiv:** simetricul lui A1, cu ce e propriu achiziției: identitatea documentului furnizorului
  (`R20`, unicitatea există), regimul TVA pe linie (deductibil / nedeductibil / scutit — vocabularul
  vine din `vat_regimes(on)`, rândurile din `F2.X1`), `purchases.invoice_received`. **Prima folosire
  reală a `HandlerVersion.requires`:** tratamentul „fără stocuri" (cheltuieli / servicii) se
  înregistrează acum, cu `requires` gol; tratamentul „cu stocuri" e al F4 și se înregistrează atunci,
  cu `requires = {inventory}` — două reguli explicite, niciun `if` (Spec B §4.2). Testul de azi
  arată că profilul fără `inventory` alege tratamentul de azi; **nu** inventează o capabilitate ca să
  testeze cealaltă ramură.
- **Depinde de:** F2.A0, F2.X1.
- **Review:** `accounting-reviewer`, `fiscal-reviewer`.
- **Terminat:** `C12`; deduplicarea (același document furnizor de două ori → refuz cu cod, nu al
  doilea document); idempotența postării.
- **Blocat de:** `F2.A0`.

### F2.A3 — Creanțe și datorii: solduri deschise și decontarea

- **Obiectiv:** *decontarea e entitate proprie, nu coloană pe linia de jurnal* (Spec B §4.2).
  Entitatea `settlement` (`operations/receivables`, `operations/payables` — sau un singur modul de
  decontări; ADR-ul lui `F2.A0` decide): alocarea unei încasări/plăți pe unul sau mai multe documente,
  parțială, avansul stins (`settles_advance` din `SettlementFact`), soldurile deschise per partener
  și scadențele (`company_partner.payment_terms_days` există; contul per partener din
  `company_partner` primește serviciul care-i lipsește). La decontare se emite
  `receivables.settlement_created` / `payables.settlement_created` cu `SettlementFact` **complet**
  (ADR-057): `partner_resident` și `contract_denomination` se **află**, nu se presupun — de aici
  **migrarea aditivă** pe `Partner` (rezidența; cu sau fără valabilitate — de decis în ADR) și pe
  `Document` (denominarea contractului). Art. 98 alin. (2) — ajustarea bazei TVA la contract în valută
  decontat în lei — e **handler propriu** (ADR-039 §3.3), construit aici, cu evenimentul lui, fiindcă
  se declanșează la decontare; confuzia cu diferența de curs produce o declarație greșită.
- **Depinde de:** F2.A1 sau F2.A2 (ceva de decontat), ADR-057.
- **Review:** `accounting-reviewer`, `fiscal-reviewer`, `schema-reviewer` (migrarea).
- **Terminat:** `C12` pe: decontare integrală, parțială, avans, în valută cu diferență (reia cazul
  1000 × (19,6234 − 19,5000) din ADR-057 prin ușa nouă), art. 98 alin. (2); aceeași decontare de două
  ori → o singură înregistrare; raportul de solduri deschise per partener dă același total ca fișa
  contului (F1.8) pe contul de creanțe.
- **Blocat de:** `F2.A0`.

### F2.A4 — Bancă: conturi, extrase, potrivire, plăți

- **Obiectiv:** `operations/banking`. Contul bancar al companiei (IBAN, valută, banca); **extrasul
  în model intern normalizat** — antet și linii, cu cheia naturală propusă
  `(company_id, bank_account_id, statement_date, bank_reference)` (Spec B §10.2, `DNB-11`: de
  confirmat **ce garantează efectiv** banca, coliziunea = semnalare, nu refuz tăcut); cititorii de
  format sunt **adaptoare** (`OD-27` blochează cititorii, nu modelul; primul extras real le
  validează); **potrivirea** — sugestii calculate pe server, acceptate/respinse de om; `OD-41`
  observă că reconcilierea *probabil nu e o grilă*, ci un panou de potrivire în două coloane cu
  tastatură — se construiește așa și se măsoară, nu se alege prin analogie vizuală. Încasarea
  confirmată → `banking.payment_received` → decontare (`F2.A3`); plata → `banking.payment_made`;
  cursul băncii diferit de BNM → `bank_rate` din `SettlementFact` (perechea a treia din ADR-057).
  Ordinul de plată e document tipărit (`F2.P1`), cu formă reglementată — actul se identifică
  (`F2.X2`), nu se deduce.
- **Depinde de:** F2.A3, F2.P1 (pentru ordinul de plată).
- **Review:** `accounting-reviewer`, `tenancy-guard`, `schema-reviewer`.
- **Terminat:** import de extras sintetic în formatul intern → linii → sugestii → acceptare →
  decontare → înregistrare (`C12`); același extras de două ori → zero linii noi (`R20`); potrivirea
  fără mouse (`C40`).
- **Blocat de:** `OD-27` — **doar cititorii** și bifa finală pe extras real.

### F2.A5 — Casă

- **Obiectiv:** `operations/cash`. Casieria per companie și valută (`CASA_MDL`, `CASA_VALUTA`
  există), dispoziția de încasare și de plată, **registrul de casă** — registru contabil, deci
  document legal, în română (`C38`), generat server-side (`C22`, `F2.P1`); încasarea/plata în numerar
  a unei facturi trece prin aceeași decontare (`F2.A3`). Plafoanele și regulile operațiunilor cu
  numerar **nu se deduc**: actul se identifică în `F2.X2`; până atunci modulul înregistrează și
  postează, fără să pretindă că validează o limită pe care n-a citit-o.
- **Depinde de:** F2.A3, F2.P1, F2.X2 (actul casei).
- **Review:** `accounting-reviewer`, `fiscal-reviewer`.
- **Terminat:** `C12` pe încasare și plată; registrul de casă reconciliat cu fișa contului de casă pe
  aceeași zi; formularele tipărite trec `test_document_language`.
- **Blocat de:** `F2.X2` (actul operațiunilor cu numerar).

### F2.A6 — TVA: registre, declarație, corecții

- **Obiectiv:** `operations/tax` (numit deja în `D4`; `tax/codes`, `tax/vat`, `tax/declarations` pe
  hartă). Registrele TVA se construiesc din liniile de document validate/postate, **pe perioada
  fiscală TVA** (`VatPeriod` — luna, neregulată la radiere, ADR-039 §7), nu pe perioada contabilă;
  declarația pe formularul oficial (art. 115: „un formular oficial" — **denumirea și structura se
  citesc din act**, `F2.X2`; cercetarea `od-22-tva.md` nu le acoperă); termenul de 25 ca
  `fiscal_parameter` versionat (ADR-039 §7.1; „ultima zi a lunii" până la 01.01.2018 — `od-22-tva.md` §6);
  proratarea (Amd §B.1 o numește; articolul și formula — `F2.X2`); declarația **rectificativă** —
  rămâne în relația cu ADR-007 (`Propus`, trei întrebări): o corecție într-o perioadă TVA închisă e
  întâi o decizie de perioadă. Logica: `vat.calculate_output`, `vat.calculate_input`, proratarea —
  versiuni în registru, fiecare cu `regression_case_set` real (`F2.C5`).
- **Depinde de:** F2.A1, F2.A2, F2.X1, F2.X2 (formularul declarației, proratarea).
- **Review:** `fiscal-reviewer`, `accounting-reviewer`.
- **Terminat:** registrele dau, pe o lună, aceleași totaluri ca fișa conturilor `TVA_COLECTATA` /
  `TVA_DEDUCTIBILA` (F1.8); declarația se generează sub contextul românesc explicit; cazul radierii
  (perioadă peste o lună) are test; corpusul are cazurile TVA.
- **Blocat de:** `F2.X2` (formularul, proratarea); depunerea — `OD-75` (bifa „acceptată de SFS").

### F2.A7 — e-Factura / SFS

- **Obiectiv:** `operations/efactura`. **Intern, acum:** payload-ul din documentul de vânzare, generat
  sub contextul românesc deschis explicit (`C38`, ADR-033), cu denumirile legale (`C39`); arhivarea
  payload-ului ca atașament (`platform/attachments`; providerul — `OD-52`); starea documentului
  e-Factura ca mașină de stări (creat → validat → transmis → acceptat/respins → anulat), cu retry
  idempotent (`R19`); importul facturilor primite → `purchases` cu deduplicarea
  `(company_id, sfs_document_uid)` **și** cu cea a documentului furnizorului (același document pe
  două căi — Spec B §10.2 e exact cazul acesta); utilizatorul `system:efactura` (`F2.P2`).
  **Extern:** contractul API, autentificarea, statusurile, mediul de test — `OD-24`; transportul e
  adaptor; `V2` (schema XML) e testul de acceptanță al rotunjirii (ADR-037), nu sursa ei.
- **Depinde de:** F2.A1, F2.A2, F2.P2.
- **Review:** `fiscal-reviewer`, `tenancy-guard`.
- **Terminat:** payload-ul se generează dintr-o factură postată și e identic la a doua generare;
  starea nu sare o tranziție; factura importată de două ori (e-Factura + manual) → un document;
  `R24`: funcționează pentru orice tenant, fără rând de capabilitate.
- **Blocat de:** `OD-24` — transportul și bifa „acceptată".

### F2.A8 — Active fixe

- **Obiectiv:** `operations/assets`. Registrul activelor (`asset_id` pe linie există), punerea în
  funcțiune, **amortizarea lunară** — handlerul e `C2` din F1.4.4 (SNC „Imobilizări", pct. 19–28,
  cele trei metode de la pct. 22; `c2-amortizarea.md`); modulul emite evenimentul lunar per obiect și
  nu recalculează nimic din ce handlerul decide; transferul, casarea, vânzarea; setul
  `opening_balance_asset` există. Rolurile pentru imobilizări **corporale** lipsesc din catalog —
  date din Planul general de conturi, în ADR-ul familiei. **Amortizarea fiscală nu intră** (HG
  704/2019 neobținută — `08-f1-backlog.md` F1.4.4); consecința pentru VEN12 e în §„Întrebări".
- **Depinde de:** F1.4.4 `C2` (sesiunea care a livrat C4 și C5, `evidenta-77`; C2 urmează în ordinea proprietarului), F2.A0.
- **Review:** `accounting-reviewer`, `fiscal-reviewer`.
- **Terminat:** `C12` pe intrare, amortizare (12 luni, suma egală cu costul minus valoarea reziduală
  pe metoda liniară — cu actul citat), casare, vânzare; a doua rulare a lunii → nimic nou.
- **Blocat de:** `C2` nelivrat încă (în ordinea proprietarului: C5 → C2 → C1).

### F2.A9 — Valuta operațională: BNM și reevaluarea

- **Obiectiv:** conectorul BNM (`OD-26` — sursa oficială a cursului, format, frecvență), care scrie
  `exchange_rate` sub rolul de date de referință (`R5`, ADR-049: `privileged_run`, rând în jurnal) cu
  identitatea `system:bnm` (`F2.P2`) — calea `P-3` din Spec A §6.2, un rând în jurnal per rulare;
  task Celery pe calea privilegiată, nu pe cea normală cu `tenant_id` (`R6`): tabela e globală, nu
  există tenant de setat — exact cazul utilizatorului de sistem din Spec A §3.4;
  cursul de pe antet vine azi de la apelant (`open_draft` nu caută nimic); regula datei e scrisă — ADR-039 §3.2, art. 97 alin. (6) și
  art. 108 — deci ce lipsește e **căutarea**, care are sens abia cu conectorul; comentariul din
  `Document.exchange_rate` și ADR-057 §3.3 numesc întrebarea `DN-04`, etichetă pe care registrul a
  închis-o prin ADR-039 (moneda funcțională) — se reconciliază eticheta, nu se deschide un rând.
  **Reevaluarea soldurilor** (`accounting.revaluation_calculated`, Spec B §7.3) **nu intră** până la extragerea Anexei 1 din SNC „Diferențe de curs valutar și de sumă"
  (ADR-057 §3.3) — `F2.X2`.
- **Depinde de:** F2.P2, `OD-76` (unde locuiește conectorul).
- **Review:** `tenancy-guard`, `schema-reviewer`, `fiscal-reviewer`.
- **Terminat:** rularea de două ori a aceleiași zile → un rând; rândul din `privileged_access_log`;
  `rate_on` întoarce cursul zilei.
- **Blocat de:** `OD-76` (stratul), `OD-26` (contractul sursei); reevaluarea — Anexa 1.

---

## Flux B — Payroll

### F2.B0 — Schema salarizării (ADR)

- **Obiectiv:** un ADR care fixează, înaintea codului: `employee` (persoana: IDNP, rezidența fiscală,
  documentul scutirilor — art. 88 și `od-22-impozitul-pe-venit.md` §3), `employment_contract`
  (salariul, timpul de muncă, data începerii/încetării, funcția), **linia de salariu cu două date**
  — perioada de muncă și data de angajament (ADR-039 §9: *un salariu calculat în iunie pentru martie
  se acumulează în iunie*; ADR-044 §6: contribuțiile urmează contabilitatea de angajamente — așa s-a
  dizolvat conflictul aparent cu `R18` din Ordinul CNAS 31-A/2026 pct. 8), **asimetria structurală**
  din cercetare: CAS e obligația angajatorului, deci cheltuială; CNAM e reținere din salariat; *nu se
  modelează cu aceeași structură „cotă angajator + cotă angajat"*, iar contribuția individuală CAS e
  istorică (`valid_to = 2020-12-31`, Legea 60/2020); granularitatea postării (`DNB-05`: o linie per
  angajat și tip, agregat, sau agregat plus read model — decizie contabilă, cu volumul din
  `11-volume-model.md`); rolurile de cont (datorii salariale, CAS, CNAM, impozit reținut — Planul
  general de conturi); nivelul: angajatul e al **companiei** (angajatorul legal), nu al tenantului;
  `payroll` ca **capabilitate cu inițializare** (`R25`, `F2.P3`); cumulativele (`OD-04`, `F2.B6`).
- **Depinde de:** ADR-039 §9, ADR-044, cercetarea `od-22-cnas-cnam.md`, `od-22-impozitul-pe-venit.md`.
- **Review:** `fiscal-reviewer`, `accounting-reviewer`, `schema-reviewer`.
- **Terminat:** ADR `Acceptat`; `DNB-05` închisă (sau despicată explicit, cu ce rămâne).
- **Blocat de:** `DNB-05` (a proprietarului), `DN-10` (vocabularul capabilităților).

### F2.B1 — Angajați și contracte

- **Obiectiv:** `operations/payroll/employees`, `contracts`: CRUD, rute, ecran; datele personale sunt
  sensibile — accesul se auditează (`platform/audit`), iar `C37` rămâne: niciun termen de model în
  interfață. Dimensiunea `employee_id` se leagă de aici.
- **Depinde de:** F2.B0.
- **Review:** `tenancy-guard`, `schema-reviewer`.
- **Terminat:** izolarea (angajații companiei B invizibili din A, sub rolul aplicației — `T1`);
  contractul cu dată de încetare nu mai intră în rulare după ea.
- **Blocat de:** `F2.B0`.

### F2.B2 — Calculul salarial

- **Obiectiv:** `operations/payroll/calculation`, `contributions`: brut → CAS (angajator) → CNAM
  (reținere) → impozit pe venit (12%, art. 15; scutirile art. 33–35 cu *capcana de versionare* din
  cercetare §2.2 — regulamentul a rămas în urma Codului, ADR-045) → net; **fiecare pas e versiune de
  logică în registru** (`payroll.calculate_contributions` — exemplul din Spec B
  §5.2; o cheie pentru impozitul reținut, pe același tipar, nume de propus în `F2.B0`), selectată după **data de angajament** (ADR-044; rezolvatoarele iau data explicit, măsurat),
  cu parametrii din `F2.X1`. Rotunjirea per angajat și per contribuție: dacă actul prescrie, e a
  actului; dacă tace, e convenție `provisional` (metoda 6). Un caz de corpus per regulă înainte de a
  fi „gata".
- **Depinde de:** F2.B0, F2.X1, F1.10 (forma corpusului).
- **Review:** `fiscal-reviewer`.
- **Terminat:** cazurile din corpus trec; același angajat, aceeași lună, de două ori → același
  rezultat; recalcularea unei luni trecute cu parametrii de atunci (`R18`) are test.
- **Blocat de:** `F2.B0`; valorile `active` — `OD-22`.

### F2.B3 — Concedii și medicale

- **Obiectiv:** `operations/payroll/leave`: concediul anual, concediul medical (indemnizația, cine o
  suportă și pentru câte zile — **actul se citește**, `F2.X2`), baza de calcul (salariul mediu — are
  reglementare proprie, `F2.X2`), ca versiuni de logică cu cazuri în corpus.
- **Depinde de:** F2.B2, F2.X2.
- **Review:** `fiscal-reviewer`.
- **Terminat:** cazurile din corpus, cu actul citat pe fiecare.
- **Blocat de:** `F2.X2` (actele concediilor și indemnizațiilor).

### F2.B4 — Rulările: aprobare, postare, fluturași, plată

- **Obiectiv:** `operations/payroll/runs`: `payroll_run` cu cheia naturală propusă
  `(company_id, period_id, run_type)` (Spec B §10.2), stări `draft → calculated → approved → posted`;
  aprobarea emite `payroll.run_approved` → handlerul cu granularitatea din `F2.B0`; **fluturașul** —
  generat server-side sub contextul românesc (`C38`, `F2.P1`); conținutul minim, dacă e prescris, din
  Codul muncii (`F2.X2`), altfel convenție; lista de plată către bancă — formatul e al băncii
  (`OD-27`, adaptor).
- **Depinde de:** F2.B2, F2.P1, F2.A4 (contul bancar).
- **Review:** `accounting-reviewer`, `fiscal-reviewer`.
- **Terminat:** `C12`: rulare → eveniment → înregistrare, cu sumele per rol egale cu totalurile
  rulării; a doua aprobare → aceeași înregistrare; fluturașul trece `test_document_language`.
- **Blocat de:** `F2.B0` (`DNB-05`).

### F2.B5 — Rularea în paralel

- **Obiectiv:** `operations/payroll/parallelrun` — **funcție de produs** (Amd §C.3): rezultatele
  sistemului existent se importă per angajat și per componentă într-un model intern normalizat
  (cititorul 1C e adaptor — familia `OD-28`, F3), iar raportul de diferențe **la ban**, per angajat și
  per contribuție, se generează pe server (`C19`, `C20`) și se exportă. E echivalentul reconcilierii la
  zero diferență din migrare, și e punctul 3 al criteriului de ieșire.
- **Depinde de:** F2.B4.
- **Review:** `fiscal-reviewer`.
- **Terminat:** pe cazurile interne, raportul arată zero; pe un caz cu o diferență introdusă
  deliberat, o arată la ban și la angajatul corect.
- **Blocat de:** — *(cititorul formatului real: `OD-28`, bifa finală pe pilot)*.

### F2.B6 — Cumulativele la activarea în cursul anului (`OD-04`)

- **Obiectiv:** setul `opening_balance_payroll_cumulative` există ca formă și refuză conținutul;
  `OD-04` decide **ce** tipuri de venit și contribuții poartă `code`, semnul, și fereastra („de la 1
  ianuarie" vs exercițiul — `from_date` e purtat, nu presupus). Calculul continuă de la cumulative;
  `payroll` trece în `initialisation_state = complete` doar cu cumulativele încărcate pentru un start
  în cursul anului (`R25`, `initialisation_ref` există).
- **Depinde de:** F2.B0, F2.B2.
- **Review:** `fiscal-reviewer`, `accounting-reviewer`.
- **Terminat:** un angajat cu cumulative de la alt sistem primește, în luna activării, același
  impozit ca și cum tot anul ar fi fost calculat aici (caz de corpus).
- **Blocat de:** `OD-04` — **a proprietarului, „înainte de F2"**, deschisă din Amendamentul 1.

---

## Flux C — Raportarea statutară și conformitatea

### F2.C1 — Situațiile financiare SNC

- **Obiectiv:** `operations/statutory/financials`: bilanțul, situația de profit și pierdere, situația
  modificărilor capitalului propriu, situația fluxurilor de numerar, notele — formularele din SNC
  „Prezentarea situațiilor financiare" (în publicația consolidată MF a Ordinului 118/2013, deja
  descărcată pentru `C2`; **de extras**, `F2.X2`); categoriile de entități (Legea 287/2017; modificarea
  cu efect de la 1 ianuarie 2027 din ADR-039 §12 e primul test real al `R15`–`R18`) → ce set de situații,
  ca parametri cu `valid_from`; **maparea cont → rând de situație e date** (`R15` numește „mapări de
  conturi"; ADR-039 §10.2 vs ADR-050 — ADR-ul familiei spune dacă e parametru sau rol); generare
  server-side sub contextul românesc (`C22`, `C38`, `F2.P1`); totalurile de la server (`C19`).
- **Depinde de:** F1.8 (aceeași agregare ca balanța), F2.A6, F2.B4, F2.P1, F2.X2.
- **Review:** `accounting-reviewer`, `fiscal-reviewer`.
- **Terminat:** pe corpus, activul = pasivul și rezultatul din situația de profit și pierdere egal cu
  cel din balanță; situația capitalului propriu pentru un exercițiu închis.
- **Blocat de:** `F2.X2` (formularele); `OD-73` — reformarea bilanțului — **blochează situația
  modificărilor capitalului propriu la prima închidere reală de exercițiu**, exact declanșatorul scris
  în registru.

### F2.C2 — Rapoartele către SFS

- **Obiectiv:** `operations/statutory/sfs`: IPC21 (darea de seamă lunară a angajatorului și
  impozitul reținut, art. 92, până pe 25 — `od-22-impozitul-pe-venit.md` §5), IALS21/INR14 (anual),
  declarația TVA (`F2.A6`), VEN12 (impozitul pe venit al entității — vezi §„Întrebări": calculul lui
  cere ajustările fiscale, un calcul propriu). Formularele sunt acte publice (ordine SFS/MF) —
  cercetare, nu blocaj extern; **canalul de depunere** e `OD-75`. Termenele: parametri (ADR-039 §7.1).
- **Depinde de:** F2.B4, F2.A6, F2.X2.
- **Review:** `fiscal-reviewer`.
- **Terminat:** fiecare raport se generează sub contextul românesc din aceleași date ca înregistrările
  (diferență zero între IPC21 și rulările lunii); structura validată contra formularului citit.
- **Blocat de:** `F2.X2` (formularele); `OD-75` (depunerea — bifa „acceptat").

### F2.C3 — CNAS, CNAM, BNS

- **Obiectiv:** `operations/statutory/cnas`, `cnam`, `bns`. Ce mai primesc CNAS și CNAM direct după
  reforma din 2021 (declarația contribuțiilor a trecut prin darea de seamă unică — cercetarea o spune
  pentru calcul, nu pentru canal) e **exact întrebarea `OD-25`**, la fel formatele și canalele BNS.
  Intern: seturile de date care le alimentează există odată ce `F2.B4` postează; forma se scrie când
  se citește.
- **Depinde de:** F2.B4.
- **Review:** `fiscal-reviewer`.
- **Terminat:** raportul generat din aceleași date ca IPC21, cu diferență zero între ele.
- **Blocat de:** `OD-25` — **formatele și canalele**; nu se deduc.

### F2.C4 — Compliance Admin (instrument intern)

- **Obiectiv:** `fiscal/admin` — instrument al echipei, nu funcție pentru clienți (Amd §D.1). Fluxul:
  act publicat → **evaluarea impactului** (parametru? algoritm? schemă?) ca înregistrare legată de
  actul din registrul de acte (`platform/legislation`, există) → implementare cu dată efectivă
  (`load_fiscal_parameters`, `register_version` — există) → rulare pe corpus (`F2.C5`) → aprobare cu
  **identitate reală** (`OD-71`) → activare **programată** (`status → active la valid_from`, Spec B
  §5.3 — azi activarea e imediată, prin comandă) → comunicare către tenanți (`platform/notifications`).
  Tot pe calea privilegiată, cu rând în `privileged_access_log`. Fără ecran client; ecran de operator.
- **Depinde de:** F2.P2 (`OD-71`).
- **Review:** `tenancy-guard`, `fiscal-reviewer`.
- **Terminat:** un parametru încărcat azi cu `valid_from` mâine devine `active` mâine fără
  intervenție și e refuzat de rezolvator azi; rândul de jurnal poartă aprobatorul.
- **Blocat de:** `OD-71` (identitatea aprobatorului — „înainte de F2", a proprietarului).

### F2.C5 — Corpusul, extins la TVA și salarii

- **Obiectiv:** F1.10 dă forma (cazuri cu citare, `regression_case_set`, markerul
  `fiscal_regression`, `C14` în CI); F2 adaugă cazurile lui: TVA (cotele, scutirile, proratarea,
  radierea), salarii (scutiri, plafoane, luna cu cumulative, salariul retroactiv — cele două date),
  amortizarea, situațiile. Spec B §12: *cazurile corpusului sunt specificația executabilă a logicii
  fiscale* — se scriu **odată cu** logica, nu după. Rularea în CI la fiecare modificare de parametru
  sau algoritm (`C14`) — filtrul pe căile de date și de logică se definește la F1.10 și se
  verifică aici că prinde și fișierele noi.
- **Depinde de:** F1.10, fiecare sarcină de logică de mai sus.
- **Review:** `fiscal-reviewer`.
- **Terminat:** fiecare `regression_case_set` din `fiscal_logic_version` arată spre cazuri care
  există; o modificare de cotă într-un fișier de date declanșează rularea.
- **Blocat de:** F1.10.

---

## Sarcini transversale

### F2.P1 — Pipeline-ul de documente tipărite

- **Obiectiv:** `C22`: factura fiscală (OMF 118/2017, Anexele 1 și 2 — `V1` citită), ordinul de
  plată, dispozițiile de casă, registrul de casă, fluturașul, declarațiile, situațiile. Pipeline
  server-side care **deschide explicit contextul românesc la intrare** (ADR-033, `C38`), formatează
  prin `platform/documents/formatting.py` (ro-MD fix), folosește **doar denumirile legale** (`C39`);
  biblioteca PDF se pinuiește exact (`C28`; ADR-013 anticipa PDF/XML/Excel în F1–F2); **întrebarea e
  deja în registru: `OD-74`** (din F1.8: Excel și PDF cer bibliotecă, respectiv pipeline-ul din `C22`, și
  nu se aleg în treacăt) — această sarcină o închide, cu ADR; arhivarea documentului generat ca atașament. Nimic randat din React.
- **Depinde de:** F1.8 (`formatting.py`, la commit), `OD-52` (providerul de stocare — pentru arhivare).
- **Review:** `tenancy-guard`.
- **Terminat:** `test_document_language` extins: fiecare tip de document generat cu limba activă
  rusă iese în română; același document generat de două ori e identic byte-cu-byte (determinism, ca
  să poată fi arhivat și comparat).
- **Blocat de:** `OD-74` (biblioteca și pipeline-ul — se închide aici, cu ADR); arhivarea: `OD-52`, doar
  providerul.

### F2.P2 — Utilizatorii de sistem și identitatea aprobatorului

- **Obiectiv:** Spec A §3.4 e **specificat**: un `user` cu `is_active = false` și e-mail nefolosibil
  per tip de proces (`system:bnm`, `system:efactura`, `system:billing`), fără `membership`, deci fără
  acces pe calea normală — trece doar prin căile privilegiate, auditat. Se construiește după spec.
  **Ce e decizie, nu spec:** `OD-71` — cine semnează aprobările de parametri și versiuni de logică în
  producție (un utilizator real cu rol de operator al conformității?). Se despart: utilizatorii de
  sistem se fac; aprobatorul așteaptă decizia.
- **Depinde de:** —
- **Review:** `tenancy-guard`, `schema-reviewer`.
- **Terminat:** `IZ`-uri noi: utilizatorul de sistem nu citește nimic pe calea normală (sub rolul
  aplicației, `T1`); `P-3` (BNM) scrie cu identitatea lui în jurnal.
- **Blocat de:** `OD-71` — **doar aprobatorul**.

### F2.P3 — Capabilitatea `payroll` și vocabularul (`DN-10`)

- **Obiectiv:** prima capabilitate **non-conformitate cu inițializare** (`R25`): `payroll`, activată
  cu `effective_from` la început de lună, `initialisation_state = required` la start în cursul anului
  (`F2.B6`). `DN-10` — vocabularul: A (module), B (listă curatoriată după ce cere inițializare), C
  (ierarhie: „payroll de bază / complet" din master plan §13). **Tensiune de numit în ADR, nu de
  ocolit:** Spec A §1.8 pune *„payroll în măsura obligațiilor declarative"* la conformitate (nu se
  dezactivează niciodată, `R24`), iar §13 îl vinde pe planuri — linia dintre obligația declarativă și
  funcția comercială trebuie trasă de proprietar.
- **Depinde de:** —
- **Review:** `tenancy-guard`.
- **Terminat:** `capability_key` cu vocabular închis (CHECK sau enumerare în cod); testul că o
  capabilitate de conformitate cu `effective_to` e refuzată rămâne verde; profilul intră în
  `capability_snapshot` al evenimentelor de salarii.
- **Blocat de:** `DN-10` (a proprietarului).

### F2.P4 — Căutare globală, import/export

- **Obiectiv:** master planul F2 le numește fără detaliu. Căutarea: pe server, peste documente,
  parteneri, înregistrări, cu contextul de tenant din subdomeniu (`C8`) — un endpoint, un ecran.
  Exportul CSV există pentru balanță, fișa contului, Cartea Mare și corespondențe (F1.8, `C20`); registrul înregistrărilor nu-l are; se extinde per ecran nou. Importul: parteneri și
  articole din CSV (nomenclatorul de pornire al unei companii care nu vine din 1C).
- **Depinde de:** F2.G.
- **Review:** `tenancy-guard`.
- **Terminat:** căutarea nu întoarce niciun rând al altui tenant (`IZ` nou); exportul e identic cu
  ecranul.
- **Blocat de:** —

### F2.X1 — Parametrii fiscali ai F2, încărcați ca `draft` / `provisional`

- **Obiectiv:** TOML cu actul lângă valoare, prin `P-4` (`load_fiscal_parameters`), din fișierele de
  cercetare: TVA (`od-22-tva.md` — cotele art. 96, scutirile art. 103, pragul art. 112, termenul art.
  115), CNAS/CNAM (`od-22-cnas-cnam.md` — anexa nr. 1 la Legea 489/1999, anexa nr. 1 la Legea
  1593/2002, salariul mediu prognozat), impozitul pe venit (`od-22-impozitul-pe-venit.md` — art. 15,
  33–35, 88), calendarul de raportare (ADR-039 §7.1), cu `provisional_reason` = *numerele MO ale
  actelor modificatoare lipsesc* (`OD-22`). **Nu se activează** aici: activarea e `activate_fiscal_parameters --approver`, actul proprietarului, ca la convenții. Parametrii nescalari (scutirile
  pe categorii, tranșele) — `DNB-06` (forma lor) e **încă deschisă** în registru, deși F0.8.1 e livrată;
  prima grilă reală de aici o închide sau o dizolvă, cu ADR.
- **Depinde de:** — *(date, nu modul: poate merge înainte de F1.10)*.
- **Review:** `fiscal-reviewer`.
- **Terminat:** `load_fiscal_parameters` idempotent pe fișier; fiecare rând are act, articol și
  `confidence`; în baza de test, după
  `activate_fiscal_parameters --approver`, `vat_rate(<cheie>, 2026-01-01)` întoarce rândul cu
  `confidence = provisional`, iar un document de vânzare primește TVA pe linie.
- **Blocat de:** — *(activarea: `OD-22`)*.

### F2.X2 — Actele neobținute, citite înainte de cod

- **Obiectiv:** un fișier de cercetare per act, cu proveniența pe fiecare cifră și „ce nu s-a putut
  verifica" la final, ca la `od-22-*.md`: (a) operațiunile cu numerar — plafoane, dispoziții,
  registrul de casă (`F2.A5`); (b) concediile și indemnizațiile — actul, baza de calcul, cine suportă
  (`F2.B3`); (c) formularele SFS: declarația TVA, IPC21, IALS21, VEN12 — ordinele care le aprobă
  (`F2.A6`, `F2.C2`); (d) proratarea TVA — articolul și formula (`F2.A6`); (e) SNC „Prezentarea
  situațiilor financiare" — formularele, din PDF-ul MF deja descărcat (`F2.C1`); (f) Anexa 1 din SNC
  „Diferențe de curs valutar și de sumă" (`F2.A9`, reevaluarea); (g) ordinul de plată — forma
  reglementată (`F2.A4`); (h) conținutul minim al fluturașului, dacă e prescris (`F2.B4`); (i) HG
  704/2019 — amortizarea fiscală, dacă VEN12 intră în F2 (§„Întrebări"). Fiecare intră în registrul de
  acte (`register_act`) cu publicarea.
- **Depinde de:** — *(poate merge oricând; nu e modul)*.
- **Review:** `fiscal-reviewer` (pe fișier).
- **Terminat:** fiecare sarcină de mai sus care cita `F2.X2` are actul în repo sau „nu s-a putut
  obține", cu ce s-a încercat (ca la `V1`: Wayback după 403).
- **Blocat de:** accesul la `legis.md` (403) și Monitorul Oficial (cu plată) — **același blocaj ca la
  `OD-22`**; calea care a mers: publicațiile proprii ale MF/SFS/CNAS, arhiva Wayback.

### F2.G — Ecranele

Pe `DataGrid` și `EntryGrid`, fără a treia grilă (`C17`), cu contractul de tastatură (`C40`, ADR-052),
șirurile în `locales/` (`C32`), fără termeni de model (`C37`). Per sarcină: factura de vânzare și cea de
achiziție (`EntryGrid`), decontarea (panou, nu grilă — lista de solduri deschise e `DataGrid`),
potrivirea bancară (**panou în două coloane cu tastatură**, `OD-41`), casa, registrele TVA (`DataGrid`),
angajații și contractele, rularea de salarii (`DataGrid` cu drill-down la angajat), raportul de
diferențe al rulării în paralel, activele. Fiecare ecran are testul de fum Vitest peste `fetch` stubuit
(convenția din F1) și niciun total calculat în client (`C19`).

---

## Ordinea și paralelismul

```
înainte de F1.10 (fără cod de modul):
  F2.X2 cercetare ─┐
  F2.X1 parametri  ├─ oricând; decizii: OD-04, OD-71, DN-10, DNB-05, DNB-11, OD-75, OD-76
  09 (acest doc)  ─┘

după criteriul de ieșire din F1:
  F2.P2 utilizatori de sistem ──┐
  F2.P1 tipărire ───────────────┼──────────────────────────────┐
  F2.P3 capabilitatea payroll ──┘                              │
                                                               │
  Flux A:  A0 ─→ A1 ∥ A2 ─→ A3 ─→ A4 ∥ A5 ─→ A6 ─→ A7          │   A8 după C2 (F1.4.4)
                                                               │   A9 după P2 și OD-76
  Flux B:  B0 ─→ B1 ─→ B2 ∥ B3 ─→ B4 ─→ B5          B6 la OD-04 │
                                                               │
  Flux C:  C4, C5 cresc pe tot parcursul; C1 după A6 + B4 + P1; C2 după B4 + A6; C3 după B4 + OD-25
```

**Punctele de sincronizare, ca la F1 (unde o ordine plauzibilă dedusă din nume a fost greșită o dată):**

1. **`F2.A0` și `F2.B0`** — ADR-urile fixează rolurile și evenimentele; niciun handler înaintea lor.
2. **`F2.X1`** — fără rânduri `vat.*` active, `vat_rate()` refuză orice cheie și nicio linie nu primește cotă; A1 nu poate emite o factură.
   Măsurat: rezolvatorul există, datele nu.
3. **Tranziția `posted` a documentului** — se construiește o dată, în A1, și o refolosesc A2, A4, A5, B4.
4. **`F2.P1`** — factura (A1), ordinul de plată (A4), casa (A5), fluturașul (B4), situațiile (C1) au
   nevoie de același pipeline; se construiește înaintea primului dintre ele care e „terminat".
5. **`F2.A3`** — bancă și casă decontează prin aceeași entitate; nu două implementări.

**Ce poate începe acum, înainte de F1.10 — și ce nu.** `CLAUDE.md` §4 interzice *modulele* F2 înainte
de criteriul de ieșire, iar criteriul stă pe F1.10 (trei puncte din cinci), care vine după C5 → C2 →
C1 în ordinea proprietarului. Fără cod de modul, pot merge: acest document; `F2.X2` (lectură);
`F2.X1` (date, prin calea `P-4` care e a F1); și deciziile de mai jos, care sunt ale proprietarului.
**Nu pot merge:** `F2.A*`, `F2.B*`, `F2.C*`, `F2.P*`, `F2.G` — sunt module. Dacă proprietarul vrea
altfel, e schimbarea unei reguli din `CLAUDE.md` §4, deci ADR, nu excepție tăcută.

---

## Criteriul de ieșire din F2

Din spec §6, neschimbat — e al proprietarului:

- [ ] O companie reală de servicii funcționează exclusiv pe Evidenta timp de un trimestru
- [ ] Toate rapoartele lunare și trimestriale depuse din Evidenta, acceptate de instituții
- [ ] Rulare payroll în paralel cu diferență zero pe cel puțin trei companii-pilot

**Toate trei sunt externe** — cer un pilot real, canale de depunere reale, un trimestru de calendar.
Nu se rescriu. Ce se adaugă e ce a lipsit la F1 până la ADR-054: **ce se poate verifica intern, înainte
să existe pilotul**, ca să nu se descopere la pilot că motorul era greșit:

- fiecare efect financiar al F2 are testul lui de lanț complet (`C12`), cu conturi și sume;
- corpusul acoperă TVA, salarii, amortizare și situații (`F2.C5`), și rulează în CI (`C14`);
- raportul rulării în paralel arată zero pe cazurile interne și găsește o diferență plantată;
- fiecare raport lunar se generează sub contextul românesc și e validat **contra formularului citit**
  — nu contra instituției, care vine la pilot;
- diferență zero între registrele TVA și fișa conturilor de TVA, între IPC21 și rulări, între situații
  și balanță — aceeași agregare, două citiri.

Ce nu prinde verificarea internă — divergența dintre înțelegerea noastră și practica instituției — se
prinde la pilot; e același loc unde ADR-054 a lăsat divergența pentru F1.

---

## Întrebări pentru proprietar, ridicate de descompunere

Nu sunt decizii deschise de registru (nu blochează schema); sunt întrebări de **scop** la care
backlogul nu poate răspunde singur:

1. **VEN12 intră în F2?** O companie de servicii datorează impozit pe venit (12%, art. 15 lit. b),
   deci declarația anuală e „raport statutar". Dar calculul ei cere ajustările fiscale ale
   rezultatului contabil — inclusiv amortizarea fiscală (HG 704/2019, neobținută) — un calcul de
   sine stătător, cât un modul. Dacă intră, `F2.X2 (i)` devine obligatorie și `F2.C2` crește.
2. **Nota de credit și returul** — ce document se emite, în practica RM, la retur de servicii
   (`F2.A0` întrebarea 1)? Dacă proprietarul știe, e o propoziție; dacă nu, e cercetare.
3. **`DNB-05`** — granularitatea postării de salarii: decizie contabilă, cu volumul din modelul F0.11.
4. **`DNB-11`** — pentru extras bancar și e-Factura, coliziunea e **refuz** sau **suspectat duplicat
   cu decizie umană**? Spec B §10.2 înclină spre a doua; cere o stare pe document.
5. **`OD-04`, `OD-71`, `DN-10`** — marcate „înainte de F2" de la Amendament încoace; sunt ale lui.

---

## Tabelul de blocaje — se verifică, nu se citește

| Sarcină | Decizie | Natura |
|---|---|---|
| toate `F2.A*`, `F2.B*`, `F2.C*`, `F2.P*`, `F2.G` | criteriul de ieșire din F1 (F1.10) | `CLAUDE.md` §4; F1.10 vine după C5 → C2 → C1 (evidenta-77) |
| F2.A0, F2.B0 | decizia proprietarului unde SNC lasă opțiuni | ca la ADR-036 §11; actele sunt în repo |
| F2.A1, F2.A2, F2.B2 (bifa `active`) | `OD-22` — numerele MO | extern (acte normative); construcția merge pe `provisional` |
| F2.A4 (cititorii) | `OD-27` | extern (bănci); modelul intern nu așteaptă |
| F2.A5, F2.A6, F2.B3, F2.B4, F2.C1, F2.C2 | `F2.X2` — actele neobținute | lectură; blocat de acces (`legis.md` 403, MO cu plată), aceeași cale ca `V1` |
| F2.A6 (rectificativa) | ADR-007 `Propus` | a proprietarului (contabil) |
| F2.A7 (transportul) | `OD-24` | extern (SFS) |
| F2.A8 | `C2` din F1.4.4 | în lucru la evidenta-77, după C5 |
| F2.A9 | `OD-76` (stratul `integrations`), `OD-26` (sursa BNM); reevaluarea — Anexa 1 SNC | ADR; extern; lectură |
| F2.B0 | `DNB-05`, `DN-10` | a proprietarului |
| F2.B6 | `OD-04` | a proprietarului, „înainte de F2" |
| F2.C1 (capitalul propriu) | `OD-73` | a proprietarului; declanșatorul e prima închidere reală de exercițiu |
| F2.C2 (depunerea) | `OD-75` — canalul SFS | extern (SFS); **nou** |
| F2.C3 | `OD-25` | extern (CNAS, CNAM, BNS) |
| F2.C4, F2.P2 (aprobatorul) | `OD-71` | a proprietarului, „înainte de F2" |
| F2.C5 | F1.10 | al F1 |
| F2.P1 | `OD-74` (biblioteca, pipeline-ul — se închide în sarcină, cu ADR); `OD-52` (arhivarea) | ADR; providerul de stocare nu blochează generarea |
| F2.P3 | `DN-10` | a proprietarului |
| F2.X1 (activarea) | `OD-22` | extern; încărcarea ca `draft` nu așteaptă |

**Externe reale: patru instituții** — SFS (`OD-24`, `OD-75`), CNAS/CNAM/BNS (`OD-25`), băncile
(`OD-27`), BNM (`OD-26`) — plus accesul la textul legii (`OD-22`, `F2.X2`). **Ale proprietarului:
șase** — `OD-04`, `OD-71`, `DN-10`, `DNB-05`, `DNB-11`, ADR-007, plus clasificările din `F2.A0`/`F2.B0`.
Niciuna dintre cele externe nu blochează construcția; toate blochează câte o bifă.
