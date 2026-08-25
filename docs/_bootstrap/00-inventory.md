# 00 — Inventar și raport de goluri

**Etapa:** 0 din BOOTSTRAP.md
**Data:** 2026-08-24
**Surse citite integral:**

| Referință în BOOTSTRAP.md | Fișier real pe disc |
|---|---|
| `master-plan-v2.md` | `docs/_input/evidenta-master-plan-v2.md` (539 linii) |
| `amendment-1.md` | `docs/_input/evidenta-master-plan-v2-amendament-1.md` (277 linii) |
| `implementation-spec.md` | `docs/_input/evidenta-implementation-spec.md` (919 linii) |

**Regula de precedență aplicată în tot documentul:** `amendament-1` > `master-plan-v2`.
`implementation-spec` derivă din ambele și este tratat ca operaționalizare; unde contrazice amendamentul, prevalează amendamentul, iar divergența este raportată în secțiunea 4.

**Legenda de verificabilitate** folosită în secțiunea 1:

- **[A]** — verificabil automat (test, lint, gardian de schemă, analiză statică). Poate deveni o suită.
- **[M]** — parțial automat: o parte se prinde de mașină, o parte cere ochi uman.
- **[U]** — necesită review uman sau decizie de proces. Nu există verificare mecanică.

---

## 1. Inventarul invarianților

### 1.1 Invarianții canonici (11)

Sursa: **Amendament §A**, care înlocuiește integral secțiunea 2 din V2. Numerotarea este cea din amendament.

| # | Invariant | Sursă | Verif. | Cum s-ar verifica |
|---|---|---|---|---|
| **INV-1** | Niciun modul business nu scrie în ledger. Toate trec prin Posting Engine, prin evenimente contabile. | Amd §A.1 = V2 §2.1 | [M] | Analiză statică de import (`accounting.ledger` nu e importat în afara `accounting`); testul complet cere review de flux |
| **INV-2** | Ledgerul postat este imutabil. Corecția se face prin storno și reînregistrare, niciodată prin UPDATE. | Amd §A.2 = V2 §2.2 | [A] | Revocarea privilegiului UPDATE pe rolul de aplicație + trigger DB + test de integrare |
| **INV-3** | Nicio interogare nu rulează fără context de tenant. Absența contextului înseamnă refuz, nu acces total. | Amd §A.3 = V2 §2.3 | [A] | Suita 1 (penetrare) + test „task Celery fără context eșuează" |
| **INV-4** | Conformitatea are două straturi, ambele versionate după dată efectivă: **parametri fiscali → date** (INSERT, nu deployment); **logică fiscală → cod versionat** (deployment). Selecția implementării se face printr-un registru, după data efectivă a perioadei calculate. | Amd §A.4 *(reformulează V2 §2.4)* | [M] | Grep pentru cote/praguri literale și pentru `if year >= X`; corpusul de regresie; restul cere `fiscal-reviewer` |
| **INV-5** | Un singur codebase. Diferențierea prin feature flags și release rings, niciodată prin versiuni per tenant. | Amd §A.5 = V2 §2.5 | [U] | Disciplină de proces |
| **INV-6** | Modificările de conformitate nu sunt opționale pentru niciun tenant și nu sunt niciodată paywall. | Amd §A.6 = V2 §2.6 | [M] | Test: modulele de conformitate nu consultă `CapabilityActivation` pentru gating; restul e review de produs |
| **INV-7** | Tenantul este proprietarul datelor. Firma de contabilitate are acces delegat și revocabil. | Amd §A.7 = V2 §2.7 | [M] | Test de revocare instantanee a accesului; proprietatea e proprietate de model, verificată la review de schemă |
| **INV-8** | Idempotență: orice comandă sau eveniment extern cu efect financiar este idempotent, cu cheia pe **evenimentul contabil**, nu doar pe endpoint. Deduplicarea (același document pe două căi) e mecanism separat, prin chei naturale de business. | Amd §A.8 *(nou)* | [A] | Test „aceeași operațiune de două ori → exact un efect financiar" + constrângeri unice |
| **INV-9** | Trasabilitatea documentului sursă: `Journal Line → Journal Entry → Accounting Event → Source Document → Sursă`, navigabilă în ambele sensuri. Storno are **două** legături: spre documentul sursă și spre înregistrarea anulată. | Amd §A.9 *(nou)* | [A] | Test de integrare care parcurge lanțul în ambele direcții pentru fiecare tip de efect financiar |
| **INV-10** | Interogarea cross-tenant este permisă exclusiv în stratul de read models. Nicio logică de business nu presupune că doi tenanți sunt fizic în aceeași bază de date. | Amd §A.10 *(nou)* | [M] | Lint pe interogări în afara `platform/readmodels`; cazurile subtile cer `tenancy-guard` |
| **INV-11** | Fiecare tabelă business are context de tenant și politică RLS. Verificat automat, nu prin convenție. | Amd §A.11 *(nou)* | [A] | Suita 2 (gardian de model) |

### 1.2 Reguli operaționale (26) — conținutul destinat `CLAUDE.md`

Sursa: **implementation-spec §1**. Sunt forma executabilă a invarianților canonici. Coloana „INV" indică invariantul canonic din care derivă.

#### 1.2.1 Izolarea datelor (spec §1.1)

| # | Regulă | INV | Verif. |
|---|---|---|---|
| R1 | Fiecare tabelă business are `tenant_id`. Excepții enumerate limitativ: registru global de contrapărți, parametri fiscali, curs BNM, tabele de sistem Django. | INV-11 | [A] |
| R2 | Fiecare tabelă business are politică RLS activă și `FORCE ROW LEVEL SECURITY`. | INV-11 | [A] |
| R3 | Contextul de tenant se setează cu `SET LOCAL` într-o tranzacție. Orice request rulează într-o tranzacție. | INV-3 | [A] |
| R4 | Absența contextului înseamnă zero rânduri sau eroare. Niciodată acces total. | INV-3 | [A] |
| R5 | Rolul de aplicație este diferit de rolul de migrare. Aplicația nu deține tabelele. | INV-3 | [A] |
| R6 | Fiecare task Celery primește `tenant_id` explicit ca argument și setează contextul înainte de orice query. | INV-3 | [A] |
| R7 | Interogările cross-tenant sunt permise exclusiv în read models și în căile privilegiate enumerate în Spec A. | INV-10 | [M] |
| R8 | Nicio parte din logica de business nu presupune că doi tenanți sunt fizic în aceeași bază de date. | INV-10 | [M] |

#### 1.2.2 Contabilitate (spec §1.2)

| # | Regulă | INV | Verif. |
|---|---|---|---|
| R9 | Niciun modul business nu scrie direct în ledger. Toate emit evenimente contabile către Posting Engine. | INV-1 | [M] |
| R10 | Ledgerul postat este imutabil. Niciun `UPDATE` pe `journal_entries` sau `journal_lines` postate. | INV-2 | [A] |
| R11 | Σ Debit = Σ Credit pe fiecare înregistrare, verificat la nivel de bază de date. | — (V2 §7.3) | [A] |
| R12 | Postarea într-o perioadă închisă este refuzată la nivel de motor, nu de interfață. | — (V2 §7.5) | [A] |
| R13 | Pentru orice efect financiar există lanțul complet, navigabil în ambele sensuri. | INV-9 | [A] |
| R14 | O înregistrare de storno are două legături: spre documentul sursă și spre înregistrarea anulată. | INV-9 | [A] |

#### 1.2.3 Conformitate (spec §1.3)

| # | Regulă | INV | Verif. |
|---|---|---|---|
| R15 | Parametrii fiscali sunt date (cote, praguri, plafoane, scutiri, coeficienți, termene, mapări de conturi), versionate cu `valid_from` / `valid_to`. | INV-4 | [M] |
| R16 | Logica fiscală este cod versionat (algoritmi, scheme de declarații, validări, comportament API). | INV-4 | [U] |
| R17 | Selecția implementării se face printr-un registru, după data efectivă a perioadei calculate. Nicio condiție `if year >= 2027` în codul de business. | INV-4 | [A] |
| R18 | Recalcularea unei perioade trecute folosește parametrii și algoritmul valabili atunci. | INV-4 | [A] |

#### 1.2.4 Integritate operațională (spec §1.4)

| # | Regulă | INV | Verif. |
|---|---|---|---|
| R19 | Orice comandă sau eveniment extern cu efect financiar este idempotent, cu cheie pe evenimentul contabil. | INV-8 | [A] |
| R20 | Deduplicarea documentelor economice se face prin chei naturale de business, separat de idempotență. | INV-8 | [A] |
| R21 | Tabelele append-only de volum mare nu primesc chei străine. Lista: `journal_lines`, `inventory_movements`, `audit_events`, `document_events`, arhive payload e-Factura, arhive extrase bancare. Legăturile se fac invers. | Amd §B.3 | [A] |
| R22 | Aceste tabele au coloana naturală de partiționare (`accounting_date` sau `occurred_at`) ca `NOT NULL` de la început. | Amd §B.3 | [A] |

#### 1.2.5 Produs (spec §1.5)

| # | Regulă | INV | Verif. |
|---|---|---|---|
| R23 | Un singur codebase. Diferențierea prin feature flags, niciodată prin ramuri sau versiuni per tenant. | INV-5 | [U] |
| R24 | Conformitatea nu este niciodată capability plătibilă sau dezactivabilă. | INV-6 | [M] |
| R25 | Activarea unei capabilități este o entitate cu dată efectivă și stare de inițializare, nu un boolean. | — (V2 §8) | [A] |
| R26 | Profilul de capabilități al tenantului este input al Posting Engine — aceeași operațiune se contabilizează diferit după capabilitățile active. | — (V2 §7.4) | [M] |

### 1.3 Reguli de dependență între module (spec §4.3)

Graful este **aciclic**. Direcția permisă:

```
platform    ←  totul poate depinde de platform
fiscal      ←  nu depinde de niciun modul business
masterdata  ←  depinde doar de platform
accounting  ←  depinde de platform, masterdata, fiscal
operations  ←  depinde de toate cele de mai sus
```

| # | Interdicție | Verif. |
|---|---|---|
| D1 | `fiscal` nu importă din niciun modul business | [A] |
| D2 | `accounting` nu importă din `sales`, `purchases`, `payroll`, `inventory` | [A] |
| D3 | Modulele operaționale nu importă `accounting.ledger` — doar `accounting.events` | [A] |
| D4 | `payroll` nu importă din `tax` | [A] |
| D5 | Nimic nu importă din `firmspace` | [A] |
| D6 | Comunicarea între module se face prin evenimente contabile, servicii publice ale modulului sau read models. Niciodată prin import direct de modele. | [M] |

Toate cele șase sunt exprimabile ca reguli de contract de import (ex. `import-linter`). Unealta nu este aleasă în documente — vezi **G-44**.

### 1.4 Convenții obligatorii (spec §2)

Nu sunt invarianți arhitecturali, dar sunt reguli cu aceeași forță în `CLAUDE.md`.

| # | Convenție | Sursă | Verif. |
|---|---|---|---|
| C1 | Un app Django per modul. Fără app-uri „utils"/„common" care acumulează logică. | §2.2 | [M] |
| C2 | Modelele nu conțin logică de business. Serviciile o conțin. | §2.2 | [U] |
| C3 | Managerul implicit al modelelor business nu filtrează pe tenant. Filtrarea o face RLS. | §2.2 | [A] |
| C4 | Fără signals Django pentru logică financiară. | §2.2 | [A] |
| C5 | Migrațiile sunt aditive. Nicio migrare nu șterge o coloană cu date financiare fără plan de arhivare aprobat. | §2.2 | [A] |
| C6 | UUID ca cheie primară pentru entitățile expuse extern; `bigint` pentru tabelele append-only de volum mare. | §2.2 | [A] |
| C7 | Versionare API în cale: `/api/v1/...`; resursele urmează modulul. | §2.3 | [A] |
| C8 | Contextul de tenant vine din subdomeniu, nu din payload sau parametri. | §2.3 | [A] |
| C9 | Fiecare endpoint cu efect financiar acceptă `Idempotency-Key`. | §2.3 | [A] |
| C10 | Erorile au cod stabil, nu doar mesaj. | §2.3 | [M] |
| C11 | Fiecare modul are teste unitare pentru servicii. | §2.4 | [M] |
| C12 | Fiecare efect financiar are test de integrare care verifică lanțul complet până la journal line. | §2.4 | [M] |
| C13 | Suitele de izolare rulează la fiecare commit. | §2.4 | [A] |
| C14 | Corpusul de regresie fiscală rulează la fiecare modificare de parametru sau algoritm. | §2.4 | [A] |
| C15 | Cod, comentarii, nume, mesaje de commit: **engleză**. Interfață, documentație de utilizator, denumiri contabile: **română**. Termenii legali își păstrează forma oficială (`IDNO`, `TVA`, `IPC`, `CNAS`, `CNAM`, `SNC`, `e-Factura`). | §2.5 | [M] |

### 1.5 Reguli suplimentare de testare a izolării (Amd §D.3)

| # | Regulă | Verif. |
|---|---|---|
| T1 | Ambele suite rulează **sub rolul de aplicație**, niciodată sub superuser sau owner de tabelă. | [A] |
| T2 | Suita 1 (penetrare) acoperă obligatoriu: engagement expirat, engagement revocat, engagement cu scope restrâns, task Celery fără context. | [A] |
| T3 | Suita 2 (gardian de model) enumeră toate tabelele și eșuează la lipsă de context de tenant, de politică RLS activă sau de `FORCE ROW LEVEL SECURITY`. Excepțiile sunt o listă versionată. | [A] |

### 1.6 Sinteză

- **26 de reguli operaționale + 6 de dependență + 15 convenții + 3 de testare = 50 de reguli** derivate din 11 invarianți canonici.
- **Verificabile automat [A]: 33.** Acestea sunt materialul din care se construiesc suita 2 (gardian de model), regulile de import și testele de integrare.
- **Mixte [M]: 13.** Acoperite parțial de agenții de review din `.claude/agents/`.
- **Umane [U]: 4** (INV-5/R23, R16, C2, INV-6 parțial). Nu au verificare mecanică; rămân responsabilitate de proces.

---

## 2. Inventarul modulelor

Sursa: **implementation-spec §4.1**. Coloana **Fază** = momentul implementării. Coloana **Model** = momentul în care structura de date trebuie să existe, chiar dacă funcționalitatea nu.

**Regula §4.2, obligatorie:** „Model F0" **nu** înseamnă „creează app-ul acum". Înseamnă că modulul din faza curentă nu trebuie proiectat astfel încât să facă imposibil modulul viitor. App-urile Django goale nu se creează.

### 2.1 platform/

| Modul | Conținut | Fază | Model | Cod în F0? |
|---|---|---|---|---|
| `platform/tenancy` | Tenant, Company | F0 | F0 | **da** (F0.3) |
| `platform/identity` | User, Membership | F0 | F0 | **da** (F0.3) |
| `platform/engagement` | Firm, Engagement | F0 | F0 | **da** (F0.3) |
| `platform/rls` | context, politici | F0 | F0 | **da** (F0.1) |
| `platform/capabilities` | activare cu dată | F0 | F0 | **da** (F0.5) |
| `platform/flags` | feature flags | F0 | F0 | **da** (F0.5) |
| `platform/audit` | audit events | F0 | F0 | **da** (F0.4) |
| `platform/documents` | document core | F0 | F0 | **da** (F0.6) |
| `platform/numbering` | serii, numerotare | F0 | F0 | **da** (F0.6) |
| `platform/attachments` | S3, metadate | F0 | F0 | **da** (F0.6) |
| `platform/notifications` | in-app, email | F0 | F0 | **da** (V2 §10; nu apare explicit în F0.1–F0.10 — vezi **X-9**) |
| `platform/readmodels` | agregate cross-tenant | F3 | F0 | nu |

### 2.2 masterdata/

| Modul | Conținut | Fază | Model | Cod în F0? |
|---|---|---|---|---|
| `masterdata/counterparties` | registru global | F0 | F0 | **da** (F0.7) |
| `masterdata/partners` | Partner (tenant) + CompanyPartner (companie) | F0 | F0 | **da** (F0.7) |
| `masterdata/items` | nomenclator | F0 | F0 | **da** (F0.7) |
| `masterdata/uom` | unități, conversii | F0 | F0 | **da** (F0.7) |
| `masterdata/warehouses` | depozit, zonă, bin | F4 | F0 | **ambiguu** — F0.7 cere modelul `Warehouse` în F0, harta zice Fază F4. Vezi **X-5** |
| `masterdata/dimensions` | centre cost, proiecte | F1 | F0 | **ambiguu** — F0.7 cere dimensiunile modelate în F0, harta zice Fază F1. Vezi **X-5** |

### 2.3 fiscal/

| Modul | Conținut | Fază | Model | Cod în F0? |
|---|---|---|---|---|
| `fiscal/parameters` | cote, praguri (DATE) | F0 | F0 | **da** (F0.8) |
| `fiscal/logic` | algoritmi (COD) | F1 | F0 | nu |
| `fiscal/registry` | selecție după dată | F0 | F0 | **da** (F0.8) |
| `fiscal/admin` | Compliance Admin | F2 | F1 | nu |

### 2.4 accounting/

| Modul | Conținut | Fază | Model | Cod în F0? |
|---|---|---|---|---|
| `accounting/coa` | plan conturi SNC | F1 | F1 | nu |
| `accounting/ledger` | journal entry / line | F1 | F1 | nu |
| `accounting/posting` | Posting Engine | F1 | F1 | nu |
| `accounting/events` | Accounting Event | F1 | F1 | nu |
| `accounting/periods` | perioade, închidere | F1 | F1 | nu |
| `accounting/currency` | multi-valută, BNM | F1 | F0 | **conflict** — F0.9 o cere în F0. Vezi **X-4** |
| `accounting/openingbalances` | solduri inițiale | F1 | F1 | nu |
| `accounting/reports` | balanță, Cartea Mare | F1 | F1 | nu |

### 2.5 tax/ și modulele operaționale F2

| Modul | Conținut | Fază | Model |
|---|---|---|---|
| `tax/codes` | coduri fiscale | F2 | F1 |
| `tax/vat` | registre TVA | F2 | F1 |
| `tax/declarations` | declarații fiscale | F2 | F2 |
| `sales` | facturi, note credit | F2 | F0 |
| `purchases` | facturi furnizor | F2 | F0 |
| `receivables` | AR, decontare | F2 | F1 |
| `payables` | AP, decontare | F2 | F1 |
| `banking` | conturi, extrase | F2 | F1 |
| `cash` | casierie | F2 | F1 |
| `assets` | active fixe | F2 | F1 |
| `efactura` | e-Factura / SFS | F2 | F1 |

### 2.6 payroll/

| Modul | Conținut | Fază | Model |
|---|---|---|---|
| `payroll/employees` | angajați | F2 | F0 |
| `payroll/contracts` | contracte muncă | F2 | F0 |
| `payroll/calculation` | calcul salarial | F2 | F1 |
| `payroll/contributions` | CNAS, CNAM, IPC | F2 | F1 |
| `payroll/leave` | concedii, medicale | F2 | F1 |
| `payroll/runs` | rulări, fluturași | F2 | F2 |
| `payroll/parallelrun` | rulare în paralel | F2 | F2 |

### 2.7 statutory/

| Modul | Conținut | Fază | Model |
|---|---|---|---|
| `statutory/sfs` | rapoarte SFS | F2 | F1 |
| `statutory/cnas` | rapoarte CNAS | F2 | F1 |
| `statutory/cnam` | rapoarte CNAM | F2 | F1 |
| `statutory/bns` | rapoarte BNS | F2 | F1 |
| `statutory/financials` | situații SNC | F2 | F1 |

### 2.8 firmspace/, migration/, billing/

| Modul | Conținut | Fază | Model |
|---|---|---|---|
| `firmspace/workspace` | dashboard contabil | F3 | F0 |
| `firmspace/calendar` | termene per client | F3 | F3 |
| `firmspace/bulkops` | operațiuni în masă | F3 | F3 |
| `migration/onec` | import 1C | F1 | F1 |
| `migration/mapping` | mapare conturi/date | F2 | F1 |
| `migration/reconciliation` | verificare la zero | F3 | F1 |
| `billing/subscriptions` | abonamente | F3 | F0 |
| `billing/wholesale` | canal partener | F3 | F0 |
| `billing/direct` | canal direct | F3 | F0 |

### 2.9 inventory/ și comerț (F4)

| Modul | Conținut | Fază | Model |
|---|---|---|---|
| `inventory/ledger` | inventory ledger | F4 | F0 |
| `inventory/movements` | mișcări | F4 | F0 |
| `inventory/valuation` | FIFO / CMP | F4 | F0 |
| `inventory/lots` | loturi | F4 | F0 |
| `inventory/serials` | numere de serie | F4 | F0 |
| `inventory/counting` | inventariere | F4 | F4 |
| `customs` | import, landed cost | F4 | F4 |
| `orders` | comenzi vânzare/cumpărare | F4 | F0 |
| `pricing` | liste prețuri | F4 | F4 |

### 2.10 ERP (F5) și integrări

| Modul | Conținut | Fază | Model |
|---|---|---|---|
| `hr` | HR separat de payroll | F5 | F2 |
| `crm` | CRM peste Partner | F5 | F2 |
| `contracts` | registru contracte | F5 | F0 |
| `workflow` | aprobări | F5 | F0 |
| `integrations/sfs` | API SFS | F2 | F1 |
| `integrations/cnas` | API CNAS | F2 | F2 |
| `integrations/cnam` | API CNAM | F2 | F2 |
| `integrations/bns` | raportare BNS | F2 | F2 |
| `integrations/bnm` | curs valutar | F1 | F0 |
| `integrations/banks` | import extrase | F2 | F2 |
| `integrations/onec` | conector 1C | F1 | F1 |

### 2.11 Sinteză

- **65 de module** în hartă.
- **21 au Fază F0** (12 în `platform/`, 5 în `masterdata/` din care 1 ambiguu, 2 în `fiscal/`, plus ambiguitățile din 2.2/2.4).
- **Directoare care vor conține fișiere în F0** (relevant pentru Etapa 1, unde directoarele goale nu se creează):
  `platform/{rls,tenancy,identity,engagement,audit,capabilities,flags,documents,numbering,attachments,notifications}`,
  `masterdata/{counterparties,partners,items,uom}`,
  `fiscal/{parameters,registry}`,
  plus `config/`, `tests/{isolation,schema_guard,integration}`, `infra/`, `frontend/`.
  Statutul lui `masterdata/warehouses`, `masterdata/dimensions`, `accounting/currency` și `integrations/bnm` în F0 depinde de rezolvarea conflictelor **X-4** și **X-5**.
- **Module fără sarcină F0.x asociată, dar marcate F0 în hartă:** `platform/notifications` (vezi **X-9**).

---

## 3. Registrul deciziilor

### 3.1 Decizii închise

Numerotarea `V2-n` se referă la lista din **V2 §15** („Decizii deschise care blochează schema DB"). Deciziile fără prefix sunt închise în alte secțiuni.

| # | Decizie | Ce s-a decis | Sursă | Efect asupra schemei |
|---|---|---|---|---|
| **ÎNC-1** *(V2-1)* | Modelul Tenant / Firm / Engagement | Confirmat. Tenant = proprietar, Company = entitate juridică cu ledger, Firm = actor cu tenant propriu, Engagement = relație delegată revocabilă. Holdingul și firma de contabilitate **nu** se modelează identic. | V2 §4.1; Amd §E („deciziile 1…închise"); Amd §F („nu se modifică modelul") | Blochează totul; determină fiecare tabelă |
| **ÎNC-2** *(V2-6)* | Identitatea globală a utilizatorului | Confirmată. Un contabil are un singur cont pentru toți clienții. | V2 §4.1; spec §6.1 F0.3; Amd §E | `User` este tabelă globală, fără `tenant_id`; apartenența se exprimă prin `Membership` |
| **ÎNC-3** *(V2-9)* | Modelul de partener | Trei niveluri: `CounterpartyRegistry` (global, după IDNO) → `Partner` (tenant, master) → `CompanyPartner` (companie, configurare). | Amd §C.1 | Trei tabele, nu una; `CounterpartyRegistry` este excepție de la `tenant_id` |
| **ÎNC-4** *(V2-3, parțial)* | Metoda de evaluare a stocurilor | Politică implicită per companie, cu suprascriere **per categorie** de stoc. MVP: FIFO și cost mediu ponderat. Schimbarea metodei cere dată efectivă la granița perioadei, închiderea perioadei anterioare, reevaluare documentată, aprobare, urmă în audit. | Amd §C.4 | `Company Inventory Policy` + `Category Inventory Policy`. **Închidere provizorie** — confirmarea contabilă rămâne deschisă, vezi **DES-6** |
| **ÎNC-5** *(V2-2, retrogradată)* | Cheia de partiționare | **Nu mai este blocantă.** Se înlocuiește cu disciplină: (a) nicio cheie străină nu arată spre tabelele append-only de volum mare; (b) coloana naturală de partiționare există `NOT NULL` de la început; (c) indecșii încep cu contextul de tenant și companie. Decizia efectivă se ia după modelul de volum. Primul candidat real este `audit_events`, nu `journal_lines`. | Amd §B.3 *(înlocuiește V2 §4.4)* | Cheile primare din MVP **nu** se constrâng; R21/R22 devin regulile aplicabile |
| **ÎNC-6** | Restaurarea per tenant | Se separă în trei concepte cu limite explicite: recuperare tehnică (PITR, SLA de infrastructură), corecție de business (storno + reînregistrare + audit), export/snapshot (forensic, litigii, offboarding). **Cererea „restaurează-mi compania la starea de vineri" se refuză, cu explicație.** | Amd §B.2 *(înlocuiește V2 §12.1)* | Audit log + lineage trebuie să permită **enumerarea completă a efectelor** unei sesiuni / utilizator / interval — cerință funcțională, în Spec A |
| **ÎNC-7** | Structura motorului de reguli fiscale | Două componente: `FISCAL PARAMETERS` (date versionate) și `FISCAL LOGIC` (cod versionat, selectat prin registru după dată efectivă). | Amd §B.1 *(restructurează V2 §5)* | Trei module: `fiscal/parameters`, `fiscal/logic`, `fiscal/registry` |
| **ÎNC-8** *(V2-7 — contestată)* | Cumulativele payroll la activare în cursul anului | Amd §E afirmă că decizia V2-7 este închisă, dar **tabelul din aceeași secțiune E o listează ca deschisă**. Vezi **X-1**. Tratată ca **deschisă** — vezi **DES-4**. | Amd §E | — |
| **ÎNC-9** | Organizarea F2 | Două fluxuri paralele după stabilizarea Accounting Core: Commercial/Tax și Payroll. Ambele consumă parametri fiscali și emit evenimente contabile; niciunul nu scrie în ledger. | Amd §C.2 | Nicio dependență `payroll → tax` (D4) |
| **ÎNC-10** | Rularea payroll în paralel | Este **funcție de produs**, nu testare internă: calcul în paralel cu sistemul existent + raport de diferențe la ban, per angajat și per contribuție. Intră în scopul F2, nu F3. | Amd §C.3 | Modulul `payroll/parallelrun`, F2 |
| **ÎNC-11** | DB dedicat per tenant | **Eliminat din roadmap.** Două topologii dublează suprafața de testare și rup dashboard-ul transversal. Dacă apare cerere de izolare fizică, este discuție comercială separată. | V2 §12.3 | Nu se construiește router de bază de date |
| **ÎNC-12** | Modelul de activare a capabilităților | Activarea este **entitate**, nu boolean: `effective_from` aliniat la granița perioadei contabile, stare de inițializare, pas de inițializare. Capability set ≠ plan comercial (axe ortogonale). | V2 §8; spec §1.5 R25 | `CapabilityActivation` în `platform/capabilities` |
| **ÎNC-13** | Conformitatea ca element comercial | Conformitatea (TVA, e-Factura, raportare SNC) nu poate fi capability plătibilă sau dezactivabilă, în niciun plan. Diferențierea se face pe volum, module operaționale și complexitate. | V2 §13; INV-6 | Modulele de conformitate nu consultă gating de plan |
| **ÎNC-14** | Interogarea cross-tenant | Permisă exclusiv în stratul de read models, care este conceptual un store separat. | Amd §A.10 | `platform/readmodels` cu `tenant_id` + `firm_id` denormalizat |
| **ÎNC-15** | Suitele de izolare în CI | Două suite distincte, ambele la fiecare release, ambele **sub rolul de aplicație**: penetrare și gardian de model. | Amd §D.3 | `tests/isolation/`, `tests/schema_guard/`; ordinea F0.1 → F0.2 înaintea oricărui model |
| **ÎNC-16** | Compliance Admin | Instrument **intern** al echipei, nu funcție pentru clienți. Necesar operațional din F2, modelat din F1. | Amd §D.1 | `fiscal/admin` |
| **ÎNC-17** | Corpus de regresie pentru conformitate | Cazuri reale anonimizate cu rezultat corect verificat de un contabil, rulate la **fiecare** modificare de parametru sau algoritm. Necesar din F1. | Amd §D.2 | `tests/fiscal_regression/` |
| **ÎNC-18** | Poziționarea comercială | „De la prima factură până la ERP." Promisiunea se limitează la traseul acoperibil în 24 de luni. Producția, MRP, WMS = direcție, nu argument de vânzare. | V2 §1 | Nu se creează module pentru ele |
| **ÎNC-19** | Stack tehnologic | React + TypeScript + Vite / Django + DRF / PostgreSQL 16+ cu RLS / Redis / Celery / S3-compatible / containere, medii dev-staging-prod. | spec §2.1 | Versiunile exacte lipsesc — **G-41** |

### 3.2 Decizii deschise

Sursa principală: **Amendament §E**. Numerotarea `DES-n` urmează ordinea din tabelul amendamentului.

| # | Decizie | Ce blochează | Termen | Opțiuni identificate în documente |
|---|---|---|---|---|
| **DES-1** | Cheia de partiționare | Nimic (disciplina din ÎNC-5 este suficientă) | După modelul de volum, **F0** | Candidați menționați: `accounting_date` (an) pentru tabele contabile, `tenant_id` pentru audit și evenimente. Amendamentul indică `audit_events` ca primul candidat real |
| **DES-2** | Numerotarea documentelor: **per companie sau per filială** | `platform/documents`, `platform/numbering` (F0.6) | **Spec A** | Cele două variante sunt enunțate, fără analiză. **Notă:** entitatea „filială" nu există în modelul de tenancy — vezi **G-18** |
| **DES-3** | Politica de propagare a modificărilor din template-ul planului de conturi către instanțele existente | `accounting/coa` (F1.1) | **Spec B** | Niciuna descrisă. Cerințele conexe: versiunea template-ului înregistrată pe companie, distincție conturi de sistem vs. subconturi, `valid_from`/`valid_to` pe cont |
| **DES-4** | Modelul cumulativelor payroll la activare în cursul anului | Schema `payroll` | **Înainte de F2** | Cerința cunoscută: cumulative de la 1 ianuarie per angajat, altfel IPC-ul iese greșit. Este „literalmente o migrare de date". Contestată — vezi **X-1** |
| **DES-5** | Relația cu AvaBoss: integrare prin evenimente sau portare ulterioară | Nimic acum | **După F3** | Două opțiuni enunțate: sursă de evenimente către Posting Engine, sau portare deliberată. Explicit: POS-ul nu se rescrie |
| **DES-6** | Confirmare contabilă pe politica de evaluare per categorie | Schema `inventory` | **Înainte de F4** | Confirmare de la contabilul practicant al echipei. Nu blochează Spec A |

### 3.3 Decizii care nu sunt în registru, dar trebuie luate

Nu le închid și nu le presupun. Sunt puncte unde documentele de intrare cer un artefact fără să dea conținutul lui. Detaliate în secțiunea 5; enumerate aici pentru că vor deveni ADR-uri:

| Referință | Subiect | Când e nevoie |
|---|---|---|
| G-02, G-03, G-04 | Nivelul și contextul RLS pentru tabelele `platform` (Tenant, Firm, Engagement, Membership) și existența unei variabile `app.company_id` | Înainte de F0.1 |
| G-05, G-06 | Modelul de roluri și forma concretă a scope-ului de Engagement | Spec A |
| G-10 | Enumerarea limitativă a căilor privilegiate și mecanismul tehnic de ridicare a izolării | Spec A |
| G-12 | Termenele legale de retenție și politica de offboarding | Spec A — **necesită sursă legală, nu deducție** |
| G-22 | Cum se împacă efectul de rețea al e-Facturii (documentul apare la destinatar) cu INV-10 | Spec A |
| G-28 | Valorile fiscale efective (cote, praguri, termene) | F0.8 pentru schemă, F1+ pentru valori — **necesită contabil practicant** |
| G-30 | Conținutul planului de conturi SNC | Spec B |
| G-41 – G-49 | Versiuni, tooling, CI, roluri DB în medii | Etapa 1 (schelet) |
| G-57 | Țintele numerice de performanță | Înainte de F1 (V2 §12.4) |

---

## 4. Raport de conflicte și erori în documentele de intrare

### 4.0 Statutul conflictelor — rezolvate 2026-08-24

Rezolvările au fost date de proprietarul proiectului. Documentele de intrare rămân neatinse
(`docs/_input/` este read-only); rezolvarea trăiește aici și în ADR-uri.

| # | Subiect | Rezolvare |
|---|---|---|
| **X-1** | Decizia V2-7, cumulativele payroll | **Rămâne deschisă.** Textul amendamentului o declară închisă, dar nimic din amendament nu o închide. `OD-04`. Nu blochează F0 |
| **X-2** | Decizia V2-3, evaluarea stocurilor | **Închisă**, în Amendament §C.4. Confirmarea contabilă rămâne separat, `OD-06` |
| **X-3** | Decizia V2-6, identitatea globală | **Închisă** — dar de **V2 §4.1** („User — identitate **globală**", tabelul de entități), nu de amendament. Atribuirea din amendament este greșită; decizia nu este |
| **X-4** | Fazarea multi-valutei | **Rezolvată:** modelată în **F0**; integrarea BNM și funcționalitatea de bază în **F1** (ledgerul are nevoie de ea); reevaluarea și diferențele de curs în **F2**. `OD-10` închisă |
| **X-5** | `warehouses`, `dimensions` | Rămâne deschisă — `OD-11` |
| **X-6** | Lista excepțiilor de la `tenant_id` | **Rezolvată.** Lista corectă: `user`, template SNC, parametri fiscali, curs BNM, registrul global de contrapărți, tabele de sistem Django — plus tabelele de tenancy, cu forma lor de politică. Trăiește **într-un singur fișier versionat**, [`infra/rls/exceptions.toml`](../../infra/rls/exceptions.toml), citit de gardianul de model. Vezi [ADR-003](../decisions/003-rls-tenancy-tables.md) |
| **X-9** | `notifications` fără sarcină | **Rezolvată:** are sarcină, F0.6.5. La fel modelul de volum, F0.11 (eroarea E-4) |
| **X-12** | Două structuri `docs/` | **Rezolvată:** prevalează structura din `BOOTSTRAP.md`, fiind mai completă |
| **X-13** | Limba rusă | Rămâne deschisă — `OD-13` / `DN-01` |
| **X-14** | `Bash` la agenții de review | **Rezolvată:** eliminat pentru `tenancy-guard`, `accounting-reviewer` și `fiscal-reviewer`; **restaurat pentru `schema-reviewer`**, restrâns la două comenzi fixe read-only (`make schema-dump`, `make rls-report`), pre-aprobate în `.claude/settings.json`. Motivul restaurării: citirea unei migrări nu este același lucru cu inspectarea schemei rezultate, iar diferența dintre ele e chiar locul unde apar erorile |

Restul intrărilor din 4.1 și 4.2 rămân ca înregistrare a ceea ce s-a găsit.


Împărțit în două: **substituții intenționate** (amendamentul corectează deliberat V2 — le enumăr ca să fie clar ce versiune se aplică) și **contradicții reale** (unde documentele nu sunt de acord fără să o spună).

### 4.1 Substituții intenționate — amendamentul prevalează

| # | Subiect | V2 spune | Amendamentul spune | Se aplică |
|---|---|---|---|---|
| **X-7** | Invariantul 4 (conformitate) | „O modificare legislativă este un INSERT, nu un deployment." (§2.4). „Dacă o modificare de cotă TVA necesită deployment, procesul a eșuat." (§6) | Două straturi: parametri → date (INSERT), logică → cod versionat (deployment). Formularea din V2 era „prea largă". | **Amd §A.4** |
| **X-8** | Cheia de partiționare | „Cheia de partiționare trebuie decisă acum" (§4.4); „Chei primare pregătite pentru partiționare" în livrabilele F0 (§10) | Retrasă ca cerință blocantă; înlocuită cu disciplină (fără FK-uri intrând, coloană `NOT NULL`, indecși cu context). Decizia se ia după modelul de volum. | **Amd §B.3** |
| **X-10** | Restaurare per tenant | „am stricat ceva luni, adu-mi datele de vineri" prezentat ca reversibilitate posibilă la nivel logic (§12.1) | Formularea V2 este „greșită și periculoasă ca promisiune de produs". Trei concepte separate; cererea de restaurare la o stare anterioară **se refuză**. | **Amd §B.2** |
| **X-11** | Motorul de reguli fiscale | Un serviciu transversal cu date versionate (§5) | Două componente distincte: `FISCAL PARAMETERS` (date) și `FISCAL LOGIC` (cod, selectat prin registru după dată efectivă) | **Amd §B.1** |
| **X-19** | Partener | Decizie deschisă: „tenant-level partajat sau company-level cu suprascriere?" (§15.9) | Trei niveluri: `CounterpartyRegistry` → `Partner` → `CompanyPartner` | **Amd §C.1** |
| **X-20** | Evaluarea stocurilor | Decizie deschisă: „per companie sau per articol?" (§15.3) | Per **categorie**, cu implicit la nivel de companie. Per articol este „prea permisiv și nesusținut de standard". | **Amd §C.4** |

Aceste șase nu sunt erori. Sunt enumerate pentru ca formularea din V2 să nu fie citată accidental ca sursă în specificații.

### 4.2 Contradicții reale

#### X-1 — Amendamentul se contrazice pe decizia V2-7 (cumulativele payroll) &nbsp;`SEVERITATE: medie`

**Unde:** Amendament §E.

- Textul de sub tabel: „Deciziile 1, 3, 6, 7, **9** din lista V2 sunt închise prin acest amendament."
- Rândul 4 din **același tabel**: „Modelul cumulativelor payroll la activare în cursul anului | Blochează: Payroll schema | Termen: Înainte de F2" — adică **deschisă**.

Nicio secțiune din amendament nu conține o decizie privind cumulativele payroll.

**Rezolvare aplicată:** tratată ca **deschisă** (`DES-4`). Tabelul este registrul operativ, iar textul nu este susținut de conținut. Necesită corectarea amendamentului.

#### X-2 — Decizia V2-3 (evaluarea stocurilor) este simultan „închisă" și „deschisă" &nbsp;`SEVERITATE: mică`

**Unde:** Amendament §C.4 vs. §E rândul 6.

§C.4 închide modelul („per categorie"), dar se auto-califică drept „închidere provizorie" și cere „confirmare necesară de la contabilul practicant". §E o listează în ambele locuri: ca închisă în text, și ca deschisă în tabel (rândul 6, formulat însă ca *confirmare*, nu ca decizie).

**Rezolvare aplicată:** modelul este închis (`ÎNC-4`); confirmarea contabilă rămâne deschisă (`DES-6`). Nu blochează Spec A. Recomandare: reformulare explicită în amendament ca „decizie luată, validare pendinte".

#### X-3 — Decizia V2-6 (identitatea globală) e declarată închisă fără text care s-o închidă &nbsp;`SEVERITATE: mică`

**Unde:** Amendament §E („deciziile 1, 3, 6, 7, 9 … închise"), dar amendamentul nu conține nicio secțiune despre identitatea utilizatorului.

Închiderea este susținută indirect de V2 §4.1 („User — identitate **globală**"), de §F („nu se modifică modelul Tenant/Company/Firm/Engagement") și de spec §6.1 F0.3 („Identitatea utilizatorului este globală").

**Rezolvare aplicată:** tratată ca închisă (`ÎNC-2`), dar **necesită ADR explicit** în Etapa 3, pentru că o decizie cu efect asupra fiecărei tabele de identitate nu poate rămâne susținută doar de o notă de subsol.

#### X-4 — Faza multi-valutei și a integrării BNM: patru afirmații diferite &nbsp;`SEVERITATE: mare pentru planificarea F0`

| Sursă | Ce spune |
|---|---|
| V2 §10, Faza 0 | „Multi-valută în core" — livrabil F0 |
| V2 §11 (tabel) | Multi-valută: **Modelat F0**, **Implementat F2** |
| spec §4.1 (hartă) | `accounting/currency`: **Fază F1**, Model F0; `integrations/bnm`: **Fază F1**, Model F0 |
| spec §6.1 **F0.9** | „Multi-valută — model în core: sumă în valută, valuta, curs, sumă în MDL. **Integrare BNM pentru curs.** Fără reevaluare încă." — sarcină **F0** |

Diferența nu e cosmetică: F0.9 cere un conector BNM funcțional în F0, în timp ce harta plasează `integrations/bnm` în F1, iar V2 §11 plasează implementarea multi-valutei în F2.

**Ce prevalează:** amendamentul nu atinge subiectul, deci precedența nu îl rezolvă. Interpretarea coerentă este că **modelul de sumă multi-valută intră în F0** (altfel fiecare tabelă financiară se retrofitează), în timp ce *utilizarea* operațională (reevaluare, diferențe de curs) e F1/F2. Statutul conectorului BNM în F0 rămâne neclar.

**Necesită decizie umană:** conectorul BNM se implementează în F0 (conform F0.9) sau se amână la F1 (conform hărții)? Nu o închid.

#### X-5 — `warehouses` și `dimensions`: sarcina F0.7 cere modele pe care harta le plasează în F4/F1 &nbsp;`SEVERITATE: medie`

**Unde:** spec §6.1 **F0.7** cere explicit, ca livrabile F0: „`Warehouse` — model, fără funcționalitate" și „Dimensiuni analitice — model, fără modul de centre de cost". Harta §4.1 dă `masterdata/warehouses` Fază **F4** și `masterdata/dimensions` Fază **F1**.

Regula §4.2 („nu se creează app-uri Django goale pentru module din faze viitoare") face situația ambiguă: dacă modelul `Warehouse` trebuie să existe în F0, el trebuie să locuiască undeva, iar acel undeva este un app Django.

**Necesită decizie umană:** unde locuiesc modelele „modelate în F0, implementate mai târziu"? Trei variante posibile, niciuna aleasă de documente:
1. App-ul modulului se creează în F0 cu doar modelul (contrazice §4.2 doar aparent — app-ul nu e gol);
2. Modelele stau într-un app `masterdata` unic, cu submodule interne;
3. Se amână, iar F0.7 se reduce la ce e efectiv folosit în F0.

Aceeași întrebare se aplică pentru: `sales`, `purchases`, `payroll/employees`, `inventory/*`, `orders`, `contracts`, `workflow`, `billing/*`, `firmspace/workspace` — toate marcate „Model F0".

#### X-6 — Lista excepțiilor de la `tenant_id` este incompletă &nbsp;`SEVERITATE: mare — blochează suita 2`

**Unde:** spec §1.1 R1 și Amd §D.3 enumeră aceleași patru excepții: „registru global de contrapărți, parametri fiscali, curs BNM, tabele de sistem Django".

Dar V2 §4.3 clasifică drept **globale** și: `Users`, și **planul de conturi SNC (template)**. Niciuna nu apare în lista de excepții. În plus, lista nu tratează deloc tabelele care *definesc* tenancy-ul:

- `Tenant` — nu poate avea `tenant_id` care să refere altceva decât pe sine
- `Firm` — firma are tenant propriu, dar tabela `Firm` este a cui?
- `Engagement` — leagă **două** tenant-uri (tenantul firmei și tenantul clientului). Care dintre ele este contextul RLS?
- `Membership`, `CompanyAccess` — la nivel de tenant, dar accesul se verifică *înainte* de a exista context
- Read models — poartă `tenant_id` **și** `firm_id`, cu politică diferită (ÎNC-14)

**Consecință directă:** suita 2 (gardian de model, F0.2) nu poate fi scrisă corect fără lista completă și motivată, iar F0.2 precede orice model. Aceasta este cea mai timpurie problemă blocantă din tot inventarul.

**Necesar:** lista limitativă completă, cu motivul fiecărei excepții, în Spec A. Vezi **G-02**.

#### X-9 — `platform/notifications` nu are sarcină F0 asociată &nbsp;`SEVERITATE: mică`

V2 §10 (Faza 0) enumeră „Document core, numerotare, atașamente, **notificări**", iar harta §4.1 dă `platform/notifications` Fază F0 / Model F0. Sarcina **F0.6** acoperă însă doar „Document core, numerotare, atașamente" — notificările lipsesc din descompunerea F0.1–F0.10, la fel ca din criteriul de ieșire din F0.

**Rezolvare propusă (Etapa 6):** fie se adaugă explicit la F0.6, fie se marchează ca livrabil F0 fără sarcină și se amână motivat. Nu decid acum.

#### X-12 — Două structuri incompatibile pentru `docs/` &nbsp;`SEVERITATE: mică, dar afectează Etapa 1`

| Sursă | Structură |
|---|---|
| spec §3 (arborele repo-ului) | `docs/master-plan-v2.md`, `docs/amendment-1.md`, `docs/implementation-spec.md`, `docs/spec-a-tenancy.md`, `docs/spec-b-accounting.md`, `docs/decisions/` |
| BOOTSTRAP §3, Etapa 3 | `docs/_input/` (read-only), `docs/_bootstrap/`, `docs/specs/`, `docs/decisions/`, `docs/PROGRESS.md` |

În plus, numele reale de pe disc diferă de tabelul din BOOTSTRAP §1: `evidenta-master-plan-v2.md`, `evidenta-master-plan-v2-amendament-1.md`, `evidenta-implementation-spec.md`.

**Rezolvare aplicată:** structura din BOOTSTRAP prevalează (este instrucțiunea acestei sesiuni și `docs/_input/` este declarat read-only). Arborele din spec §3 se folosește pentru tot ce nu ține de `docs/`. În Etapa 1 voi trata această divergență explicit, nu tacit.

#### X-13 — Localizare: `ru` apare doar în arborele de directoare &nbsp;`SEVERITATE: mică`

spec §3 conține `frontend/src/locales/ ← ro, ru`, dar spec §2.5 spune „Interfață, documentație de utilizator, denumiri contabile: **română**", iar V2 nu menționează limba rusă nicăieri — nici în poziționare, nici în roadmap, nici în structura comercială.

**Necesită decizie umană:** limba rusă este în scop pentru interfață? Are efect asupra modelului de date (denumiri de conturi, de documente, de rapoarte pot avea nevoie de traduceri stocate, nu doar de fișiere de resurse) și asupra costului fiecărui ecran. Nu o închid.

#### X-14 — Agenții de review sunt declarați read-only, dar primesc `Bash` &nbsp;`SEVERITATE: mică, relevantă pentru Etapa 2`

spec §5.2 definește `tenancy-guard`, `schema-reviewer`, `accounting-reviewer` și `fiscal-reviewer` cu `tools: Read, Grep, Glob, Bash` și cu instrucțiunea „Never edit files". `Bash` permite scrierea. BOOTSTRAP Etapa 2 cere explicit „agenții de review sunt read-only fără excepție" și „setul minim de unelte necesar, nu mai mult".

**Rezolvare propusă în Etapa 2:** fie se elimină `Bash`, fie se păstrează cu justificare explicită (ex. `schema-reviewer` are nevoie de `psql` pentru a inspecta schema). Ridic problema atunci, cu opțiunile.

#### X-15 — Divergențe minore de fază, semnalate fără acțiune

| Subiect | V2 §11 | spec §4.1 |
|---|---|---|
| Workflow și aprobări | Modelat **F0/F1**, implementat F5 | Model **F0**, Fază F5 |
| Dimensiuni analitice | Modelat F0, implementat **F1** | Model F0, Fază **F1** — coerent |
| Loturi / numere de serie | Modelat F0, implementat F4 / F4+ | Model F0, Fază F4 / F4 — coerent |

Singura divergență este „F0/F1" vs „F0" pentru workflow. Fără efect practic; se rezolvă la modelarea documentului (stare + posibilitate de aprobare în F0.6).

### 4.3 Erori factuale sau de redactare

| # | Unde | Ce |
|---|---|---|
| E-1 | Amd §E, text sub tabel | Enumeră „deciziile 1, 3, 6, 7, 9" ca închise; 7 este contrazisă de propriul tabel, 6 nu are secțiune corespunzătoare, 3 este închisă doar provizoriu. Vezi X-1, X-2, X-3. |
| E-2 | BOOTSTRAP §1, tabel | Numele fișierelor din tabel (`master-plan-v2.md` etc.) nu corespund celor de pe disc (prefixate `evidenta-`). |
| E-3 | spec §1.1 R1 și Amd §D.3 | Listă de excepții identică și incompletă în ambele documente — un `Users` global fără `tenant_id` va face suita 2 să eșueze corect, dar din motiv greșit. Vezi X-6. |
| E-4 | spec §6.1, criteriu de ieșire F0 | „Modelul de volum de date este livrat" apare ca criteriu de ieșire, dar nu are sarcină F0.x corespunzătoare (F0.1–F0.10 nu îl conțin). Sursa cerinței este Amd §B.3. |

---

## 5. Raport de goluri

Ce este necesar pentru implementare și **nu există** în documentele de intrare. Nu completez niciunul din memorie. Coloana „Se rezolvă în" indică artefactul care trebuie să conțină răspunsul.

### 5.1 Tenancy, identitate, acces (Spec A)

| # | Gol | De ce e necesar | Blochează | Se rezolvă în |
|---|---|---|---|---|
| **G-01** | Câmpurile, tipurile, constrângerile, indicii și relațiile pentru `Tenant`, `Company`, `Firm`, `Engagement`, `User`, `Membership`, `CompanyAccess`, `CapabilityActivation`. Documentele dau doar rolul fiecărei entități, într-o frază. | Fără ele nu există migrare | F0.3, F0.5 | **Spec A** (Etapa 4) |
| **G-02** | Nivelul exact al fiecărei tabele `platform` și lista **completă** a excepțiilor de la `tenant_id`, cu motiv. Include: pe ce tenant e ancorat `Engagement` (leagă două), unde stă `Firm`, cum se verifică `Membership` înainte de a exista context. | Suita 2 (F0.2) nu poate exista fără ea; F0.2 precede orice model | **F0.2 — cel mai timpuriu blocaj** | **Spec A**. Vezi X-6 |
| **G-03** | Setul complet de variabile de sesiune. Documentele numesc `app.tenant_id` și `app.actor_firm_id`. Lipsesc: contextul de companie (tabelele company-scoped sunt majoritatea ledgerului), identitatea utilizatorului, corelatorul de sesiune/request. | Fără `app.company_id` sau echivalent, izolarea între companiile aceluiași tenant se face în aplicație, nu în DB — ceea ce contrazice „două bariere independente" | F0.1 | **Spec A** |
| **G-04** | Forma efectivă a politicilor RLS (`USING` / `WITH CHECK`), separat pentru: tabele tenant-level, company-level, read models (tenant + firm), globale. Plus forma exactă a comportamentului fail-closed. | BOOTSTRAP Etapa 4 pct. 2 o cere „în formă aproape-SQL"; V2 §4.2 o descrie doar conceptual | F0.1, F0.2 | **Spec A** |
| **G-05** | Modelul de roluri și permisiuni. `Membership` „cu roluri" și `CompanyAccess` „cu rol" — rolurile nu sunt enumerate nicăieri. Nici drepturile speciale (ex. „redeschiderea perioadei necesită permisiune specială" — a cui?). | RBAC e cerut din F0 (V2 §12.3) | F0.3 | **Spec A** |
| **G-06** | Reprezentarea concretă a scope-ului de Engagement: „ce companii, ce module, ce drepturi". Nu există structură, nici efect asupra politicii RLS (un engagement cu scope restrâns trebuie să restrângă rândurile, nu doar UI-ul). | Suita 1 testează explicit „engagement cu scope restrâns" | F0.2, F0.3 | **Spec A** |
| **G-07** | Ciclul de viață complet al Engagement-ului: denumirile canonice ale stărilor, matricea de tranziții permise, cine le poate declanșa, ce se întâmplă cu documentele în lucru la revocare, cum funcționează transferul între firme, ce anume „se păstrează în istoric". | V2 §9.1 dă traseul grafic, fără semantică | F0.3 | **Spec A** |
| **G-08** | Subdomeniul: format, unicitate, nume rezervate, procedura de schimbare, subdomeniul tenantului propriu al firmei, rezolvarea în dev/staging, comportament la subdomeniu inexistent. | C8 face din subdomeniu singura sursă a contextului de tenant | F0.1, F0.10 | **Spec A** |
| **G-09** | Autentificare: MFA obligatoriu sau opțional și pentru cine, politica de parole, durata și invalidarea sesiunilor, fluxul de invitație (token, expirare), recuperarea contului, parametrii concreți de rate limiting. | V2 §12.3 le cere din F0, fără parametri | F0.3, F0.10 | **Spec A** |
| **G-10** | Enumerarea **limitativă** a căilor privilegiate și mecanismul tehnic prin care izolarea se ridică (rol separat? variabilă de sesiune dedicată? funcție `SECURITY DEFINER`?), plus forma auditului obligatoriu pentru fiecare. V2 §4.2 dă patru exemple („facturarea abonamentelor, polling SFS, curs BNM, aplicarea regulilor fiscale noi") și le numește „singurele locuri" — dar exemplele nu sunt o enumerare. | INV-10 și R7 se referă la o listă care nu există | F0.1 | **Spec A** |
| **G-11** | Read models: tabelele concrete, agregatele conținute, cadența și declanșatorul actualizării, politica RLS proprie, ce se întâmplă cu rândurile agregate la revocarea engagement-ului, cum se reconstruiesc. **Observație de secvențiere:** `platform/readmodels` este Fază F3, dar sursele lor (documente închise) apar din F2 — calea de scriere trebuie proiectată încât F2 să nu necesite retrofit. | BOOTSTRAP Etapa 4 pct. 7; ÎNC-14 face din ele singura excepție cross-tenant | F3 (dar decizia de model — F0) | **Spec A** |
| **G-12** | **Termenele legale de păstrare a documentelor contabile în Republica Moldova**, perioada de grație la offboarding, regimul de arhivare, formatul exportului complet, ce se șterge efectiv și ce nu. V2 §12.2 spune „au termene legale" fără să le numească. | Afectează modelul de date, deci se decide acum (V2 §12.2) | Spec A | **Spec A — necesită sursă legală citată, nu deducție.** Marcat ca „DECIZIE NECESARĂ" în Etapa 4 |
| **G-13** | Mecanismul de **enumerare completă a efectelor** unei sesiuni / utilizator / interval: ce corelator există (session_id? request_id?), pe ce tabele se propagă, cum se ajunge de la un interval de timp la mulțimea de journal entries produse. Amd §B.2 îl declară „cerință funcțională, nu efect secundar al audit-ului" — dar nu îl proiectează. R21 interzice FK-uri spre `audit_events`, deci legătura trebuie să existe invers, pe entitățile financiare. | Susține corecția de business, singurul răspuns produsului la cererea de restaurare | F0.4 | **Spec A** |
| **G-14** | Modelul de billing: entitățile (`Subscription`, `Plan`, `Invoice`?), relația exactă cu `CapabilityActivation`, cine este facturat în modelul wholesale, cum se separă capability set de plan comercial la nivel de date, moneda și TVA pe abonament, ce se întâmplă la neplată. | BOOTSTRAP Etapa 4 pct. 10 | F3, dar modelul e F0 | **Spec A** |
| **G-15** | Release rings: definiție, câte, cum se atribuie tenanții, relația cu feature flags, cine mută un tenant între ringuri. | INV-5 se sprijină pe ele | F0.5 | **Spec A** |

### 5.2 Audit, documente, master data (F0.4, F0.6, F0.7)

| # | Gol | De ce e necesar | Blochează | Se rezolvă în |
|---|---|---|---|---|
| **G-16** | `AuditEvent`: câmpurile sunt enumerate ca listă de concepte (tenant, companie, utilizator, acțiune, entitate, valoare anterioară, valoare nouă, IP, sesiune, sursă, moment) fără tipuri, fără formatul valorilor before/after (JSON? diff?), fără lista entităților auditate, fără politica de retenție și fără cine are drept de citire. | F0.4 | F0.4 | **Spec A** |
| **G-17** | `Document core`: câmpurile concrete și, mai ales, **variantele de stare per domeniu** („`Draft → Confirmed → Posted → Completed`, cu variante per domeniu" — variantele nu sunt date). | F0.6 | F0.6 | **Spec A** |
| **G-18** | Numerotare: gramatica seriilor (format, componente, resetare anuală), garanția de unicitate, dacă golurile sunt permise, comportamentul la anulare și storno, și **ce înseamnă „filială"** — entitatea nu există în modelul de tenancy (există Tenant, Company; nu există Branch). Decizia `DES-2` nu poate fi luată până când nu se știe ce e o filială. | F0.6 | F0.6 | **Spec A** |
| **G-19** | `document_events`: apare doar în lista tabelelor append-only (R21), fără nicio descriere a scopului sau a câmpurilor. | R21/R22 îl impun ca tabelă reală | F0.6 | **Spec A** |
| **G-20** | Atașamente: layout-ul în S3, separarea per tenant (bucket? prefix?), semnarea URL-urilor, limite de dimensiune și tip, scanare antivirus, retenție, ce se întâmplă la offboarding. | F0.6 | F0.6 | **Spec A** |
| **G-21** | Notificări: canale, evenimente care le declanșează, șabloane, limba, preferințe per utilizator. Vezi și X-9 (modulul nu are sarcină F0). | F0 (V2 §10) | F0.6 | **Spec A** sau backlog F0 |
| **G-22** | `CounterpartyRegistry`: sursa publică de date, cadența de actualizare, regimul juridic al utilizării, câmpurile exacte, comportamentul când sursa e indisponibilă. **Și o tensiune de proiectare neabordată:** efectul de rețea descris în Amd §C.1 („când emitentul și destinatarul sunt amândoi în Evidenta, factura apare direct în lista de documente primite a destinatarului") presupune o cale prin care date ale tenantului A ajung la tenantul B. Aceasta este cross-tenant și nu apare în nicio listă de căi privilegiate, nici în read models. | ÎNC-3, INV-10 | F0.7 | **Spec A — necesită decizie explicită** |
| **G-23** | `Partner` și `CompanyPartner`: câmpurile sunt enumerate ca listă de concepte în Amd §C.1, fără tipuri, fără reguli de unicitate (IDNO unic per tenant?), fără comportamentul la modificarea datelor în registrul global. | F0.7 | F0.7 | **Spec A** |
| **G-24** | `Item`, `UnitOfMeasure`, conversii: câmpuri, tipuri de articol (marfă / serviciu / produs?), indicatorii de urmărire pe lot și pe număr de serie (ceruți „modelat F0"), precizia cantităților. | F0.7 | F0.7 | **Spec A** |
| **G-25** | Dimensiuni analitice: cele 10 sunt enumerate (Partener, Articol, Angajat, Contract, Depozit, Proiect, Departament, Centru de cost, Activ, Comandă de producție), dar lipsesc tipurile, obligativitatea per cont, validarea, și **decizia de reprezentare** — coloane fixe pe linia de jurnal sau tabel de dimensiuni? Are efect direct asupra indicilor și a dimensiunii lui `journal_lines`. | V2 §7.2 le numește „exemplul canonic de decizie ieftină acum și foarte scumpă peste un an" | F0.7 → F1.2 | **Spec B** (structura liniei), semnalat în **Spec A** |

### 5.3 Fiscal (F0.8, F1.6)

| # | Gol | De ce e necesar | Blochează | Se rezolvă în |
|---|---|---|---|---|
| **G-26** | Schema unui parametru fiscal: cheie, tip de valoare, scope (global / tenant / companie), unitate de măsură, precizie, cum se reprezintă un parametru compus (grile progresive, plafoane cu praguri). | F0.8 | F0.8 | **Spec B** |
| **G-27** | Registrul de logică fiscală: forma înregistrării, cum se declară intervalul de valabilitate al unei implementări, cum se face selecția după data efectivă, cum se testează două implementări simultan. | INV-4, R17, R18 | F0.8 | **Spec B** |
| **G-28** | **Valorile fiscale efective**: cotele TVA, cotele CNAS și CNAM, plafoanele salariale, scutirile personale, cotele de impozit pe venit, pragurile de înregistrare, termenele de raportare, coeficienții de amortizare. Documentele enumeră **categoriile**, niciodată valorile. | Fără ele nu există niciun calcul | F1.6, F2 | **Sursă externă + contabil practicant.** Nu se deduc, nu se completează din memorie |
| **G-29** | Corpusul de regresie: de unde vin cazurile reale, procedura de anonimizare, formatul de stocare, cine validează rezultatul așteptat, câte cazuri sunt suficiente. | Amd §D.2, necesar din F1 | F1.10 | **Spec B** + proces |

### 5.4 Contabilitate (Spec B)

| # | Gol | De ce e necesar | Blochează | Se rezolvă în |
|---|---|---|---|---|
| **G-30** | **Conținutul planului de conturi SNC** — lista efectivă a conturilor. Documentele descriu cum se versionează template-ul, niciodată ce conține. | F1.1 | F1.1 | **Sursă externă (SNC) + contabil practicant** |
| **G-31** | Politica de propagare a modificărilor de template către instanțele existente — `DES-3`, deschisă, fără opțiuni descrise. Întrebarea din V2 §7.1 („ce se întâmplă cu cele 8.000 de companii care au instanțiat versiunea veche?") rămâne fără variante evaluate. | F1.1 | F1.1 | **Spec B** — de marcat „DECIZIE NECESARĂ" cu opțiuni |
| **G-32** | `JournalEntry` / `JournalLine`: câmpuri, tipul și precizia sumelor, reprezentarea debit/credit (coloane separate sau sumă cu semn), cheile primare (`bigint` pentru linii, per C6), și **cum se face navigarea inversă** `JournalEntry → JournalLine` fără FK (R21 interzice FK-uri spre `journal_lines`; navigarea în ambele sensuri cerută de INV-9 trebuie deci să se sprijine pe index, nu pe constrângere). | F1.2 | F1.2 | **Spec B** |
| **G-33** | Mecanismul concret prin care Σ Debit = Σ Credit se verifică „la nivel de bază de date" (R11): trigger la commit? constrângere pe o coloană agregată în `journal_entries`? constrângere `DEFERRABLE`? Fiecare variantă are alt cost și alt comportament la import în masă. | R11 | F1.2 | **Spec B** |
| **G-34** | Perioade: granularitatea (lună? trimestru?), relația cu anul fiscal, matricea de tranziții între cele patru stări numite (deschisă / în închidere / închisă / blocată), dacă blocarea e per companie sau per modul, cine poate redeschide. | F1.5 | F1.5 | **Spec B** |
| **G-35** | Multi-valută: precizia și regula de rotunjire pentru MDL și pentru valută, tipurile de curs (BNM, manual, contractual), conturile de diferențe de curs, momentul reevaluării, ce curs se folosește pentru baza TVA. | F0.9 model, F1+ implementare | F0.9 | **Spec B** |
| **G-36** | Solduri inițiale: structura pentru fiecare din cele șase domenii (GL, clienți, furnizori, stocuri cu cantitate+cost, active, angajați cu cumulative anuale), procedura de validare la zero diferență, ce se întâmplă la corecție. | F1.7; condiție a migrării din 1C | F1.7 | **Spec B** |
| **G-37** | Storno: modelul concret (înregistrare inversă sau linii cu semn negativ), efectul asupra rulajelor și al rapoartelor, cine are dreptul, ce se întâmplă la storno într-o perioadă închisă. | INV-2, INV-9, R14 | F1.2 | **Spec B** |
| **G-38** | Idempotență și deduplicare: compoziția cheii de idempotență, TTL-ul, comportamentul la conflict (aceeași cheie, payload diferit), și **cheile naturale de deduplicare per tip de document** (ce anume identifică „același document economic" pentru o factură, un extras bancar, un e-Factura). | INV-8, R19, R20, C9 | F1.3 | **Spec B** |
| **G-39** | `AccountingEvent`: câmpuri, taxonomia tipurilor de eveniment, versionarea payload-ului, relația cu documentul sursă. | F1.3 | F1.3 | **Spec B** |
| **G-40** | Posting rules: forma regulilor (date în DB? DSL? cod?), algoritmul de rezoluție, cum intră profilul de capabilități ca input, cum se testează o regulă, cum se versionează după dată efectivă. | R26, F1.4 | F1.4 | **Spec B** |

### 5.5 Infrastructură, tooling, CI

| # | Gol | De ce e necesar | Blochează | Se rezolvă în |
|---|---|---|---|---|
| **G-41** | Versiunile exacte: Python, Django, DRF, PostgreSQL (spec zice „16+"), Redis, Celery, Node, React, Vite. | Etapa 1 | Etapa 1 | Decizie în Etapa 1, consemnată ca ADR |
| **G-42** | Tooling Python: manager de pachete (uv / poetry / pip-tools), linter și formatter, type checker, pre-commit. | Etapa 1 | Etapa 1 | Etapa 1 |
| **G-43** | CI: platforma (GitHub Actions? GitLab CI?), joburile, și în special **cum rulează suitele de izolare sub rolul de aplicație** într-un runner efemer. | ÎNC-15, T1 | F0.2 | Etapa 1 / F0.2 |
| **G-44** | Unealta care verifică regulile de dependență D1–D6 (ex. `import-linter`) și fișierul ei de contracte. | D1–D6 | F0 | Etapa 1 |
| **G-45** | `docker-compose.yml`: imaginile concrete, volumele, healthcheck-urile, porturile, variabilele de mediu. BOOTSTRAP cere scheletul în Etapa 1, dar niciun document nu dă parametrii. | Etapa 1 | Etapa 1 | Etapa 1 — voi folosi valori implicite evidente și le voi marca explicit ca alegeri de schelet, reversibile |
| **G-46** | Provider S3 și layout-ul bucket-urilor în dev / staging / prod; unde stau credențialele. | F0.6 | F0.6 | Etapa 1 |
| **G-47** | Relația între migrațiile Django și SQL-ul manual din `infra/migrations/` (politici RLS, roluri): cine le aplică, în ce ordine, cum se garantează că o tabelă nouă primește politică **înainte** de a fi folosită. | R2, suita 2 | F0.1 | **Spec A** + Etapa 1 |
| **G-48** | Procedura de creare a rolurilor DB (`db_roles.sql`) în dev, CI, staging, prod, și cum se împacă cu utilizatorul implicit al Django în teste. | F0.1 | F0.1 | F0.1 |
| **G-49** | Mediile: unde se găzduiește, cum se gestionează secretele, cum se configurează backup și PITR (promise ca SLA în Amd §B.2). | V2 §12.3 | F0 → producție | Decizie separată, în afara Etapelor 0–6 |

### 5.6 Frontend

| # | Gol | De ce e necesar | Blochează | Se rezolvă în |
|---|---|---|---|---|
| **G-50** | Bibliotecă de componente / design system, management de stare, client HTTP, rutare, i18n (și dacă `ru` e în scop — X-13), formatarea numerelor și datelor pentru RM, testarea frontend. | F0.10 | F0.10 | Decizie în Etapa 1 sau F0.10 |
| **G-51** | Rezoluția subdomeniului în dezvoltare locală (C8 face din subdomeniu sursa contextului; `localhost` nu are subdomenii fără configurare). | F0.10 | F0.10 | F0.10 |

### 5.7 Integrări

| # | Gol | De ce e necesar | Blochează | Se rezolvă în |
|---|---|---|---|---|
| **G-52** | e-Factura / SFS: contractul API, metoda de autentificare (certificat digital?), lista de statusuri, politica de retry, formatul payload-ului arhivat, existența unui mediu de test. Riscul „API SFS instabil sau nedocumentat" e listat ca ridicat în V2 §14, fără date concrete. | F2 | F2 | Sursă externă (SFS) |
| **G-53** | CNAS / CNAM / BNS: formatele rapoartelor, canalele de depunere, dacă există API sau doar încărcare manuală. | F2 | F2 | Sursă externă |
| **G-54** | BNM: endpoint-ul cursului, formatul, cadența, comportamentul în zile nelucrătoare și la indisponibilitate. | F0.9 / F1 | F0.9 | Sursă externă |
| **G-55** | Bănci: formatele de extras acceptate și lista băncilor vizate. | F2 | F2 | Sursă externă |
| **G-56** | 1C: versiunile și configurațiile suportate, metoda de extragere (ODBC? export de fișiere? COM?). Migrarea e „instrumentul de vânzare", dar nu are nicio specificație tehnică. | F1.9 | F1.9 | Decizie + investigație |

### 5.8 Non-funcțional și proces

| # | Gol | De ce e necesar | Blochează | Se rezolvă în |
|---|---|---|---|---|
| **G-57** | Țintele numerice de performanță pentru cele patru scenarii din V2 §12.4 (balanță pe 5 ani, închidere de perioadă cu volum mare, dashboard cu 100 de clienți, generarea declarației TVA). V2 cere fixarea lor „înainte de F1". | Determină indecșii și read models | Înainte de F1 | Decizie umană |
| **G-58** | Modelul de volum de date (livrabil F0 conform Amd §B.3): scenarii mic / mediu / mare cu date reale „de la o firmă de contabilitate colaboratoare" — firma nu este identificată, iar sarcina nu apare în F0.1–F0.10 (vezi E-4). | Decizia `DES-1` | F0 | Backlog F0 (Etapa 6) + decizie umană |
| **G-59** | SLA-ul intern de conformitate: V2 §6 propune 5 zile lucrătoare pentru cote și praguri, 15 pentru formulare noi — explicit ca „propunere", neconfirmată. | Operațiunea de conformitate | Lansare | Decizie umană |
| **G-60** | Contabilul practicant în echipă sau sub contract: listat ca „condiție de start" în registrul de riscuri, neconfirmat. Blochează G-28, G-30, DES-6 și validarea corpusului de regresie. | Riscul „lipsa expertizei contabile" e marcat **critic** | F1 | Decizie umană |
| **G-61** | Guvernanța: cine aprobă o excepție de la un invariant („orice excepție se documentează explicit și se aprobă" — V2 §2), cine aprobă un ADR, cine aprobă un plan de arhivare pentru C5. | Toate regulile care spun „aprobat" | Etapa 3 | `docs/decisions/README.md` |

### 5.9 Sinteză a golurilor

- **61 de goluri**, din care **15 blochează Spec A**, **11 blochează Spec B**, **9 sunt de infrastructură/tooling** (rezolvabile în Etapa 1 prin alegeri reversibile, marcate ca atare), **5 necesită surse externe instituționale** și **5 necesită decizii umane de proces**.
- **Golul cel mai timpuriu este G-02** (lista completă a excepțiilor de la `tenant_id`), pentru că F0.2 — suita de gardian de model — precede orice model, iar suita nu poate fi scrisă fără lista de excepții.
- **Golurile care nu se pot închide intern:** G-12 (retenție legală), G-28 (valori fiscale), G-30 (plan de conturi SNC), G-52–G-55 (formate și API-uri instituționale). Acestea cer surse oficiale sau contabil practicant. Nu le voi deduce în niciuna dintre etapele următoare.

---

## 6. Ce urmează

**Ordinea sarcinilor F0 este fixă și nu se rearanjează** (spec §6.1): F0.1 (roluri DB și infrastructură RLS) → F0.2 (suitele de verificare) → F0.3 (tenancy și identitate) → … Ambele preced orice model.

Consecință directă pentru planificare: **G-02, G-03, G-04 și G-10 trebuie rezolvate în Spec A înainte ca F0.1 și F0.2 să poată fi executate**, deși F0.1/F0.2 sunt primele sarcini de implementare. Spec A (Etapa 4) este pe drumul critic al întregului proiect.

Puncte care necesită răspuns uman înainte de a avansa dincolo de Etapa 3 sunt consolidate în raportul de checkpoint al Etapei 0 și vor intra în `docs/decisions/000-open-decisions.md` la Etapa 3.
