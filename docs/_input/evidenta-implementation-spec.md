# Evidenta.md — Document de Implementare pentru Claude Code

**Versiune:** 1.0
**Statut:** specificație de implementare. Derivă din Master Plan V2 + Amendamentul 1.
**Acoperire:** F0 și F1 în detaliu executabil. F2–F5 ca structură și obiective.

---

## 0. Cum se folosește acest document

Acest document **nu se dă integral** lui Claude Code ca instrucțiune permanentă. Se descompune în trei artefacte cu roluri diferite:

| Artefact | Locație | Conținut | Când e citit |
|---|---|---|---|
| Reguli permanente | `CLAUDE.md` (rădăcină) | Secțiunile 1, 2, 4.3, 8 | La fiecare sesiune, automat |
| Definiții de agenți | `.claude/agents/*.md` | Secțiunea 5 | La pornirea sesiunii |
| Referință | `docs/` | Acest document, V2, Amendamentul 1, Spec A, Spec B | La cerere, când agentul are nevoie de context |

**Motivul separării:** `CLAUDE.md` intră în context la fiecare sesiune, deci fiecare cuvânt din el costă. Regulile trebuie să fie scurte, imperative și verificabile. Roadmap-ul, justificările și discuția de produs stau în `docs/` și se citesc doar când sunt relevante.

**Regula de aur pentru sesiuni:** o sesiune Claude Code = un modul sau o capabilitate, niciodată „implementează Faza 0". Sarcinile largi produc cod plauzibil care încalcă invarianți subtil.

---

## 1. Invarianți — conținut pentru CLAUDE.md

Acestea sunt reguli, nu recomandări. Codul care le încalcă nu se comite, indiferent cât de bine funcționează.

### 1.1 Izolarea datelor

1. Fiecare tabelă business are `tenant_id`. Excepțiile sunt enumerate limitativ: registru global de contrapărți, parametri fiscali, curs BNM, tabele de sistem Django.
2. Fiecare tabelă business are politică RLS activă și `FORCE ROW LEVEL SECURITY`.
3. Contextul de tenant se setează cu `SET LOCAL` în interiorul unei tranzacții. Orice request rulează într-o tranzacție.
4. Absența contextului înseamnă zero rânduri sau eroare. Niciodată acces total.
5. Rolul de aplicație este diferit de rolul de migrare. Aplicația nu deține tabelele.
6. Fiecare task Celery primește `tenant_id` explicit ca argument și setează contextul înainte de orice query.
7. Interogările cross-tenant sunt permise **exclusiv** în stratul de read models și în căile privilegiate enumerate în Spec A.
8. Nicio parte din logica de business nu presupune că doi tenanți sunt fizic în aceeași bază de date.

### 1.2 Contabilitate

9. Niciun modul business nu scrie direct în ledger. Toate emit evenimente contabile către Posting Engine.
10. Ledgerul postat este imutabil. Corecția se face prin storno și reînregistrare. Niciun `UPDATE` pe `journal_entries` sau `journal_lines` postate.
11. Σ Debit = Σ Credit pe fiecare înregistrare, verificat la nivel de bază de date.
12. Postarea într-o perioadă închisă este refuzată la nivel de motor, nu de interfață.
13. Pentru orice efect financiar există lanțul complet, navigabil în ambele sensuri:
    `Journal Line → Journal Entry → Accounting Event → Source Document → Sursă`
14. O înregistrare de storno are două legături: spre documentul sursă și spre înregistrarea anulată.

### 1.3 Conformitate

15. **Parametrii fiscali sunt date** (cote, praguri, plafoane, scutiri, coeficienți, termene, mapări de conturi), versionate cu `valid_from` / `valid_to`.
16. **Logica fiscală este cod versionat** (algoritmi de calcul, scheme de declarații, validări, comportament API).
17. Selecția implementării se face printr-un registru, **după data efectivă a perioadei calculate**. Nicio condiție de tipul `if year >= 2027` în codul de business.
18. Recalcularea unei perioade trecute folosește parametrii și algoritmul valabili atunci.

### 1.4 Integritate operațională

19. Orice comandă sau eveniment extern cu efect financiar este idempotent, cu cheie de idempotență pe **evenimentul contabil**.
20. Deduplicarea documentelor economice (același document pe două căi) se face prin chei naturale de business, separat de idempotență.
21. Tabelele append-only de volum mare nu primesc chei străine. Lista: `journal_lines`, `inventory_movements`, `audit_events`, `document_events`, arhive payload e-Factura, arhive extrase bancare. Legăturile se fac invers.
22. Aceste tabele au coloana naturală de partiționare (`accounting_date` sau `occurred_at`) ca `NOT NULL` de la început.

### 1.5 Produs

23. Un singur codebase. Diferențierea prin feature flags, niciodată prin ramuri sau versiuni per tenant.
24. Conformitatea nu este niciodată capability plătibilă sau dezactivabilă.
25. Activarea unei capabilități este o entitate cu dată efectivă și stare de inițializare, nu un boolean.
26. Profilul de capabilități al tenantului este input al Posting Engine — aceeași operațiune se contabilizează diferit după capabilitățile active.

---

## 2. Stack și convenții

### 2.1 Stack

```
Frontend    React + TypeScript + Vite
Backend     Django + Django REST Framework
DB          PostgreSQL 16+ (RLS obligatoriu)
Cache/Queue Redis
Tasks       Celery
Storage     S3-compatible
Deploy      Containere, medii dev / staging / prod
```

### 2.2 Reguli Django

- **Un app Django per modul.** Fără app-uri „utils" sau „common" care acumulează logică.
- **Modelele nu conțin logică de business.** Serviciile o conțin. Modelele definesc structura și constrângerile.
- **Managerul implicit al modelelor business nu filtrează pe tenant.** Filtrarea o face RLS. Un manager care filtrează creează impresia falsă de siguranță și maschează absența contextului.
- **Fără signals pentru logică financiară.** Efectele contabile sunt explicite, apelate din servicii.
- **Migrațiile sunt aditive.** Nicio migrare nu șterge o coloană cu date financiare fără plan de arhivare aprobat.
- **UUID ca cheie primară** pentru entitățile expuse extern; `bigint` pentru tabelele append-only de volum mare.

### 2.3 Reguli API

- Versionare în cale: `/api/v1/...`
- Resursele urmează modulul: `/api/v1/accounting/`, `/api/v1/payroll/`
- Contextul de tenant vine din subdomeniu, nu din payload sau parametri
- Fiecare endpoint care produce efect financiar acceptă `Idempotency-Key`
- Erorile au cod stabil, nu doar mesaj

### 2.4 Reguli de test

- Fiecare modul are teste unitare pentru servicii
- Fiecare efect financiar are test de integrare care verifică lanțul complet până la journal line
- Suitele de izolare (secțiunea 6.1) rulează la fiecare commit
- Corpusul de regresie fiscală rulează la fiecare modificare de parametru sau algoritm

### 2.5 Limbă

- Cod, comentarii, nume de variabile, mesaje de commit: **engleză**
- Interfață, documentație de utilizator, denumiri contabile: **română**
- Termenii legali își păstrează forma oficială: `IDNO`, `TVA`, `IPC`, `CNAS`, `CNAM`, `SNC`, `e-Factura`

---

## 3. Structura repo-ului

```
evidenta/
├── CLAUDE.md                      ← reguli permanente
├── README.md
├── docker-compose.yml
├── Makefile
│
├── .claude/
│   ├── agents/                    ← definiții subagenți
│   │   ├── tenancy-guard.md
│   │   ├── schema-reviewer.md
│   │   ├── accounting-reviewer.md
│   │   ├── fiscal-reviewer.md
│   │   ├── test-author.md
│   │   └── repo-explorer.md
│   └── commands/                  ← workflow-uri repetabile
│       ├── new-module.md
│       ├── review-migration.md
│       └── isolation-check.md
│
├── docs/
│   ├── master-plan-v2.md
│   ├── amendment-1.md
│   ├── implementation-spec.md     ← acest document
│   ├── spec-a-tenancy.md
│   ├── spec-b-accounting.md
│   └── decisions/                 ← ADR-uri, câte un fișier per decizie
│
├── backend/
│   ├── manage.py
│   ├── pyproject.toml
│   ├── config/
│   │   ├── settings/
│   │   │   ├── base.py
│   │   │   ├── dev.py
│   │   │   ├── staging.py
│   │   │   └── prod.py
│   │   ├── urls.py
│   │   ├── celery.py
│   │   └── db_roles.sql           ← rol aplicație vs rol migrare
│   │
│   ├── evidenta/                  ← toate modulele (secțiunea 4)
│   │
│   └── tests/
│       ├── isolation/             ← suita 1: penetrare
│       ├── schema_guard/          ← suita 2: gardian de model
│       ├── fiscal_regression/     ← corpus de regresie
│       └── integration/
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── app/                   ← rutare, layout, context
│       ├── modules/               ← oglindește modulele backend
│       ├── shared/                ← componente, hooks, tipuri
│       └── locales/               ← ro, ru
│
└── infra/
    ├── docker/
    ├── migrations/                ← SQL manual: politici RLS, roluri
    └── ci/
```

---

## 4. Structura completă a modulelor

### 4.1 Harta modulelor

Coloana **Fază** indică momentul implementării. Coloana **Model** indică momentul în care structura de date trebuie să existe, chiar dacă funcționalitatea nu.

```
evidenta/
│
├── platform/                              Fază   Model
│   ├── tenancy/         Tenant, Company     F0     F0
│   ├── identity/        User, Membership    F0     F0
│   ├── engagement/      Firm, Engagement    F0     F0
│   ├── rls/             context, politici   F0     F0
│   ├── capabilities/    activare cu dată    F0     F0
│   ├── flags/           feature flags       F0     F0
│   ├── audit/           audit events        F0     F0
│   ├── documents/       document core       F0     F0
│   ├── numbering/       serii, numerotare   F0     F0
│   ├── attachments/     S3, metadate        F0     F0
│   ├── notifications/   in-app, email       F0     F0
│   └── readmodels/      agregate cross-tenant F3   F0
│
├── masterdata/
│   ├── counterparties/  registru global     F0     F0
│   ├── partners/        Partner (tenant)    F0     F0
│   │                    CompanyPartner      F0     F0
│   ├── items/           nomenclator         F0     F0
│   ├── uom/             unități, conversii  F0     F0
│   ├── warehouses/      depozit, zonă, bin  F4     F0
│   └── dimensions/      centre cost, proiecte F1   F0
│
├── fiscal/
│   ├── parameters/      cote, praguri (DATE) F0    F0
│   ├── logic/           algoritmi (COD)      F1    F0
│   ├── registry/        selecție după dată   F0    F0
│   └── admin/           Compliance Admin     F2    F1
│
├── accounting/
│   ├── coa/             plan conturi SNC     F1    F1
│   ├── ledger/          journal entry/line   F1    F1
│   ├── posting/         Posting Engine       F1    F1
│   ├── events/          Accounting Event     F1    F1
│   ├── periods/         perioade, închidere  F1    F1
│   ├── currency/        multi-valută, BNM    F1    F0
│   ├── openingbalances/ solduri inițiale     F1    F1
│   └── reports/         balanță, Cartea Mare F1    F1
│
├── tax/
│   ├── codes/           coduri fiscale       F2    F1
│   ├── vat/             registre TVA         F2    F1
│   └── declarations/    declarații fiscale   F2    F2
│
├── sales/               facturi, note credit F2    F0
├── purchases/           facturi furnizor     F2    F0
├── receivables/         AR, decontare        F2    F1
├── payables/            AP, decontare        F2    F1
├── banking/             conturi, extrase     F2    F1
├── cash/                casierie             F2    F1
├── assets/              active fixe          F2    F1
│
├── payroll/
│   ├── employees/       angajați             F2    F0
│   ├── contracts/       contracte muncă      F2    F0
│   ├── calculation/     calcul salarial      F2    F1
│   ├── contributions/   CNAS, CNAM, IPC      F2    F1
│   ├── leave/           concedii, medicale   F2    F1
│   ├── runs/            rulări, fluturași    F2    F2
│   └── parallelrun/     rulare în paralel    F2    F2
│
├── statutory/
│   ├── sfs/             rapoarte SFS         F2    F1
│   ├── cnas/            rapoarte CNAS        F2    F1
│   ├── cnam/            rapoarte CNAM        F2    F1
│   ├── bns/             rapoarte BNS         F2    F1
│   └── financials/      situații SNC         F2    F1
│
├── efactura/            e-Factura / SFS      F2    F1
│
├── firmspace/
│   ├── workspace/       dashboard contabil   F3    F0
│   ├── calendar/        termene per client   F3    F3
│   └── bulkops/         operațiuni în masă   F3    F3
│
├── migration/
│   ├── onec/            import 1C            F1    F1
│   ├── mapping/         mapare conturi/date  F2    F1
│   └── reconciliation/  verificare la zero   F3    F1
│
├── billing/
│   ├── subscriptions/   abonamente           F3    F0
│   ├── wholesale/       canal partener       F3    F0
│   └── direct/          canal direct         F3    F0
│
├── inventory/
│   ├── ledger/          inventory ledger     F4    F0
│   ├── movements/       mișcări              F4    F0
│   ├── valuation/       FIFO / CMP           F4    F0
│   ├── lots/            loturi               F4    F0
│   ├── serials/         numere de serie      F4    F0
│   └── counting/        inventariere         F4    F4
│
├── customs/             import, landed cost  F4    F4
├── orders/              comenzi v/c          F4    F0
├── pricing/             liste prețuri        F4    F4
│
├── hr/                  HR separat de payroll F5   F2
├── crm/                 CRM peste Partner    F5    F2
├── contracts/           registru contracte   F5    F0
├── workflow/            aprobări             F5    F0
│
└── integrations/
    ├── sfs/             API SFS              F2    F1
    ├── cnas/            API CNAS             F2    F2
    ├── cnam/            API CNAM             F2    F2
    ├── bns/             raportare BNS        F2    F2
    ├── bnm/             curs valutar         F1    F0
    ├── banks/           import extrase       F2    F2
    └── onec/            conector 1C          F1    F1
```

### 4.2 Regulă privind app-urile neimplementate

**Nu se creează app-uri Django goale pentru module din faze viitoare.**

Coloana „Model" din harta de mai sus nu înseamnă „creează app-ul acum". Înseamnă: când proiectezi un modul din faza curentă, structura de date trebuie să nu facă imposibil modulul viitor.

Exemple concrete de ce înseamnă asta:
- `dimensions` la F0 înseamnă că linia de jurnal are câmpuri de dimensiune de la început, nu că modulul de centre de cost există
- `lots` la F0 înseamnă că modelul de articol are indicatorul de urmărire pe lot, nu că gestiunea loturilor funcționează
- `workflow` la F0 înseamnă că documentul are stare și posibilitate de aprobare, nu că motorul de aprobări există

App-uri goale creează impresia că modulul e început, generează migrații inutile și confundă agenții care explorează repo-ul.

### 4.3 Reguli de dependență — conținut pentru CLAUDE.md

Graful de dependențe este **aciclic**. Direcția permisă:

```
platform  ←  totul poate depinde de platform
fiscal    ←  nu depinde de niciun modul business
masterdata ← depinde doar de platform
accounting ← depinde de platform, masterdata, fiscal
operations ← depinde de toate cele de mai sus
```

Interdicții explicite, verificate automat:

| Interdicție | Motiv |
|---|---|
| `fiscal` nu importă din niciun modul business | Ar crea ciclu; regulile fiscale sunt fundament |
| `accounting` nu importă din `sales`, `purchases`, `payroll`, `inventory` | Contabilitatea nu cunoaște sursa; primește evenimente |
| Modulele operaționale nu importă `accounting.ledger` | Doar `accounting.events` |
| `payroll` nu importă din `tax` | Ambele consumă `fiscal` |
| Nimic nu importă din `firmspace` | Este strat de prezentare peste read models |

Comunicarea între module se face prin: evenimente contabile, servicii publice ale modulului, sau read models. Niciodată prin import direct de modele.

---

## 5. Orchestrarea agenților

### 5.1 Ce funcționează și ce nu

Trei constatări care determină designul de mai jos:

- Subagenții **nu comunică între ei**. Raportează în sesiunea principală, care orchestrează.
- Subagenții **nu moștenesc contextul conversației principale**. Tot ce le trebuie — căi de fișiere, decizii, mesaje de eroare — trebuie inclus în promptul de delegare.
- Subagenții **nu moștenesc promptul de sistem** implicit. Definiția lor este completă și trebuie să fie autosuficientă.

**Consecință:** nu paralelizăm scrierea codului pe niveluri. Doi agenți care scriu simultan în module care se ating produc conflicte pe care nimeni nu le arbitrează. Paralelizăm **verificarea**.

Modelul corect:

```
Sesiune principală  ──  scrie codul, orchestrează
        │
        ├── tenancy-guard        (review, read-only)
        ├── schema-reviewer      (review migrații)
        ├── accounting-reviewer  (review efecte financiare)
        ├── fiscal-reviewer      (review parametri vs logică)
        ├── test-author          (scrie teste)
        └── repo-explorer        (recunoaștere, read-only)
```

### 5.2 Definiții de agenți

Fiecare fișier merge în `.claude/agents/`. Frontmatter configurează agentul; corpul devine promptul lui de sistem.

---

#### `.claude/agents/tenancy-guard.md`

```markdown
---
name: tenancy-guard
description: MUST BE USED after any change that adds or modifies a Django model, a
  queryset, a Celery task, or an API endpoint. Verifies tenant isolation compliance.
  Read-only — reports findings, does not edit.
tools: Read, Grep, Glob, Bash
model: sonnet
---

You audit tenant isolation in a multi-tenant Django accounting system that relies on
PostgreSQL Row Level Security.

For every file you are given, check:

1. Does every new business model have a tenant_id field? Allowed exceptions:
   global counterparty registry, fiscal parameters, BNM exchange rates, Django
   system tables. Anything else is a finding.
2. Does every new model have an RLS policy defined in infra/migrations/?
   A model without a matching policy is a critical finding.
3. Is FORCE ROW LEVEL SECURITY applied?
4. Does any queryset run outside a transaction where SET LOCAL is active?
5. Does every Celery task accept tenant_id explicitly and set context before
   any query? A task that derives tenant from global state is a critical finding.
6. Is there any cross-tenant query outside the readmodels layer or the
   enumerated privileged paths? Report it as critical.
7. Does any custom model manager filter by tenant? This is a finding — filtering
   belongs to RLS, and manager-level filtering masks missing context.

Output format:
- CRITICAL: findings that allow data leakage between tenants
- WARNING: findings that weaken defence in depth
- OK: explicit confirmation of what you verified

Never edit files. Report only. If you find zero issues, say so explicitly and
list what you checked.
```

---

#### `.claude/agents/schema-reviewer.md`

```markdown
---
name: schema-reviewer
description: MUST BE USED before committing any Django migration. Reviews primary
  keys, foreign keys, indexes, constraints and partition discipline. Read-only.
tools: Read, Grep, Glob, Bash
model: sonnet
---

You review database migrations for a multi-tenant PostgreSQL accounting system.

Check every migration for:

1. Append-only high-volume tables must NOT receive incoming foreign keys.
   The list: journal_lines, inventory_movements, audit_events, document_events,
   efactura payload archives, bank statement archives.
   A foreign key pointing at any of these is a CRITICAL finding — it makes
   future partitioning a schema redesign rather than a maintenance operation.

2. Those same tables must have their natural partition column
   (accounting_date or occurred_at) as NOT NULL.

3. Composite indexes must lead with tenant context:
   (tenant_id, company_id, ...) for company-scoped tables.
   A bare index on accounting_date alone is a finding.

4. Financial integrity constraints must exist at database level, not only in
   application code. Specifically: debit/credit balance per journal entry.

5. Migrations must be additive. Any migration dropping a column that holds
   financial data is a CRITICAL finding unless an approved archival plan is
   referenced in the migration docstring.

6. UUID primary keys for externally exposed entities; bigint for high-volume
   append-only tables.

Output CRITICAL / WARNING / OK. Never edit. Explain the consequence of each
finding, not just the rule it breaks.
```

---

#### `.claude/agents/accounting-reviewer.md`

```markdown
---
name: accounting-reviewer
description: MUST BE USED for any change that produces, modifies or consumes a
  financial effect — postings, corrections, settlements, valuations, payroll
  results. Read-only.
tools: Read, Grep, Glob, Bash
model: sonnet
---

You review accounting correctness in an append-only double-entry system built
for Moldovan national accounting standards (SNC).

Verify:

1. No business module writes to the ledger directly. Modules emit accounting
   events; only the Posting Engine creates journal entries. A direct write is
   CRITICAL.

2. No UPDATE on posted journal_entries or journal_lines. Corrections happen
   through reversal plus re-entry. Any mutation of posted data is CRITICAL.

3. Every journal entry balances: sum of debits equals sum of credits.

4. Posting into a closed period is rejected by the engine, not by the UI.

5. Full lineage exists and is navigable in both directions:
   Journal Line -> Journal Entry -> Accounting Event -> Source Document -> Source.
   A financial effect without traceable origin is CRITICAL.

6. A reversal entry carries TWO links: to the source document and to the entry
   it reverses. Missing the second link is a finding — drill-down on accounts
   with corrections becomes incoherent without it.

7. Any operation that can be retried is idempotent, with the idempotency key on
   the accounting event rather than only on the API endpoint.

8. Where the posting outcome depends on active capabilities, the capability
   profile is an explicit input to rule resolution, not an implicit branch.

Output CRITICAL / WARNING / OK. Never edit.
```

---

#### `.claude/agents/fiscal-reviewer.md`

```markdown
---
name: fiscal-reviewer
description: MUST BE USED for any change touching tax rates, contributions,
  thresholds, payroll calculation, declaration schemas or statutory report
  generation. Read-only.
tools: Read, Grep, Glob, Bash
model: sonnet
---

You review the separation between fiscal parameters and fiscal logic in a
Moldovan accounting system.

Verify:

1. PARAMETERS live in data, never in code. Rates, thresholds, ceilings,
   personal exemptions, coefficients, reporting deadlines, default account
   mappings. A hardcoded rate is CRITICAL.

2. LOGIC lives in versioned code: calculation algorithms, declaration schemas,
   validation rules, institutional API behaviour. This is expected and correct.

3. Implementation selection happens through a registry keyed on the EFFECTIVE
   DATE OF THE PERIOD BEING CALCULATED. Any condition of the form
   `if year >= 2027` in business code is CRITICAL — recalculating a 2026 period
   in 2028 must use the 2026 algorithm.

4. Every parameter records its source: normative act, Monitorul Oficial number,
   publication date, effective date. A parameter without provenance is a finding.

5. Every parameter and every logic version carries valid_from / valid_to.

6. Changes to parameters or algorithms are covered by the fiscal regression
   corpus. A change with no corresponding regression case is a finding — a rate
   change for 2027 can silently break recalculation of 2025.

Output CRITICAL / WARNING / OK. Never edit.
```

---

#### `.claude/agents/test-author.md`

```markdown
---
name: test-author
description: Use to write or extend tests for a module that has just been
  implemented. Writes tests only — does not modify production code.
tools: Read, Write, Edit, Grep, Glob, Bash
model: sonnet
---

You write tests for a multi-tenant Django accounting system.

For any module you are given, produce:

1. Unit tests for services. Models hold structure; services hold logic — test
   the services.

2. Integration tests for every financial effect, asserting the complete chain
   from source document down to journal lines, including amounts and accounts.

3. Isolation tests: authenticated as Tenant A, attempt to reach every resource
   type of Tenant B. Expected result is always zero access. Include the cases
   that are easy to forget: expired engagement, revoked engagement, engagement
   with restricted scope, Celery task with no context set.

4. Idempotency tests: submit the same operation twice with the same key and
   assert exactly one financial effect.

5. Period tests: assert that posting into a closed period is rejected by the
   engine.

All isolation tests must run under the APPLICATION database role, never as
superuser or table owner. A test running as owner bypasses RLS and proves
nothing — if you cannot confirm the role, say so rather than writing a test
that gives false assurance.

Do not modify production code. If a test cannot pass because production code is
wrong, report that instead of adjusting the test to match the bug.
```

---

#### `.claude/agents/repo-explorer.md`

```markdown
---
name: repo-explorer
description: Use to map unfamiliar parts of the codebase, locate where a concept
  is implemented, or summarize a module before changing it. Read-only.
tools: Read, Grep, Glob
model: haiku
---

You map codebases and report structure. You never edit.

Given a question about where something lives or how a module is organised,
return:
- The files that matter, with paths
- The entry points
- The dependencies in and out
- Anything that looks inconsistent with the documented module dependency rules

Be concise. The caller wants a map, not a tutorial.
```

---

### 5.3 Cum se folosesc în practică

Secvența pentru o sarcină tipică:

```
1. Sesiune principală: implementează modulul
2. Delegă către tenancy-guard      → primește CRITICAL/WARNING/OK
3. Delegă către schema-reviewer    → dacă există migrații
4. Delegă către accounting-reviewer → dacă are efect financiar
5. Delegă către fiscal-reviewer    → dacă atinge conformitatea
6. Rezolvă constatările
7. Delegă către test-author
8. Rulează suitele complete
9. Commit
```

**Important la delegare:** promptul trebuie să conțină căile de fișiere concrete și contextul deciziei. Agentul nu vede conversația principală. „Verifică modulul de payroll" e insuficient; „verifică `backend/evidenta/payroll/services/calculation.py` și migrația `0007_payroll_run.py`, atenție la separarea parametri/logică pentru CNAS" e util.

### 5.4 Comenzi repetabile

În `.claude/commands/`, câte un fișier markdown per workflow. Trei care merită de la început:

- **`new-module.md`** — scaffolding-ul unui modul nou conform convențiilor: structură de directoare, servicii, politici RLS, teste de bază, înregistrare în graful de dependențe
- **`review-migration.md`** — lanțul complet de review pentru o migrare, cu delegare către `schema-reviewer` și `tenancy-guard`
- **`isolation-check.md`** — rulează ambele suite de izolare și raportează

---

## 6. Etapele de implementare

### FAZA 0 — Fundament

**Obiectiv:** platforma poate izola corect doi tenanți și un engagement, demonstrat prin teste automate.

**Nu se scrie niciun modul business în această fază.**

#### 6.1 — Ordinea sarcinilor

Ordinea contează. Fiecare pas depinde de cel anterior.

**F0.1 — Roluri de bază de date și infrastructură RLS**

Primul lucru, înaintea oricărui model.

- Rol de migrare (deține tabelele) separat de rol de aplicație
- Configurare Django pentru a folosi rolul de aplicație la runtime
- Mecanism de setare a contextului: `SET LOCAL app.tenant_id`, `app.actor_firm_id`
- Middleware care garantează că fiecare request rulează într-o tranzacție
- Decorator/context manager pentru task-uri Celery

> Django presupune implicit un singur utilizator de bază de date cu drepturi complete. Dacă acest pas se sare, RLS va fi activat și complet inefectiv, pentru că owner-ul tabelei ocolește politicile.

**F0.2 — Suitele de verificare**

Înaintea modelelor, nu după.

*Suita 1 — penetrare.* Autentificat ca Tenant A, se încearcă acces la fiecare tip de resursă a lui Tenant B. Rezultat așteptat: zero acces. Include engagement expirat, revocat, cu scope restrâns, și task Celery fără context.

*Suita 2 — gardian de model.* Enumeră toate tabelele din schemă și eșuează dacă vreuna nu are context de tenant, politică RLS activă sau `FORCE ROW LEVEL SECURITY`. Excepțiile sunt enumerate explicit într-o listă versionată.

Ambele rulează sub rolul de aplicație. Ambele intră în CI de la primul commit.

> Suita 1 prinde bug-urile de azi. Suita 2 prinde tabela pe care cineva o adaugă peste trei ani fără să știe regula. A doua este mai valoroasă pe termen lung.

**F0.3 — Tenancy și identitate**

Conform Spec A. Entități: `Tenant`, `Company`, `Firm`, `Engagement`, `User`, `Membership`, `CompanyAccess`.

Puncte critice:
- Identitatea utilizatorului este **globală**. Un contabil are un cont pentru toți clienții.
- Politica RLS admite două căi de acces: membru al tenantului, sau engagement activ.
- Engagement are ciclu de viață complet cu istoric păstrat la revocare.
- Subdomeniul identifică tenantul, nu firma.

**F0.4 — Audit**

`AuditEvent` cu: tenant, companie, utilizator, acțiune, entitate, valoare anterioară, valoare nouă, IP, sesiune, sursă, moment.

Cerință funcțională care depășește audit-ul clasic: **enumerarea completă a efectelor** unei sesiuni, ale unui utilizator sau ale unui interval. Aceasta susține corecția de business (secțiunea B.2 din Amendament) și nu apare gratuit dacă audit-ul e proiectat doar pentru citire.

**F0.5 — Capabilități și feature flags**

`CapabilityActivation` ca entitate: capabilitate, dată efectivă aliniată la granița perioadei, stare de inițializare, pas de inițializare.

Feature flags separate de capabilități: primele sunt tehnice (release rings), a doua sunt funcționale (ce a activat tenantul).

**F0.6 — Document core, numerotare, atașamente**

Concepte comune: număr, dată, companie, stare, valută, contraparte, sursă, creat de, aprobat de, stare de postare, atașamente, comentarii, istoric.

Stări generice: `Draft → Confirmed → Posted → Completed`, cu variante per domeniu.

Numerotare configurabilă pe companie, tip de document, an, serie. *(Decizia „per companie sau per filială" rămâne deschisă — vezi Spec A.)*

**F0.7 — Master data**

- `CounterpartyRegistry` — registru global după IDNO
- `Partner` — nivel tenant
- `CompanyPartner` — configurare per companie
- `Item`, `UnitOfMeasure`, conversii
- `Warehouse` — model, fără funcționalitate
- Dimensiuni analitice — model, fără modul de centre de cost

**F0.8 — Parametri fiscali și registru**

Structura de date pentru parametri versionați, cu proveniență. Registrul de selecție după dată efectivă. Fără algoritmi încă.

**F0.9 — Multi-valută**

Model în core: sumă în valută, valuta, curs, sumă în MDL. Integrare BNM pentru curs. Fără reevaluare încă.

**F0.10 — Convenții API și schelet frontend**

Structura de rutare, contextul de tenant din subdomeniu, gestionarea erorilor, autentificare, layout de bază.

#### Criteriu de ieșire din F0

- [ ] Ambele suite de izolare rulează verde în CI, sub rolul de aplicație
- [ ] Se pot crea doi tenanți, o firmă și un engagement, iar accesul se comportă corect în toate cele patru combinații (membru, engagement activ, engagement revocat, niciunul)
- [ ] Un task Celery fără context explicit eșuează, nu returnează date
- [ ] Gardianul de model eșuează dacă se adaugă o tabelă fără `tenant_id`
- [ ] Modelul de volum de date este livrat (necesar pentru decizia de partiționare)

---

### FAZA 1 — Accounting Core

**Obiectiv:** Evidenta produce o balanță de verificare corectă, verificabilă la leu contra unei balanțe 1C reale.

**F1.1 — Plan de conturi SNC**

Template versionat global → instanță per companie. Conturi de sistem vs. subconturi create de companie. `valid_from` / `valid_to`. Mecanism de propagare a modificărilor legislative. *(Politica de propagare rămâne decizie deschisă — vezi Spec B.)*

**F1.2 — Ledger**

`JournalEntry`, `JournalLine` cu dimensiuni analitice. Constrângere de echilibru la nivel de bază de date. Append-only, fără FK-uri intrând.

**F1.3 — Accounting Events**

Stratul între modulele business și ledger. Idempotență pe eveniment. Lineage complet.

**F1.4 — Posting Engine**

Rezoluție de reguli: condiții, șabloane, rezoluție de cont, taxe, dimensiuni, valută, date efective. **Profilul de capabilități ca input.**

**F1.5 — Perioade și închidere**

Stări de perioadă, blocare, redeschidere cu permisiune specială și urmă în audit. Refuz la nivel de motor.

**F1.6 — Logică fiscală, primul strat**

Registrul de algoritmi, cu selecție după dată efectivă. Primele implementări.

**F1.7 — Note contabile manuale și solduri inițiale**

Solduri inițiale pentru: GL, clienți, furnizori, stocuri, active, angajați (cumulative anuale).

**F1.8 — Rapoarte contabile**

Balanță de verificare, Cartea Mare, fișa contului, jurnale, rulaje. Drill-down complet până la documentul sursă.

**F1.9 — Importator 1C, fundament**

Conector, extragere plan de conturi, parteneri, solduri.

**F1.10 — Corpus de regresie fiscală**

Cazuri reale anonimizate cu rezultat cunoscut. Rulat la fiecare modificare de parametru sau algoritm.

#### Criteriu de ieșire din F1

- [ ] Balanță de verificare corectă pe date reale importate din 1C
- [ ] Diferență zero la reconciliere
- [ ] Storno și reînregistrare funcționează, cu lineage coerent
- [ ] Postarea într-o perioadă închisă este refuzată
- [ ] Corpusul de regresie rulează în CI

---

### FAZA 2 — Primul produs vandabil

**Obiectiv:** o companie de servicii cu angajați poate abandona complet 1C. Primul release comercial.

**Organizare: două fluxuri paralele** după stabilizarea F1.

```
Flux A — Commercial / Tax          Flux B — Payroll
─────────────────────────          ────────────────────────
Sales                              Employees
Purchases                          Employment contracts
Receivables / Payables             Salary calculation
Banking / Cash                     CNAS / CNAM / IPC
Fixed Assets                       Leave / sick leave
VAT + registers                    Payroll runs
e-Factura / SFS                    Parallel run
        │                                  │
        └──────────────┬───────────────────┘
                       ↓
              Statutory Reporting
       SFS · CNAS · CNAM · BNS · situații SNC
```

Ambele fluxuri consumă parametri fiscali și emit evenimente contabile. Niciunul nu scrie în ledger.

**Elemente care nu se pot omite din F2:**
- Pachetul complet de raportare statutară — nu „basic"
- Rularea payroll în paralel ca funcție livrată, cu raport de diferențe la ban
- Compliance Admin ca instrument intern operațional

#### Criteriu de ieșire din F2

- [ ] O companie reală de servicii funcționează exclusiv pe Evidenta timp de un trimestru
- [ ] Toate rapoartele lunare și trimestriale depuse din Evidenta, acceptate de instituții
- [ ] Rulare payroll în paralel cu diferență zero pe cel puțin trei companii-pilot

---

### FAZA 3 — Workspace contabil și migrare

**Obiectiv:** o firmă de contabilitate poate muta întregul portofoliu.

- Ciclu complet de Engagement: invitație, acceptare, scope, suspendare, revocare, transfer
- Read models pentru dashboard transversal *(singurul loc din sistem unde interogarea cross-tenant e permisă)*
- Calendar de termene per client
- Operațiuni în masă
- Facturare wholesale și directă
- 1C Migration Center productizat: wizard, mapare, validare, reconciliere la zero diferență

---

### FAZA 4 — Comerț și stocuri

- Inventory ledger, mișcări, evaluare FIFO și cost mediu ponderat
- Politică de evaluare per categorie, cu implicit la nivel de companie
- Loturi, numere de serie, inventariere
- Import, vamă, landed cost
- Comenzi de vânzare și achiziție, liste de prețuri

**Atenție la activare:** activarea Inventory pentru o companie existentă cere solduri inițiale cantitate + cost, metodă de evaluare și dată de cutover. Ledgerul e append-only — istoricul nu devine retroactiv stoc.

---

### FAZA 5 — ERP operațional

HR separat de payroll. CRM peste același Partner. Contracte. Workflow și aprobări ca platform capability. Contabilitate de gestiune. API public.

---

### Dincolo de F5 — direcție, neangajat

Producție, MRP, calitate, retail, POS, WMS, procurement avansat, logistică, contabilitate de proiect, bugetare, BI avansat, AI.

Se proiectează pentru compatibilitate. **Nu se promit comercial.** Ordinea reală se decide din cererea pieței după F3.

---

## 7. Definition of Done

O sarcină nu este terminată până când toate punctele de mai jos sunt adevărate:

- [ ] Codul respectă toți invarianții din secțiunea 1
- [ ] `tenancy-guard` raportează zero CRITICAL
- [ ] `schema-reviewer` raportează zero CRITICAL (dacă există migrații)
- [ ] `accounting-reviewer` raportează zero CRITICAL (dacă există efect financiar)
- [ ] `fiscal-reviewer` raportează zero CRITICAL (dacă atinge conformitatea)
- [ ] Ambele suite de izolare rulează verde
- [ ] Există teste de integrare pentru fiecare efect financiar, cu lanțul complet verificat
- [ ] Există test de idempotență pentru fiecare operațiune retriabilă
- [ ] Nicio decizie deschisă nu a fost închisă tacit în cod — dacă a apărut una, se documentează în `docs/decisions/`

---

## 8. Ce nu se face — conținut pentru CLAUDE.md

- Nu se creează app-uri Django goale pentru faze viitoare
- Nu se scriu module din F2+ înainte de criteriul de ieșire din faza curentă
- Nu se implementează CRM, producție, MRP, WMS sau POS. Nu sunt în scop.
- Nu se folosesc signals Django pentru logică financiară
- Nu se adaugă managere de model care filtrează pe tenant
- Nu se scrie `if year >= X` în logică fiscală
- Nu se adaugă chei străine către tabelele append-only de volum mare
- Nu se face `UPDATE` pe date contabile postate
- Nu se creează endpoint-uri care ocolesc Posting Engine
- Nu se pornesc microservicii
- Nu se rulează teste de izolare sub superuser sau owner de tabelă
- Nu se adaptează un test ca să treacă peste un bug din codul de producție

---

## 9. Ce lipsește încă

Acest document este scheletul. Două specificații trebuie scrise înainte ca F0 să poată începe efectiv:

**Spec A — Identitate, tenancy, engagement, billing, release.** Entități cu câmpuri, politici RLS în formă aproape-SQL, cazurile de test de izolare enumerate, constrângerile de schemă, ciclul de viață al Engagement-ului, căile privilegiate enumerate limitativ, restaurare/export/offboarding/retenție.

**Spec B — Accounting core.** Structura ledgerului, planul de conturi SNC ca date versionate cu politica de propagare, dimensiunile, maparea document → postare condiționată de capabilități, motorul de reguli fiscale, perioadele, multi-valuta, soldurile inițiale.

Fără Spec A, sarcinile F0.3–F0.7 nu au suficient detaliu pentru implementare. Restul documentului este utilizabil imediat: rolurile de bază de date, suitele de verificare, definițiile de agenți și `CLAUDE.md` pot fi puse în repo astăzi.
