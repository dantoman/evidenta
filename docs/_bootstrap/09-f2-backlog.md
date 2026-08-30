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
- **Statut, 2026-08-30:** **F2 pornită** prin declarația proprietarului; cele opt întrebări răspunse,
  cinci ADR-uri (060–064). Scris inițial **înaintea** închiderii criteriului de ieșire din F1 (trei din cinci puncte
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
| Parametrii TVA | rezolvatorul `fiscal/parameters/services/vat.py` (`vat_rate`, `vat_regimes`, `assert_regime`) există; la scrierea acestui tabel **niciun rând `vat.*`** — din 2026-08-30 (`F2.X1`, a doua încărcare) `tva.toml` are cinci rânduri **`draft`**, pe care rezolvatorul nu le întoarce până la activare (`status = active`, actul proprietarului) | ✓ structura; valorile `draft` → activarea e `OD-22` |
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
  citit (`V1`), dar întrebarea *ce document se emite la retur* nu s-a pus. **Înclinația proprietarului,
  2026-08-30, ca ADR-ul să nu pornească orb: document de vânzare cu natură retur, nu `ReversalDocument`
  — returul unei prestări are aceeași structură de linii și același ciclu de viață ca o livrare, doar
  semnul diferă; `ReversalDocument` e pentru anularea unei erori, nu pentru un eveniment economic nou.
  Nu e decizia finală: dacă schema e-Factura (`V2`, `OD-24`) permite o singură formă, alegerea e făcută
  în afara noastră. `F2.X2 (j)` se face ÎNAINTEA acestei sarcini;** (2) avansul: `sales.document`
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
  date din Planul general de conturi, în ADR-ul familiei. **Calculul** amortizării fiscale nu intră (VEN12 e amânat — `OD-79`), dar
  **registrul de active poartă dimensiunea fiscală de la primul obiect înregistrat**: categoria, data
  intrării sub regulile fiscale, pragul la intrare (art. 26¹ alin. (2)). Decis 2026-08-30, se
  consemnează în ADR-ul acestei familii chiar dacă VEN12 rămâne afară — HG 704/2019 (obținută,
  `F2.X2 (i)`) pct. 8–9 și anexa 1 cer registru statutar **per obiect**, iar un activ înregistrat fără
  categorie fiscală nu se poate reclasifica retroactiv fără să știi ce era la data intrării. Costul
  reconstrucției crește per obiect, deci partea structurală nu așteaptă răspunsul la scop.
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
- **Blocat de:** `OD-76` (stratul), `OD-26` (contractul sursei). ~~Reevaluarea — Anexa 1~~: obținută
  integral 2026-08-30 (`F2.X2 (f)`); ce mai lipsește reevaluării e ADR-ul familiei, nu actul.

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
  istorică (`valid_to = 2020-12-31`, Legea 60/2020); **granularitatea postării — decisă
  2026-08-30, varianta C** (`DNB-05`): linii **agregate pe rol** per rulare (cheltuială salarială,
  datorii salariale, CAS, CNAM, impozit reținut) și **formule per angajat** (`journal_formula`,
  ADR-048) cu `employee_id` într-un slot de dimensiune — `employee` e dimensiune numită din F1.2,
  coloana pe linie și sloturile pe formulă există. Drill-down-ul `R13` rămâne în contabilitate:
  rulare → formulă → angajat, fără să traverseze `D2` sau `D3`. Volumul, din `11-volume-model.md`:
  6 salariați ≈ 10 linii și 36 de formule; 200 de salariați, tot ~10 linii și ~1 200 de formule —
  liniile nu cresc cu angajații, formulele da, și sunt tabela făcută pentru asta. **ADR-ul
  consemnează că granularitatea nu e configurabilă, și că motivul e `R10`:** schimbarea ei după prima
  rulare postată nu e migrare, e campanie de storno și repostare; rolurile de cont (datorii salariale, CAS, CNAM, impozit reținut — Planul
  general de conturi); nivelul: angajatul e al **companiei** (angajatorul legal), nu al tenantului;
  `payroll` ca **capabilitate cu inițializare** (`R25`, `F2.P3`); cumulativele (`OD-04`, `F2.B6`).
- **Depinde de:** ADR-039 §9, ADR-044, cercetarea `od-22-cnas-cnam.md`, `od-22-impozitul-pe-venit.md`.
- **Review:** `fiscal-reviewer`, `accounting-reviewer`, `schema-reviewer`.
- **Terminat 2026-08-30:** [ADR-065](../decisions/065-schema-salarizarii.md) `Acceptat`; `DNB-05`
  **închisă** — detaliul per angajat în registru, o formulă per angajat şi tip de sumă. Trei revizori,
  **cinci CRITICAL**, toate confirmate pe sursă şi corectate înainte de semnare; unul a redeschis
  `DNB-05`, fiindcă argumentul de volum pe care se luase decizia era fals (§8.1) — decizia a rămas,
  motivele sunt altele. Deschise pe drum: `OD-81` (închisă prin refuz: parcurile IT nu intră în F2),
  `OD-83` (motorul ramifică doar pe capabilităţi), `OD-84` (accesul pe rapoartele cu dimensiune de
  angajat), `OD-85`, `OD-86`.
- **Blocat de:** — *(`DNB-05` **decisă 2026-08-30, varianta C**, și `DN-10` închisă prin [ADR-060](../decisions/060-vocabularul-capabilitatilor.md); ADR-ul acestei sarcini le poartă pe amândouă. **Prima sarcină a F2.**)*

### F2.B1 — Angajați și contracte

- **Obiectiv:** `operations/payroll/employees`, `contracts`: CRUD, rute, ecran; datele personale sunt
  sensibile — accesul se auditează (`platform/audit`), iar `C37` rămâne: niciun termen de model în
  interfață. Dimensiunea `employee_id` se leagă de aici.
  **Din `F2.X2 (k)`, trei cerințe care nu vin din calcul:**
  (1) **contractul e cap de serie** — `employment_contract_amendment` per act adițional
  ([ADR-067](../decisions/067-contractul-e-cap-de-serie.md)); „ce clauză era în vigoare la data D" se
  citește parcurgând seria, nu dintr-o coloană;
  (2) înregistrarea poartă **ordinul angajatorului** — dată, număr, tip de eveniment —, fiindcă
  termenul IRM19 de 10 zile lucrătoare curge *„începând cu ziua următoare după data indicată în
  ordin"*, nu de la contract; excepția explicită e funcția cu pensie în condiții avantajoase, unde
  *„nu se întocmește ordinul"*;
  (3) **`payroll_line` are cheie primară `UUID` și îngheață la `approved`**, prin trigger pe tiparul
  `rls.opening_balance_line_frozen` — `OD-87`, ambele obligatorii;
  (4) **categoria de plătitor CAS e a raportului, cu cea de pe companie ca implicit**
  ([ADR-068](../decisions/068-anexa-citita-categoria-e-a-raportului.md) §3) — nu din cazuri marginale,
  ci fiindcă un rezident de parc IT e simultan pct. 1.4 pentru salariaţi şi pct. 1.1 pentru
  contractele civile;
  (5) **constructorul declaraţiei nominale se scrie peste o populaţie de raporturi asigurate, nu peste
  tabela de angajaţi** ([ADR-069](../decisions/069-persoana-asigurata-nu-e-angajatul.md)): prestatorul
  pe contract civil e persoană asigurată cu cont personal şi apare nominal (art. 19 alin. (7) teza a
  doua), deci **„persoane asigurate" nu e submulţime a lui „angajaţi"**. Azi populaţia are un singur
  membru; **interfaţa e cea largă**, fiindcă lărgirea unei interogări scrise pe `employee` nu e
  extindere, e rescrierea fiecărui apelant.
- **Depinde de:** F2.B0.
- **Review:** `tenancy-guard`, `schema-reviewer`.
- **Terminat:** **reconcilierea populaţiei** — *orice persoană cu sarcină CAS în perioada `P` apare ca
  rând nominal în declaraţia `P`, **şi invers*** ([ADR-070](../decisions/070-trei-feluri-nu-o-familie.md)
  §5). **Reciproca contează la fel de mult:** un rând nominal fără sarcină e tot un defect. Se scrie pe
  date reale, **fără nicio structură nouă** — e singurul dintre cele patru defecte ale familiei care se
  prinde fără să se construiască ceva, şi n-a fost scris fiindcă populaţia se numea „angajaţi" şi părea
  evident completă. Apoi: izolarea (angajații companiei B invizibili din A, sub rolul aplicației —
  `T1`);
  contractul cu dată de încetare nu mai intră în rulare după ea; o clauză schimbată produce act
  adițional și lasă contractul inițial citibil; **test explicit pe lista negativă de excepții la
  suspendare** — suspendările din circumstanțe independente de voința părților, concediul pentru
  îngrijirea unui membru bolnav al familiei și concediul parțial plătit până la 3 ani **nu** se
  raportează cu codul 03. *E cea mai periculoasă dintre constatările mici ale lui `F2.X2 (k)`: o
  implementare care raportează orice suspendare produce declarații greșite, iar greșeala e tăcută.*
- **Blocat de:** `OD-87` — clasificarea append-only; tipul cheii primare o încorporează, deci nu se
  lasă pe seama primei migrări (măsurătoarea: `12-volumul-salarizarii.md`). ~~`F2.X2 (k)`~~ **făcută
  2026-08-30** ([`f2-x2-k-contractul-si-irm19.md`](../_input/cercetare/f2-x2-k-contractul-si-irm19.md)):
  art. 49 şi IRM19 obţinute integral, cu două constatări care **schimbă schema** — înregistrarea poartă
  **ordinul angajatorului** (dată, număr, tip de eveniment), fiindcă de el curge termenul de 10 zile, şi
  contractul are nevoie de **istoric de acte adiţionale**, fiindcă orice schimbare a oricărei clauze din
  art. 49 alin. (1) cere unul semnat. Depunerea rămâne blocată pe **Anexa nr. 4¹** (validările, text
  neobţinut) şi pe clasificatorul funcţiilor de la col. 11 — bifa, nu construcţia.

### F2.B2 — Calculul salarial

- **Obiectiv:** `operations/payroll/calculation`, `contributions`: brut → CAS (angajator) → CNAM
  (reținere) → impozit pe venit (12%, art. 15; scutirile art. 33–35 cu *capcana de versionare* din
  cercetare §2.2 — regulamentul a rămas în urma Codului, ADR-045) → net; **fiecare pas e versiune de
  logică în registru** (`payroll.calculate_contributions` — exemplul din Spec B
  §5.2; o cheie pentru impozitul reținut, pe același tipar, nume de propus în `F2.B0`), selectată după **data de angajament** (ADR-044; rezolvatoarele iau data explicit, măsurat),
  cu parametrii din `F2.X1`. Rotunjirea per angajat și per contribuție: dacă actul prescrie, e a
  actului; dacă tace, e convenție `provisional` (metoda 6). Un caz de corpus per regulă înainte de a
  fi „gata".
  **Invariantul art. 22 alin. (1), din anexa citită
  ([ADR-068](../decisions/068-anexa-citita-categoria-e-a-raportului.md) §5):** baza lunară a fiecărui
  salariat **nu poate fi sub salariul minim lunar pe ţară**, proporţional timpului lucrat; la timp
  parţial, contribuţia nu poate fi sub **25%** din cea calculată la salariul minim. E **logică**
  (`R16`), versionată şi cu caz de corpus — **nu parametru**; parametru e doar salariul minim.
  *Un handler care înmulţeşte baza cu cota îl ratează, iar declaraţia iese sub minim.*
  **Domeniu explicit ([ADR-069](../decisions/069-persoana-asigurata-nu-e-angajatul.md) §3): se aplică
  raporturilor de muncă, NU contractelor civile** — art. 22 spune „pentru fiecare **salariat**".
  Aplicat orbeşte pe orice bază CAS, umflă rândurile contractelor civile la salariul minim: datorie
  reală mărită tăcut şi **perfect echilibrată**, deci `R11` trece şi niciun test de sold n-o vede.
  **Test cerut:** o bază CAS de pe contract civil sub salariul minim rămâne sub el.
  **Şi cota împărţită de la pct. 1.5** — 24% evaluat, 18% suportat — cere `EmployerCharge` cu două
  sume (ADR-068 §4).
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
  deliberat, o arată la ban și la angajatul corect — **și o poate purta ca „diferență explicată", cu
  motiv**. Starea e cerută de criteriul rescris ([ADR-064](../decisions/064-diferenta-explicata-nu-diferenta-zero.md));
  forma ei — model, ecran, export — se decide aici, în tiparul lui `unassigned` din Cartea Mare: o
  diferență cinstită între două citiri, purtată vizibil, nu tolerată.
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
- **Blocat de:** — *(`OD-04` închisă prin [ADR-061](../decisions/061-cumulativele-de-salarii.md): trei chei, toate valorile pozitive, fereastra anului fiscal. `CHECK amount >= 0` e **deja aplicat**, prin migrarea proprie `opening/0002` din 2026-08-30 — nu mai e sarcină aici.)*

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
  declarația TVA (`F2.A6`), VEN12 — **amânat din F2, `OD-79`**, cu declanșator: *trimestrul de pilot
  traversează 31 decembrie*. Termenul e 25 martie, punctul 2 al criteriului numește doar rapoartele
  lunare și trimestriale, iar duratele de funcționare utilă (HG 941/2020, Catalogul) nu s-au obținut —
  „da" n-ar fi cumpărat o dată mai devreme. Formularele sunt acte publice (ordine SFS/MF) —
  cercetare, nu blocaj extern; **canalul de depunere** e `OD-75`. Termenele: parametri (ADR-039 §7.1).
  **Regulă de formular, fermă, din redacţiile IALS21 obţinute (2026-08-30):** pentru un rând de
  **zilier** se completează **doar coloanele 1, 2, 3, 5, 6, 7 şi 16**; redacţia din 08.05.2026 a
  **şters** paragraful cu scutirea personală. **Coloanele 8–15 pentru un rând de zilier sunt REFUZ la
  scriere, nu zero calculat** — un zero calculat arată ca o scutire acordată şi zero folosit, ceea ce
  formularul nu mai prevede.
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
- **Blocat de:** — *(`OD-71` închisă pe jumătatea „cine semnează", [ADR-062](../decisions/062-aprobatorul-din-productie.md): o persoană reală cu MFA, fără nivel nou de rol. Termenul e **înainte de prima activare în producție**, nu înainte de F2.)*

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
- **Blocat de:** F1.10 — **convenția, fixată de F1.10 (evidenta-04, 2026-08-30) și moștenită aici:**
  pachetul `backend/tests/corpus/` (README acolo); markerul `pytest.mark.fiscal_regression` se aplică
  **doar** prin `tests.corpus.citations.case(*sets, cites=(...))` — un test din pachet care n-a trecut
  prin `case()` cade la gardianul de integritate, deci „un caz care nu poate cita nu intră" e
  mecanic; numele seturilor `corpus/<logic_key>/<versiune>` când cazul fixează o regulă versionată,
  `corpus/<familie>/<versiune>` altfel; `test_corpus_integrity.py` citește fiecare `regression_case_set`
  din `fiscal/parameters/data/*.toml` și cade dacă un set n-are caz — deci un rând `[[logic]]` nou
  vine cu cazul lui în același commit; citările rezolvă la titlurile `###` din
  `_input/cercetare/f1-10-corpus-citari.md` sau la „ADR-NNN §x"; `-m fiscal_regression` selectează
  exact corpusul; convențiile se însămânțează din fișierele TOML livrate (`book.py`), deci o schimbare
  de `valid_from`/valoare/implementare ajunge în corpus (`C14`).

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
- **Blocat de:** — *([ADR-062](../decisions/062-aprobatorul-din-productie.md); utilizatorii de sistem erau oricum specificați în Spec A §3.4.)*

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
- **Blocat de:** — *([ADR-060](../decisions/060-vocabularul-capabilitatilor.md): `payroll`, `inventory`, `multi_company`, tuplu în cod materializat ca CHECK; `payroll` **nu** e capabilitate de conformitate, dar ieșirile lui declarative nu se dezactivează.)*

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
  actelor modificatoare lipsesc* (`OD-22`).
  **Din anexa nr. 1 la Legea nr. 489/1999, obţinută 2026-08-30
  ([ADR-068](../decisions/068-anexa-citita-categoria-e-a-raportului.md)): anexa nr. 3 — cele 43 de
  poziţii de drepturi şi venituri aferent cărora nu se calculează CAS**, nomenclator închis cu act pe
  fiecare poziţie; şi **salariul minim lunar pe ţară**, de care atârnă invariantul art. 22 (`F2.B2`).
  **Atenţie: anexa nr. 3 e ea însăşi listă cu redacţii** — poziţiile 42 (2 500 lei/lună pentru
  îngrijirea copiilor) şi 43 (funcţionari electorali) sunt adăugiri recente. **Fără margini, o poziţie
  lipsă nu dă eroare — dă CAS calculat pe un venit care trebuia exclus**, adică o datorie reală mai
  mare, echilibrată. Fiecare poziţie se încarcă cu actul ei şi cu `valid_from` din articolul final al
  actului, nu din data redacţiei (`OD-92`). **Nu se activează** aici: activarea e `activate_fiscal_parameters --approver`, actul proprietarului, ca la convenții. Parametrii nescalari (scutirile
  pe categorii, tranșele) — `DNB-06` (forma lor) e **încă deschisă** în registru, deși F0.8.1 e livrată;
  prima grilă reală de aici o închide sau o dizolvă, cu ADR.
- **Depinde de:** — *(date, nu modul: poate merge înainte de F1.10)*.
- **Review:** `fiscal-reviewer`.
- **Terminat:** `load_fiscal_parameters` idempotent pe fișier; fiecare rând are act, articol și
  `confidence`; în baza de test, după
  `activate_fiscal_parameters --approver`, `vat_rate(<cheie>, 2026-01-01)` întoarce rândul cu
  `confidence = provisional`, iar un document de vânzare primește TVA pe linie.
- **Blocat de:** — *(activarea: `OD-22`)*.
- **Făcut 2026-08-30, la instrucțiunea proprietarului („se încarcă, nu se activează"):** două fișiere
  în `fiscal/parameters/data/` — `cnas_cnam.toml` (4 acte, 7 parametri) și `impozit_pe_venit.toml`
  (3 acte, 8 parametri) — încărcate pe baza de dezvoltare prin `P-4`, **15 rânduri `draft`,
  `provisional` cu motivul pe fiecare**; a doua rulare: 0 noi, 15 neschimbate. Chei: `cnas.employer_rate`
  (24), `cnas.employer_rate_budgetary` (29), `cnas.late_payment_rate_daily` (0,1/zi), `cnam.employee_rate`
  (9), `cnam.employer_rate` (0 — inferență din clasificatorul bugetar, marcată), `cnam.fixed_premium_annual`
  (12 636), `labour.average_monthly_salary_forecast` (17 400, 2026), `income_tax.rate_individual` (12),
  cele cinci scutiri din 2025 (P, M, Sm, N, H) plus **`income_tax.exemption_spouse_ordinary = 0`** — rândul
  există ca scutirea care nu se acordă să nu fie inventată (capcana din cercetare; ADR-045), și
  `income_tax.exemption_income_cap` (360 000). **Ancorarea, spusă în fișier:** cotele CAS/CNAM stau în
  anexele la L. 489/1999 și L. 1593/2002, ale căror identități MO și date de intrare în vigoare nu s-au
  obținut; rândurile sunt ancorate în legea anuală care le aplică (2024, respectiv 2026), cu inferența
  marcată, și se re-ancorează la reîncărcare când `f2-x1-identitatile-actelor.md` le aduce — un rând
  `draft` se actualizează, unul `active` nu (R15). **Amânat, cu motivul:** TVA (`vat.regimes`,
  `vat.standard`, `vat.reduced`, pragul, termenul) și termenele din Cod — ancora e Codul fiscal, a cărui
  dată de intrare în vigoare nu e în nicio cercetare; contribuția individuală CAS = 0 din 2021 (data
  Legii 60/2020 lipsește); CNAM 2024–2025 și salariul mediu 2025 (datele HG/legilor lipsesc); scutirile
  2024 (actul neidentificat). Vocabularul cheilor e propus în fișiere și se confirmă în `F2.B0`.
  **A doua încărcare, aceeași zi, după `f2-x1-identitatile-actelor.md`:** `tva.toml` (Codul fiscal,
  Titlul III, ancorat pe clauza citită — 01.07.1998; L. 12/2026 cu publicarea) — `vat.regimes` (tabelul
  celor patru coduri peste art. 96 a/b, 103, 104), `vat.standard` (20), `vat.reduced` (8),
  `vat.registration_threshold` (1 700 000 din 01.03.2026), `vat.return_deadline_day` (25, din 2018);
  în `cnas_cnam.toml`: `cnas.employee_rate = 0` din 01.01.2021 (L. 60/2020, cu publicarea) și salariul
  mediu 2025 (16 100, **HG 845/2024** — nu „966", care era poziția), plus publicarea pe HG 773/2025.
  **Total: 22 de rânduri, toate `draft`, 0 în alt statut** — măsurat pe baza vie; a treia rulare a
  fiecărui fișier: 0 noi, 0 actualizați. Ferestrele `valid_from` ale cotelor TVA încep la 2024 — fereastra
  cercetată — nu la 1998: un `valid_from` mai vechi ar fi o afirmație necitită. **Rămân neîncărcate,
  cu motivul în fișiere:** pragurile anterioare ale art. 112 (actele neidentificate cu certitudine),
  lista art. 103 (structură din 2020, `DNB-06` deschisă), CNAM 2024–2025 (datele legilor), scutirile
  2024, cota persoanelor juridice (VEN12 e întrebare de scop).

### F2.X2 — Actele neobținute, citite înainte de cod

- **Obiectiv:** un fișier de cercetare per act, cu proveniența pe fiecare cifră și „ce nu s-a putut
  verifica" la final, ca la `od-22-*.md`: (a) operațiunile cu numerar — plafoane, dispoziții,
  registrul de casă (`F2.A5`); (b) concediile și indemnizațiile — actul, baza de calcul, cine suportă
  (`F2.B3`); (c) formularele SFS: declarația TVA, IPC21, IALS21, VEN12 — ordinele care le aprobă
  (`F2.A6`, `F2.C2`); (d) proratarea TVA — articolul și formula (`F2.A6`); (e) SNC „Prezentarea
  situațiilor financiare" — formularele, din PDF-ul MF deja descărcat (`F2.C1`); (f) Anexa 1 din SNC
  „Diferențe de curs valutar și de sumă" (`F2.A9`, reevaluarea); (g) ordinul de plată — forma
  reglementată (`F2.A4`); (h) conținutul minim al fluturașului, dacă e prescris (`F2.B4`); (i) HG
  704/2019 — amortizarea fiscală, dacă VEN12 intră în F2 (§„Întrebări"); **(j)** returul și corectarea
  facturii — recitirea țintită a Instrucțiunii OMF 118/2017, anexa nr. 2 (`F2.A0`; `V1` tace —
  re-verificat 2026-08-30, zero potriviri pe „retur", „corectare", „notă de credit", „anulare",
  „storno" în fișier). **(k)** **IRM19** — informaţia de angajare/modificare/încetare (10 zile lucrătoare, toţi angajatorii) — şi **Codul muncii art. 49**, clauzele obligatorii ale contractului individual: câmpurile lui `employment_contract` sunt azi derivate din ce consumă calculul, nu transcrise dintr-un act ([ADR-065](../decisions/065-schema-salarizarii.md) §11); **se citesc înaintea lui `F2.B1`**. **Prioritar: (j) se face înaintea lui `F2.A0`** — e cel mai ieftin punct deschis al
  fazei, un document deja în repo, și singurul unde răspunsul poate fi deja acolo.
  Fiecare intră în registrul de acte (`register_act`) cu publicarea.
- **Depinde de:** — *(poate merge oricând; nu e modul)*.
- **Review:** `fiscal-reviewer` (pe fișier).
- **Terminat:** fiecare sarcină de mai sus care cita `F2.X2` are actul în repo sau „nu s-a putut
  obține", cu ce s-a încercat (ca la `V1`: Wayback după 403).
- **Blocat de:** accesul la `legis.md` (403) și Monitorul Oficial (cu plată) — **același blocaj ca la
  `OD-22`**; calea care a mers: publicațiile proprii ale MF/SFS/CNAS, arhiva Wayback.

**Făcut 2026-08-30, la instrucțiunea proprietarului („în paralel, prioritate mare; tăcerea se
consemnează ca fapt datat"):** cinci fișiere `_input/cercetare/f2-x2-*.md` plus
`f2-x1-identitatile-actelor.md`, scrise în paralel, fiecare cu statutul sursei, proveniența pe cifră,
filtrul România aplicat și „ce nu s-a putut verifica" cu ce s-a încercat. **Ce a mers și ce nu, ca
metodă:** cuprinsurile edițiilor de pe `monitorul.gov.md` (`/ro/monitor/<id>`) sunt publice — de acolo
vin identitățile MO, inclusiv pentru ediții vechi, găsite prin sondarea id-urilor; `legis.md` întoarce
403 **și nu e arhivat de Wayback** (paginile sunt cochilii JS care încarcă `/cautare/rezultate/{id}`,
zero capturi, niciun PDF) — deci textul consolidat curent al niciunei legi n-a fost citit; textele
primare obținute integral sunt cele publicate de instituția autoare (PDF-ul MF al SNC, regulamentul
BNM, textele `.doc` ale MF pentru legile de punere în aplicare a Codului fiscal — nr. 1164/1997 și
nr. 1417/1997 —, proiectele de pe `gov.md`); codurile și legile s-au citit doar în consolidări
**până în 2019**, din copii care nu sunt ale emitentului (`lex.justice.md` prin Wayback, `usmf.md`,
NATLEX), marcate ca atare. Rezultatul pe act:

| Act | Identitatea (MO, intrare în vigoare) | Ce prescrie — obținut | Ce tace / ce lipsește | Fișier |
|---|---|---|---|---|
| (a) Normele operațiunilor de casă, **HG 764/1992** | doar numărul/data, din indexul `legis.md`; MO, intrarea în vigoare, modificările — **neobținute** | dintr-un răspuns SFS **arhivat**: un registru de casă per entitate, înscriere per dispoziție, **închidere zilnică** cu sold reportat, al doilea exemplar detașabil la contabilitate; dispozițiile de încasare/plată ca documente de bază | forma/coloanele, semnatarii, numerotarea, plafonul de casă; **statut incert** — răspunsurile SFS din 2022 nu-l mai citează, act de abrogare negăsit | `f2-x2-numerar-si-ordinul-de-plata.md` |
| (a) Plafoanele de numerar, **Legea 34/2024** | MO 86-88 din 01.03.2024, poz. 129; în vigoare **01.04.2025** (comunicat MF) | din comunicatul MF: 100 000 lei/lună cumulativ între persoane juridice și către persoane fizice; 100 000 lei per încasare de la persoane fizice; sancțiuni 3–10% / 10–18% / 0,1%/zi; numerarul eliberat spre decontare 30 de zile, restituire în 5 zile lucrătoare | textul adoptat necitit; **numerele articolelor neconfirmate**; proiectul din 2023 diferă de lege (15 → 30 zile) | idem |
| (a) Documentele primare, **Legea 287/2017 art. 11** | MO 1-6 din 05.01.2018, poz. 22 (`f2-x1`) | alin. (1), (4) în parafrază SFS | **alin. (7) — lista elementelor obligatorii — neobținută**; nicio formă MF în vigoare pentru dispoziții sau registrul de casă (BNS: formularele din 1995/1997 nu mai sunt valabile) | idem |
| (b) **Codul muncii 154/2003** | MO 159-162 din 29.07.2003, art. 648; în vigoare 01.10.2003 (art. 391) | art. 113 (min. 28 de zile calendaristice), 114, 114¹ (proporțional, 2022 — din proiect guvernamental), 117 (indemnizația ≥ salariul mediu, plătită cu ≥ 3 zile înainte), 165 | consolidare **martie 2019**; modificările LP 47/2024 (MO 111/22.03.2024, poz. 171), LP 193/2025 (MO 441-444/21.08.2025, poz. 602), LP 194/2025 — identificate, necitite | `f2-x2-concedii-indemnizatii-fluturas.md` |
| (b) Salariul mediu, **HG 426/2004** | MO 73-76 din 07.05.2004, art. 570; ultima modificare HG 685/2019 | pct. 3–5, 6–8, 10–12, 14: perioada de 3 luni (12 pentru categoriile listate), incluziuni/excluderi, normativele 29,4 / 21,1, formula pe zi calendaristică, 1/12 din premiile anuale, zilele de boală ale angajatorului la 75% | nicio modificare după 31.12.2019 găsită pe `gov.md`/MF — absență, nu dovadă | idem |
| (b) Indemnizațiile, **Legea 289/2004** | MO 168-170 din 10.09.2004, art. 773; în vigoare 01.01.2005 (art. 34) | art. 4 alin. (2¹): angajatorul plătește **primele 5 zile** (max. 15/an), BASS de la a 6-a; art. 5 alin. (4): CNAS plătește direct; art. 13: 60/70/90/100% după stagiu, angajatorul 75%; art. 7: venitul asigurat pe 12 luni, plafon 5 salarii medii prognozate; art. 6: stagiul 3 ani / 9 din 24 de luni; din 01.01.2024 partea angajatorului nu depinde de stagiu (Legea 241/2023, MO 318-321/18.08.2023, poz. 564) | consolidare **iulie 2019**; Legea 241/2023 necitită; actul certificatului medical | idem |
| (b) **HG 108/2005** (aplicarea Legii 289) | MO 24-25 din 11.02.2005, art. 162 | pct. 22, 67, 70, 90–91, 96–97 | consolidare până în 12.2018, copie pe `usmf.md` (nu emitentul) | idem |
| (h) Fluturașul | — | **Codul muncii art. 142 alin. (3):** la fiecare plată, în scris, trei elemente — componentele salariului, reținerile cu temeiul lor, suma netă | **nicio formă prescrisă** — tăcere datată 30.08.2026, după verificare la MF, SFS, ISM. Consecință: forma fluturașului e convenție de platformă cu minimul din art. 142 alin. (3) | idem |
| (c) **Declarația TVA** — Ordinul IFPS 1164/25.10.2012 | MO 234-236 din 09.11.2012, poz. 1375; aplicare din perioada 01/2013 (fragment) | șase modificări cu MO (OSFS 01/2020, 209/2021, 428/2021, 20/2023, **482/01.10.2025**, **529/04.11.2025**) | clauza de intrare în vigoare; conținutul modificărilor din 2025; **structura boxelor 1–24 e reconstituită din fragmente, contradictorie** — nu se folosește ca formă | `f2-x2-formularele-sfs.md` |
| (c) **IPC21** — OMF 94/30.07.2020 | MO 199-204 din 07.08.2020, art. 687; prima perioadă ianuarie 2021 | structura (tab. 1 col. 3–6, tab. 2 părțile I/II, anexa 3 clasificator, anexa 4 validări) din proiectele MF 2020/2022; zece modificări, nouă cu MO (OMF 14/2024 fără), ultima OMF 56/27.04.2026 | textul adoptat; OMF 14/2024 fără MO; **canalul: „metode automatizate de raportare electronică", niciun serviciu numit** | idem |
| (c) **IALS21** — OMF 95/30.07.2020; **INR14** — OMF 140/20.11.2017 | IALS21: MO 199-204 din 07.08.2020, art. 688; în vigoare 01.01.2021. INR14: **MO negăsit** | IALS21: cele 16 coloane + anexa (din proiect); modificare OMF 103/17.09.2024 (MO 400-401) | IALS21 tace asupra canalului (verificat pe proiect); INR14 există doar ca fragmente indexate | idem |
| (c) **VEN12** — OMF 153/22.12.2017 | MO 451-463 din 29.12.2017, poz. 2303 | structura rândurilor și anexelor din proiectul 2023; modificări 99/2023 (MO 426-429/14.11.2023, din anul 2023), 10/2024, 145/2024 | clauza de intrare în vigoare; canalul — tace | idem |
| (d) **Proratarea — art. 102 alin. (4)** Cod fiscal | alin. (3) până la 31.12.2019, renumerotat prin Legea 171/2019 (MO 393-399, poz. 319, 27.12.2019 — inferență din notele SFS) | **formula, verbatim din reproducerea SFS** (BGPF 28.21.1, Ordin SFS 384/13.08.2024): prorata lunară = livrări impozabile (fără TVA, fără avansuri) / (impozabile + scutite fără drept de deducere), rotunjită matematic la **două zecimale**; prorata definitivă pe indicatorii anuali, în declarația ultimei perioade, cu diferența acolo; rotunjirea 1 → 2 zecimale prin Legea 60/2020 | textul legii; alineatul regulii de minimis 0,05 | `f2-x2-prorata-tva-si-amortizarea-fiscala.md` |
| (e) **SNC „Prezentarea situațiilor financiare"** (OMF 118/2013, rescris integral prin OMF 48/2019) | ca la `snc_stocuri.toml`; PDF MF re-descărcat, md5 verificat, extras cu `pdftotext`, comparat cu copia MF din 2016 | **formularele transcrise integral, cod de rând + denumire + formule de control:** bilanț 116, bilanț prescurtat 23, profit și pierdere 44 / prescurtată 14, capital propriu 19, fluxuri de numerar 26; verificări încrucișate (rd. 180 SPP = rd. 570 bilanț etc.); **niciun tabel cont → rând** — fiecare rând are punctul lui de conținut; **`OD-73`: actul NU tace** — pct. 18 pune reformarea ca etapa 5, *după* aprobare, semnare și prezentare; **pct. 228:** *„După aprobarea şi prezentarea situaţiilor financiare entitatea reformează bilanţul/bilanţul prescurtat prin decontarea: (…)"* | data contabilă a înregistrării de reformare și legătura cu depunerea — tac; categoriile de entități din Legea 287/2017 (art. 4, 5, 21) citate doar din tabelele comparative ale proiectului guvernamental din feb. 2026 | `f2-x2-snc-situatii-financiare-si-diferente-de-curs.md` |
| (f) **SNC „Diferențe de curs valutar și de sumă", Anexa 1** | idem | **Anexa 1 integral**, cu Tabelul 1; pct. 6–15 (momentele), 17–26 (diferențele de sumă), 28; **caz `R17`/`R18` găsit:** pct. 11–12 rescrise prin OMF 48/2019 — avansurile au trecut din monetare în nemonetare la 01.01.2020 | — | idem |
| (g) **Ordinul de plată** — Regulamentul BNM, HCE 108/08.06.2023 | MO 220-222 din 29.06.2023, art. 632; în vigoare **05.08.2023**; modificat HCE 229/2025 (MO 523-525/132, în vigoare 09.04.2026); **text primar integral** | cap. II pct. 6–15 și Anexa 1: **13 elemente obligatorii** (numărul ≤ 12 caractere, IBAN 24, destinația ≤ 420, limba română, fără corectări); **set de date, nu formular tipărit** | predecesorul HCA 157/2013 (MO 191-197/1370): abrogarea necitită | `f2-x2-numerar-si-ordinul-de-plata.md` |
| (i) **HG 704/2019** (amortizarea fiscală) | nr. 704 din 27.12.2019; MO 400-406, poz. 1041 (31.12.2019, per SFS); în vigoare **01.01.2020** (pct. 3, citat); abrogă HG 289/2007; modificată prin HG 939/2020 (MO 372-382, poz. 1139) și HG 311/2023 (MO 182-185, poz. 411) | text din **proiectul ședinței Guvernului din 27.12.2019** (`gov.md`, prin Wayback), coincide cu fiecare punct citat de SFS: metoda liniară, calcul **anual** proporțional cu lunile — A = [(V · Na) / 12] · D (pct. 14), norma = 100% / durata (pct. 17), **per obiect**, în registru statutar (pct. 8–9, anexa 1), pragul delegat la art. 26¹ alin. (2) (12 000 lei per SFS, Legea 356/2022), reparațiile după SNC, cu plafonul de 15% la bunurile în locațiune, arendă, leasing operațional sau redevență; HG 311/2023 adaugă pct. 16⁴ | rotunjirea, valoarea reziduală, categoriile, legătura cu VEN12 — tac; **duratele de funcționare utilă stau în alt act — HG 941/2020, Catalogul (MO 372-382, poz. 1141) — neobținut**; HG 939/2020 necitită | `f2-x2-prorata-tva-si-amortizarea-fiscala.md` |
| (j) Returul / corectarea facturii | — | — | **neînceput** — recitirea Instrucțiunii OMF 118/2017 | — |
| **Identitățile actelor citate de parametri** (`OD-22`, `F2.X1`) | **17 din 21 confirmate pe pagina ediției MO** (număr, dată, poziție): L. 178/2018, 60/2020, 212/2023, 214/2024, 311/2024, 139/2025, 187/2025, 228/2025, 318/320/321 din 2025 (659-661, poz. 792/796/798), **L. 12/2026** (96-99, 26.02.2026, poz. 60 — titlul confirmă art. 112), **HG 773/2025** (620-622, 18.12.2025, poz. 785), HG 845/2024 (533-535, 19.12.2024, poz. 966), HG 697/2014, Ordinul CNAS 31-A (100-103, 27.02.2026, Partea III, 157), L. 287/2017 (1-6, 05.01.2018, poz. 22). **Parțial 4:** L. 489/1999 (MO 2000 nr. 1-4, art. 2), L. 1593/2002 (MO 2003 nr. 18-19, art. 57), Codul muncii — citate oficial în proiecte `gov.md`, fără pagina ediției; publicarea originară a Codului fiscal (MO 62 din 18.09.1997) **neconfirmată oficial** — oficial citată e republicarea din MO ediție specială, 08.02.2007. **Niciunul neidentificat.** | **Clauza de intrare în vigoare, citată verbatim, doar la Codul fiscal:** Titlurile I–II **01.01.1998** (L. 1164/1997), Titlul III **01.07.1998** (L. 1417/1997), din textele `.doc` ale MF. Pentru restul, data e afirmată de MF/SFS, nu citită din clauză | **corecție:** „HG 966/2024" din `od-22-cnas-cnam.md` e o confuzie — 966 e **poziția** în MO 533-535 din 19.12.2024; actul e **HG 845 din 18.12.2024** | `f2-x1-identitatile-actelor.md` |

**Consecințe pentru sarcini, fără să decidă nimic:** `F2.C1` nu mai așteaptă formularele — le are;
rămân `OD-73` (cu premisa corectată: actul numește momentul) și categoriile de entități necitite din
publicația proprie a Legii 287/2017. `F2.A9` nu mai așteaptă Anexa 1 — o are, cu un caz `R17`/`R18`
în plus. `F2.A4` are elementele ordinului de plată din text primar. `F2.B3` are regulile, în consolidări
din 2019 — modificările de după se citesc înainte de cod. `F2.B4` are minimul fluturașului (art. 142
alin. (3)) și tăcerea asupra formei. `F2.A6` are formula proratei (din reproducerea SFS) și identitatea
declarației, dar **nu structura ei** — boxele se citesc din formularul adoptat, care nu s-a obținut.
`F2.A5` rămâne cel mai descoperit: nicio formă în vigoare pentru registrul de casă și dispoziții,
art. 11 alin. (7) necitit, HG 764/1992 cu statut incert. `OD-75` rămâne externă: niciunul dintre ordinele SFS nu numește un serviciu electronic — declarația TVA
trimite la art. 187 alin. (2¹) din Cod, IPC21 la „metode automatizate (…) în modul reglementat de SFS",
IALS21 și VEN12 tac.
**`F2.X1` poate face a doua încărcare:** Codul fiscal are ancoră (01.07.1998 pentru TVA, 01.01.1998
pentru impozitul pe venit), L. 12/2026 și HG 773/2025 au publicarea, L. 60/2020 are MO — ce mai
lipsește e data de adoptare a unor legi, care se citește din fișier act cu act.

### F2.X3 — Recontrolarea blocajelor de acces

- **Obiectiv:** un blocaj de acces marcat „neobținut" rămâne așa la nesfârșit dacă nimeni nu
  recontrolează. **Declanșatorul e deja tras:** la 2026-08-30, în timpul lui `F2.X2 (k)`, **Wayback a
  devenit accesibil** din acest mediu — ceea ce în `f2-x2-formularele-sfs.md` și `f2-x1` era refuzat
  a funcționat, și a deschis instantanee `sfs.md` (care întoarce în continuare 403 direct). Actele de
  mai jos au fost marcate neobținute **din cauza accesului, nu a inexistenței**, înainte de această
  schimbare — deci merită o trecere:
  **(a)** IALS21 adoptat, Ordinul MF nr. 95/2020 cu modificarea nr. 103/2024 — extinde `OD-04`
  ([ADR-061](../decisions/061-cumulativele-de-salarii.md));
  **(b)** structura declarației TVA, boxele 1–24 — `F2.A6` nu are forma;
  **(c)** HG 941/2020, Catalogul duratelor de funcționare utilă — `OD-79`;
  **(d)** HG 704/2019 în text propriu, nu din proiectul ședinței de Guvern;
  **(e)** **redacţia curentă a anexei nr. 1 la Legea nr. 489/1999** — versiunea 2020 **a fost
  obţinută** la 2026-08-30 (de proprietar, ataşată la LP257/2020), deci structura nu mai lipseşte;
  ce rămâne sunt valorile pct. 1.5, 1.8 şi 1.9 (`OD-85`, restrânsă);
  **(f)** Ordinul MF nr. 33/2019, clauza proprie de intrare în vigoare — `OD-90`;
  **(g)** `legis.md` însuși, dacă a devenit accesibil.
- **Depinde de:** — *(lectură; nu blochează nimic)*.
- **Review:** `fiscal-reviewer` (pe fișier).
- **Terminat:** fiecare poziție ori are actul în repo, ori are „reîncercat la <dată>, tot inaccesibil,
  cu ce s-a încercat". **Tăcerea se reconsemnează, cu data nouă** — nu se lasă cea veche.
- **Blocat de:** — *(nimic; e chiar ridicarea unor blocaje)*.

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
făcut (2026-08-30):
  F2.X2 cercetare ─┐
  F2.X1 parametri  ├─ deciziile proprietarului: OD-04, OD-71, DN-10, DNB-05, DNB-11 — TOATE ÎNCHISE
  09 (acest doc)  ─┘  rămân externe: OD-75, OD-76, OD-22, OD-24…OD-27

F2 pornită; ordinea:
  F2.P2 utilizatori de sistem ──┐
  F2.P1 tipărire ───────────────┼──────────────────────────────┐
  F2.P3 capabilitatea payroll ──┘                              │
                                                               │
  Flux A:  A0 ─→ A1 ∥ A2 ─→ A3 ─→ A4 ∥ A5 ─→ A6 ─→ A7          │   A8 după C2 (F1.4.4)
           ↑ F2.X2 (j) înaintea lui A0                         │
                                                               │   A9 după P2 și OD-76
  Flux B:  B0 ─→ B1 ─→ B2 ∥ B3 ─→ B4 ─→ B5          B6 după B2  │   ← B0 e PRIMA sarcină a F2
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
altfel, e schimbarea unei reguli din `CLAUDE.md` §4, deci ADR, nu excepție tăcută. **2026-08-30, seara:** F1.10 e livrată
(`f8773ea`, evidenta-04) și cele cinci puncte ale criteriului de ieșire din F1 sunt bifate în
`08-f1-backlog.md`.

**Declarația a venit — 2026-08-30: „F2 pornește. Prima sarcină e `F2.B0`, cu `DNB-05` varianta C."**
Aceeași formă ca la F0, o propoziție a proprietarului. Cele opt întrebări ale fazei sunt răspunse
(§ de mai sus), cinci decizii au ADR și rândurile lor sunt tăiate din tabelul de blocaje în același
commit. **Ordinea de pornire, cu ce trebuie făcut înainte:** `F2.B0` (prima); `F2.X2 (j)` înaintea lui
`F2.A0`; `F2.P2` și `F2.P3` nu mai așteaptă nimic.

---

## Criteriul de ieșire din F2

Din spec §6, neschimbat — e al proprietarului:

- [ ] O companie reală de servicii funcționează exclusiv pe Evidenta timp de un trimestru
- [ ] Toate rapoartele lunare și trimestriale depuse din Evidenta, acceptate de instituții
- [ ] Rulare payroll în paralel pe cel puțin trei companii-pilot, cu, pentru fiecare, **fie diferență
      zero, fie fiecare diferență explicată una câte una**, cu motiv — **rescris 2026-08-30**,
      [ADR-064](../decisions/064-diferenta-explicata-nu-diferenta-zero.md): „diferență zero contra 1C"
      presupunea că 1C are dreptate, deci obliga produsul să fie la fel de greșit ca incumbentul ca să
      poată fi declarat gata

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

### Întrebarea reformulată, pe fiecare punct — raport, nu decizie

*Instrucțiunea proprietarului, 2026-08-30: „pentru fiecare: blochează construcția sau doar
validarea? Dacă structura se poate construi pe date interne și externul doar confirmă, punctul iese
de pe drumul critic și rămâne bifa finală. Raportează pe fiecare; nu decide."* Așa a plecat
importatorul 1C la F3 (ADR-054). Decizia de a rescrie criteriul e a lui.

| Punct | Ce validează de fapt | Blochează construcția? | Ce se construiește și se verifică intern | Ce rămâne extern — bifa |
|---|---|---|---|---|
| **1.** O companie reală de servicii, exclusiv pe Evidenta, un trimestru | Completitudinea produsului în uz zilnic și corectitudinea lui în practică — e **milestone-ul** („primul release comercial"), nu validarea unui modul | **Nu.** Nicio sarcină din `F2.A`–`F2.C` nu așteaptă pilotul ca să fie scrisă | **Trei luni consecutive închise pe o companie sintetică de servicii**, cu toate ieșirile lunare generate: facturi, decontări, extras, casă, trei rulări de salarii, trei închideri de lună, trei declarații TVA și trei IPC21, situațiile la trimestru — lanțul complet, pe corpus, în CI | Compania reală și trimestrul de calendar. **Consecință de calendar, de spus:** trimestrul nu se comprimă — dacă punctul rămâne în criteriu, F2 nu se poate închide mai devreme de trei luni după începutul pilotului, oricât de gata ar fi codul; ce se face în acele trei luni (F3?) e decizia lui |
| **2.** Toate rapoartele lunare și trimestriale **depuse din Evidenta, acceptate** de instituții | Două lucruri, cu naturi diferite: **generarea** corectă a formularelor (structura din act) și **depunerea + acceptarea** (canalul instituției și validatorul ei) | **Generarea: nu** — formularele sunt acte publice (`F2.X2 (c)`), se citesc și se validează contra formularului citit. **Depunerea: parțial** — transportul nu se poate construi fără contractul canalului (`OD-24`, `OD-25`, `OD-75`); modelul și fișierul, da | Fiecare raport generat sub contextul românesc din aceleași date ca înregistrările, cu diferență zero contra registrului (IPC21 ↔ rulări, TVA ↔ fișa conturilor de TVA, situații ↔ balanță); structura contra formularului; **exportul fișierului în formatul pe care portalul îl primește** — dacă portalul acceptă fișier, e aceeași structură publică | Canalul (API sau portal) și **acceptarea** — validatorul instituției e testul de acceptanță, ca `V2` pentru rotunjire (ADR-037). Se poate despica în două puncte: *generate și validate contra formularului* (intern) și *depuse și acceptate* (extern, bifa) |
| **3.** Rulare payroll în paralel, diferență zero, ≥ 3 companii-pilot | **Înțelegerea noastră contra practicii** — exact ce corpusul intern nu poate prinde (ADR-054 §2, „ce nu prind") | **Nu.** `F2.B5` e funcție de produs (Amd §C.3): modelul intern al rezultatelor celuilalt sistem, raportul de diferențe la ban, ecranul — toate pe date interne; **cititorul** exportului 1C e adaptor (familia `OD-28`, F3) | Raportul arată zero pe cazurile interne și găsește o diferență plantată la angajatul și componenta corecte. **Observație de construcție, ridicată aici:** „diferență zero contra 1C" presupune că 1C are dreptate — un Evidenta corect contra unui 1C greșit n-ar atinge niciodată zero; raportul are nevoie de o stare **„diferență explicată"** (cu motiv, ca `unassigned` din Cartea Mare), altfel punctul e imposibil de bifat cinstit | Cele trei companii-pilot și rezultatele lor reale — și, pentru fiecare, fie zero, fie diferențe explicate una câte una |

**Ce iese din raport, fără să decidă:** niciunul dintre cele trei puncte nu blochează construcția;
toate trei blochează câte o bifă; două (1 și 3) au un echivalent intern verificabil în CI, iar al
doilea se despică natural în „generat și validat" (intern) și „depus și acceptat" (extern). Tiparul e
identic cu ADR-054 — și, ca acolo, rescrierea criteriului e un ADR al proprietarului, nu o notă în
backlog. Până atunci, criteriul rămâne cum e, iar lista de mai sus e ce se poate bifa înaintea lui.

---

## Întrebările pentru proprietar — **toate opt, răspunse 2026-08-30**

**Răspunsurile, cu vehiculul fiecăruia.** Textul întrebărilor rămâne dedesubt, nemodificat: e
înregistrarea felului în care au fost puse, iar recomandarea sesiunii se citește lângă decizia care a
urmat-o.

| # | Decizie | Unde stă |
|---|---|---|
| 1. `OD-71` | **Varianta A** — aprobatorul e o **persoană reală cu MFA**, fără `membership` și fără nivel nou de rol; semnătura e identitate, nu permisiune. `B` vine cu `DN-18`, separat. Termenul devine **înainte de prima activare în producție**. Cele trei convenții semnate `dev@example.md` **rămân semnate** — append-only, nu se „repară" | [ADR-062](../decisions/062-aprobatorul-din-productie.md) |
| 2. `OD-04` | **Varianta B** — vocabularul metodei cumulative (`income_tax.taxable_income`, `.exemptions_granted`, `.withheld`), extins la IALS21 când actul adoptat e obținut; **nu se ancorează pe proiectul din 2020**. **Toate valorile pozitive**, `CHECK amount >= 0`: un cumulativ e o mărime, nu o mișcare | [ADR-061](../decisions/061-cumulativele-de-salarii.md) |
| 3. `DN-10` | **Varianta B** — `payroll`, `inventory`, `multi_company`. `payroll` **nu** e capabilitate de conformitate, dar ieșirile lui declarative nu se dezactivează. Ierarhia se amână, **ieftin doar fiindcă `SNAPSHOT_VERSION` există** | [ADR-060](../decisions/060-vocabularul-capabilitatilor.md) |
| 4. `DNB-05` | **Varianta C** — linii agregate pe rol, formule per angajat. **Nu e configurabilă**, iar motivul e `R10` | ADR-ul lui `F2.B0` |
| 5. `DNB-11` | **După cine garantează cheia** — refuz unde garantăm noi, „suspectat duplicat" unde garantează un terț; UID-ul SFS iese la `R19`. **Refuzul e implicitul reversibil** până când fiecare sarcină ajunge la cheia ei | [ADR-063](../decisions/063-coliziunea-se-decide-dupa-cine-garanteaza.md) |
| 6. VEN12 | **(i) Amânat**, declanșator: *pilotul traversează 31 decembrie*. **(ii) Nu se amână:** registrul de active poartă dimensiunea fiscală de la primul obiect | `OD-79`; partea (ii) în ADR-ul lui `F2.A8` |
| 7. Returul | **Proces:** `F2.X2 (j)` **înaintea** lui `F2.A0`. **Înclinația proprietarului:** document de vânzare cu natură retur, nu `ReversalDocument` — aceeași structură de linii și același ciclu de viață ca o livrare. Nefinal: schema e-Factura poate decide în locul nostru | `F2.A0`, după `F2.X2 (j)` |
| 8. Criteriul | **Punctul 3 rescris acum** — *diferență explicată*. Punctele 1 și 2 amânate, declanșator: alegerea companiei-pilot. Starea de produs e a lui `F2.B5` | [ADR-064](../decisions/064-diferenta-explicata-nu-diferenta-zero.md) |

**Ce a schimbat sesiunea în propria recomandare, consemnat fiindcă e prima dată:** recomandarea
inițială era ca `OD-71` să se decidă *împreună* cu `DN-18`. A fost **retrasă de sesiune**, cu motivul
verificabil — raze de acțiune diferite: aprobatorul atinge doar tabele globale, `DN-18` atinge datele
tenantului, RLS și `R27` — și cu precedentul `OD-22`, care a blocat două sarcini luni de zile lipind
un parametru fiscal de o structură de plan de conturi.

---

### Textul întrebărilor, păstrat

*Instrucțiunea din 2026-08-30: cele cinci de scop, cele trei „înainte de F2", `DNB-05` și `DNB-11` —
cu ce blochează fiecare și cu recomandarea sesiunii unde există una. `OD-71` primul.* Recomandarea e
a sesiunii, cu sursele ei; decizia e a proprietarului și se consemnează în ADR, nu aici.

1. **`OD-71` — aprobatorul din producție.** *Ce e:* fiecare activare de parametru și de versiune de
   logică pune `--approver` pe rând și pe rândul `P-4` din jurnal; azi identitatea e `dev@example.md`,
   contul creat de `make create-tenant`, deci în producție ar semna un cont de probă. *Ce blochează:*
   orice activare în producție (deci `F2.X1` la trecerea în `active`), `F2.C4` (Compliance Admin),
   jumătatea „aprobator" din `F2.P2`. *Recomandarea sesiunii:* **două lucruri, despărțite.**
   (a) Utilizatorii de sistem pentru rulările automate (`P-2`, `P-3`) sunt **specificați** în Spec A
   §3.4 — `is_active = false`, e-mail nefolosibil, fără `membership`, doar căi privilegiate — se
   construiesc fără decizie. (b) Aprobatorul e o **persoană**: un `user` real, cu MFA (ADR-021),
   angajat al platformei, nu al unui tenant — și aici e golul: **nu există niciun rol de nivel
   platformă** (măsurat: `platform/identity`, `platform/tenancy` n-au nimic asemănător), iar decizia
   vecină e `DN-18` (accesul de suport al platformei, `P-7`). Recomandare: se decid împreună, ca
   „identitățile personalului platformei" — aprobatorul atinge doar tabele globale, deci nu atinge
   nici RLS, nici `R27`; un rol `platform_operator` pe `user`, fără `membership`, cu MFA, e forma cea
   mai mică. Rândurile deja aprobate cu `dev@example.md` (cele trei convenții) nu se editează —
   jurnalul e append-only — ci primesc, la prima identitate reală, un eveniment nou de aprobare.
2. **`OD-04` — cumulativele de salarii la activarea în cursul anului.** *Ce e:* setul
   `opening_balance_payroll_cumulative` există ca formă și refuză conținutul — `code` e text
   neinterpretat, `from_date` e purtat. *Ce blochează:* `F2.B6`, activarea `payroll` la mijloc de an
   (`R25`), corectitudinea impozitului din prima lună. *Recomandarea sesiunii:* vocabularul lui `code`
   nu se inventează — **vine din metoda cumulativă a reținerii**: HG 697/2014 pct. 38 — calculul se face prin metoda cumulativă, de la începutul anului
   fiscal sau de la data angajării (parafraza din `od-22-impozitul-pe-venit.md` §3, nu citat verbatim). Ce trebuie purtat de la 1 ianuarie, per angajat, e deci ce
   intră în acel calcul: venitul impozabil cumulat, scutirile acordate cumulat, impozitul reținut
   cumulat — plus ce cer rapoartele anuale per angajat (IALS21), a căror listă de coloane o aduce
   `F2.X2 (c)`. CAS și CNAM **nu** au nevoie de cumulative: nu au plafon anual (cercetare §4 —
   plafonul a dispărut odată cu contribuția individuală, 2021). Fereastra: **anul fiscal, nu
   exercițiul companiei** — de aceea `from_date` e coloană, nu presupunere. Recomandare concretă:
   `code` = coloanele per angajat ale IALS21, semnul = cum le raportează formularul; decizia se ia
   **după** ce `F2.X2 (c)` aduce formularul, ca vocabularul să fie al actului.
3. **`DN-10` — vocabularul capabilităților.** *Ce e:* `capability_key` e text liber; singurele nume
   declarate sunt cele trei de conformitate. *Ce blochează:* `F2.P3` — `payroll` ca prima capabilitate
   cu inițializare — și, prin ea, `F2.B6`. *Recomandarea sesiunii:* **varianta B** din Spec A §11.10
   — listă curatoriată, scurtă, definită de *ce cere inițializare*: `payroll` (cumulativele),
   `inventory` (F4: solduri cantitate + cost, metodă, cutover), `multi_company`; ierarhia (C) se
   amână până când grila comercială o cere efectiv — azi n-o cere niciun cod. **Tensiunea de numit în
   ADR:** Spec A §1.8 pune „payroll în măsura obligațiilor declarative" la conformitate (`R24`), iar
   master planul §13 îl vinde pe planuri („de bază" / „complet"). Linia recomandată: *capabilitatea*
   `payroll` se activează (are inițializare), dar **odată activată, ieșirile ei declarative nu se pot
   dezactiva sau plăti separat** — obligația declarativă apare când există angajați, nu când există
   plan.
4. **`DNB-05` — granularitatea postării de salarii.** *Ce e:* o linie per angajat și tip de sumă
   (A), agregat pe tip cu detaliul în `payroll` (B), sau agregat plus read model (C) — Spec B §4.2.
   *Ce blochează:* `F2.B0`, `F2.B4`, volumul lui `journal_line`. *Recomandarea sesiunii:* **(C), în
   forma pe care ADR-048 și ADR-053 o dau deja:** liniile agregate pe rol (cheltuială salarială,
   datorii salariale, CAS, CNAM, impozit reținut) per rulare, iar **formulele** (`journal_formula`,
   ADR-048 — rândul pe care îl citește contabilul) per angajat, cu `employee_id` într-un slot de
   dimensiune. Drill-down-ul `R13` rămâne în contabilitate: rulare → formulă → angajat, fără să
   treacă prin alt modul — exact cum fișa contului agregă pe document și coboară la formule
   (ADR-053 §3.1). Volum, din `11-volume-model.md`: media IMM e 6 salariați — o rulare = ~10 linii și
   ~36 de formule; la 200 de angajați, tot ~10 linii și ~1 200 de formule. Liniile nu cresc cu
   angajații; formulele da, și sunt tabela făcută pentru asta.
5. **`DNB-11` — cheile naturale de deduplicare: refuz sau „suspectat duplicat".** *Ce e:* Spec B
   §10.2 propune cinci chei și întreabă ce face sistemul la coliziune. *Ce blochează:* `F2.A4`
   (linia de extras), `F2.A7` (importul e-Factura), `F2.B4` (rularea), `F2.A2` (deja răspuns pentru
   un tip: `purchase_document` **refuză** prin `UNIQUE`). *Recomandarea sesiunii:* **după cine
   garantează cheia.** Chei pe care le garantăm noi — factura emisă (numerotarea, ADR-022), rularea
   de salarii `(company, period, run_type)` — **refuz**, fiindcă o coliziune e un defect al nostru.
   Chei care vin din afară — documentul furnizorului, `bank_reference`, `sfs_document_uid` —
   **„suspectat duplicat", cu decizie umană**, fiindcă un furnizor care reia seria la an nou sau o
   bancă cu referință goală produc coliziuni legitime. Consecință: o stare pe document (`suspected_duplicate`)
   și un flux de rezolvare — iar `purchase_document`, care azi refuză, ar trece la semnalare.
6. **VEN12 în F2?** *Ce e:* o companie de servicii datorează impozit pe venit (12%, art. 15 lit. b),
   deci declarația anuală e „raport statutar" (master plan: „pachet complet"). Dar calculul ei cere
   ajustările fiscale ale rezultatului contabil — inclusiv amortizarea fiscală (HG 704/2019,
   `F2.X2 (i)`, în lucru) — un calcul de sine stătător, cât un modul. *Ce blochează:* scopul lui
   `F2.C2` și `F2.X2 (i)`. *Recomandarea sesiunii:* **în F2, dar ultimul** — e anual (25 martie), un
   trimestru de pilot nu-l cere decât dacă traversează sfârșitul anului; se construiește după ce
   ieșirile lunare merg, cu HG 704/2019 citită. Dacă proprietarul îl scoate din F2, criteriul de
   ieșire (punctul 2, „rapoartele lunare și trimestriale") nu-l numește oricum.
7. **Documentul de retur / nota de credit** (`F2.A0`, întrebarea 1). *Ce e:* ce document se emite,
   în practica RM, la returul unei prestări; `ReversalDocument` există. *Ce blochează:* forma
   postării pentru vânzări. *Fapt datat, fără recomandare:* `v1-factura-fiscala-omf-118-2017.md`
   **tace** pe retur și corecție — verificat 2026-08-30 (niciun „retur", „corect", „anul" în fișier).
   Instrucțiunea OMF 118/2017 (anexa nr. 2) ar putea trata corectarea facturii; e o **recitire
   țintită**, adăugată la `F2.X2` ca punctul (j). Dacă proprietarul știe răspunsul din practică, e o
   propoziție.
8. **Criteriul de ieșire** — raportul pe fiecare punct e mai sus (§„Întrebarea reformulată"); ce
   rămâne a lui e dacă rescrie criteriul, cum a făcut cu F1, și ce se întâmplă cu F3 în trimestrul de
   pilot.

**Nu blochează nimic azi, dar se ating în F2 și merită știute:** `OD-73` (reformarea bilanțului — la
prima închidere reală de exercițiu), `OD-72` (încrederea pe versiunile de logică — la a doua versiune
a aceleiași chei, probabil la TVA sau salarii), ADR-007 `Propus` (perioada stornoului — la prima
declarație rectificativă).

---

## Tabelul de blocaje — se verifică, nu se citește

| Sarcină | Decizie | Natura |
|---|---|---|
| toate `F2.A*`, `F2.B*`, `F2.C*`, `F2.P*`, `F2.G` | criteriul de ieșire din F1 (F1.10) | `CLAUDE.md` §4; F1.10 vine după C5 → C2 → C1 (evidenta-77) |
| F2.A0, F2.B0 | decizia proprietarului unde SNC lasă opțiuni | ca la ADR-036 §11; actele sunt în repo |
| F2.A1, F2.A2, F2.B2 (bifa `active`) | `OD-22` — numerele MO | extern (acte normative); construcția merge pe `provisional` |
| F2.A4 (cititorii) | `OD-27` | extern (bănci); modelul intern nu așteaptă. `DNB-11` **nu mai blochează** ([ADR-063](../decisions/063-coliziunea-se-decide-dupa-cine-garanteaza.md)): refuzul e implicitul reversibil |
| F2.A5 | `F2.X2 (a)` — art. 11 alin. (7) din Legea 287/2017 necitit; HG 764/1992 neobținută, statut incert; nicio formă în vigoare a registrului de casă | lectură; `legis.md` nici prin Wayback |
| F2.A6 (structura declarației TVA), F2.C2 (textele ordinelor) | `F2.X2 (c)` — identitățile MO obținute, textele adoptate nu; boxele declarației nesigure | lectură; formularele adoptate |
| F2.B3 (modificările post-2019), F2.C1 (categoriile din L. 287/2017) | `F2.X2 (b), (e)` — consolidări doar până în 2019; L. 287/2017 necitită din publicația proprie | lectură |
| F2.A6 (rectificativa) | ADR-007 `Propus` | a proprietarului (contabil) |
| F2.A7 (transportul) | `OD-24` | extern (SFS) |
| F2.A8 | `C2` din F1.4.4; amortizarea fiscală — HG 704/2019 **obținută** (`F2.X2 (i)`), Catalogul HG 941/2020 nu | în lucru la evidenta-77, după C5; lectură |
| F2.A9 | `OD-76` (stratul `integrations`), `OD-26` (sursa BNM); ~~reevaluarea — Anexa 1 SNC~~ obținută integral 2026-08-30 (`F2.X2 (f)`) | ADR; extern |
| ~~F2.B0~~ | ~~`DNB-05`, `DN-10`~~ | **LIVRATĂ 2026-08-30** — [ADR-065](../decisions/065-schema-salarizarii.md) `Acceptat` |
| ~~F2.B6~~ | ~~`OD-04`~~ | **deblocată 2026-08-30** — [ADR-061](../decisions/061-cumulativele-de-salarii.md) |
| F2.C1 (capitalul propriu) | `OD-73` — **premisa corectată 2026-08-30:** SNC „Prezentarea" pct. 18 și 228 numesc momentul (după aprobare și prezentare); tac asupra datei contabile | a proprietarului; declanșatorul e prima închidere reală de exercițiu |
| F2.C2 (depunerea) | `OD-75` — canalul SFS | extern (SFS); **nou** |
| F2.C3 | `OD-25` | extern (CNAS, CNAM, BNS) |
| ~~F2.C4, F2.P2~~ | ~~`OD-71`~~ | **deblocate 2026-08-30** — [ADR-062](../decisions/062-aprobatorul-din-productie.md); termenul devine *înainte de prima activare în producție* |
| F2.C5 | F1.10 — **convenția e fixată** (evidenta-04, 2026-08-30): `tests/corpus/`, `case(*sets, cites=...)` ca unică ușă, `corpus/<logic_key>/<versiune>`, gardian peste fiecare `regression_case_set` din `fiscal/parameters/data/*.toml`, `-m fiscal_regression` | al F1; F2 moștenește |
| F2.P1 | `OD-74` (biblioteca, pipeline-ul — se închide în sarcină, cu ADR); `OD-52` (arhivarea) | ADR; providerul de stocare nu blochează generarea |
| ~~F2.P3~~ | ~~`DN-10`~~ | **deblocată 2026-08-30** — [ADR-060](../decisions/060-vocabularul-capabilitatilor.md) |
| F2.X1 (activarea) | `OD-22` | extern; încărcarea ca `draft` nu așteaptă |

**Externe reale: patru instituții** — SFS (`OD-24`, `OD-75`), CNAS/CNAM/BNS (`OD-25`), băncile
(`OD-27`), BNM (`OD-26`) — plus accesul la textul legii (`OD-22`, `F2.X2`). Niciuna nu blochează
construcția; toate blochează câte o bifă.

**Ale proprietarului: erau șase, au rămas două.** `OD-04`, `OD-71`, `DN-10`, `DNB-05` și `DNB-11`
s-au închis la 2026-08-30, într-o singură instrucțiune. Rămân **ADR-007** (`Propus` — perioada
stornoului, declanșator: prima declarație rectificativă) și **clasificările din `F2.A0`/`F2.B0`**,
care se iau în ADR-urile lor, cu Planul general de conturi citat. Plus `OD-79`, deschisă atunci și
amânată cu declanșator.
