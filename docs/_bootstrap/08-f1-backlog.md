# 08 — Backlog F1: Accounting Core

- **Data:** 2026-08-25
- **Sursa ordinii:** `_input/evidenta-implementation-spec.md` §6.2 (F1.1 → F1.10). Ordinea de
  referință se păstrează; unde se abate, se spune de ce.
- **Obiectivul fazei:** Evidenta produce o balanță de verificare corectă, **verificabilă la leu**
  contra unei balanțe 1C reale.
- **Regula de dimensionare:** o sarcină care atinge mai mult de un modul, sau care nu poate fi
  verificată printr-un criteriu clar, este prea mare. Fiecare sarcină de mai jos încape într-o
  sesiune.

## Cum se citește o sarcină

Aceeași formă ca la F0 — `Obiectiv`, `Fișiere`, `Depinde de`, `Review`, `Terminat`, `Blocat de` —
plus **Definition of Done**, care se aplică peste criteriul propriu: zero CRITICAL de la agenții
invocați, suitele verzi, nicio decizie deschisă închisă tacit.

Un lucru s-a schimbat față de F0, și e învățat acolo: **lista de blocaje se curăță.** La F0 s-au
găsit într-o singură zi trei sarcini blocate de decizii închise de zile, plus două decizii luate de
proprietar și neconsemnate deloc. Deriva merge într-o singură direcție — registrul se actualizează,
backlogul nu — iar o listă de blocaje pe care nimeni n-o curăță încetează să fie o listă de blocaje
și devine un motiv de a nu începe. §12 de mai jos e tabelul care se verifică, nu se citește.

## Ce s-a schimbat față de F0, ca metodă

**Schema F1 e fixată de patru ADR-uri, nu de acest document.** [ADR-036](../decisions/036-forma-postarii.md)
(forma postării), [ADR-038](../decisions/038-vocabularul-de-evenimente.md) (`event_type`),
[ADR-039](../decisions/039-valuta-si-perioade.md) (valută și perioade),
[ADR-029](../decisions/029-dimensiuni-analitice.md) (dimensiuni). Backlogul le implementează; nu le
redeschide. Unde o sarcină pare să ceară altceva, ADR-ul câștigă și sarcina se corectează.

---

## F1.1 — Planul de conturi SNC

### F1.1.1 — Șablonul global, versionat

- **Obiectiv:** planul de conturi există ca **date versionate**, nu ca fixture copiat o dată.
- **Fișiere:** `backend/evidenta/accounting/coa/models.py`, migrații, politici
- **Depinde de:** —
- **Review:** `schema-reviewer`, `tenancy-guard`, `fiscal-reviewer`
- **Terminat:** `coa_template` și `coa_template_account` există ca tabele globale, în lista de
  excepții; `UNIQUE (code, version)`; neîntrepătrundere pe `(code, daterange)` pentru versiunile
  `published`; scrierea **retrasă explicit** de la rolul aplicației. **Niciun cont încărcat.**
- **Blocat de:** — *(structura; **conținutul** e `OD-23` — niciun cod de cont nu intră fără
  trimitere la Planul general de conturi și la ordinul care îl aprobă)*

> **Două corecturi față de forma inițială, găsite la implementarea F1.1** *(sesiunea care a livrat
> planul de conturi; consemnate aici de sesiunea care ține registrul)*. **(1)** Conținutul planului
> este `OD-23`, nu `OD-22` — `OD-22` sunt valorile fiscale: cote, plafoane, scutiri. **(2)** „Scriere
> doar prin calea privilegiată `P-4`" **nu se putea îndeplini**: `P-4` este „aplicarea regulilor
> fiscale noi — inserează parametri fiscali și versiuni de logică", iar planul de conturi e act
> normativ contabil, nu parametru fiscal. Nicio cale din enumerarea Spec A §6.2 nu acoperă
> publicarea unei versiuni de plan de conturi — de aceea `OD-56`, deschisă la implementare. Livrat
> cu `GRANT SELECT` plus `REVOKE INSERT, UPDATE, DELETE`, care e starea corectă până când calea
> există.

### F1.1.2 — Instanța per companie

- **Obiectiv:** planul unei companii este „versiune de șablon + strat de suprascriere", nu copie.
- **Fișiere:** `backend/evidenta/accounting/coa/`, migrații, politici
- **Depinde de:** F1.1.1
- **Review:** `schema-reviewer`, `tenancy-guard`
- **Terminat:** `company_chart` și `company_account`, tenant-scoped, îngustate pe companie;
  conturile au `valid_from`/`valid_to` și **nu se șterg niciodată**; un cont de sistem nu poate fi
  modificat de tenant, iar unul propriu poate. Granița e cea din normă, nu inventată:
  [ADR-036](../decisions/036-forma-postarii.md) §6.3 — gradul I din clasele 1–7 e obligatoriu,
  restul e recomandare.
- **Blocat de:** — *(`DNB-03`, propagarea legislativă, **nu blochează F1**: apare abia când există
  tenanți în producție și se schimbă legea — ADR-036 §13)*

### F1.1.3 — `required_dimensions` pe cont

- **Obiectiv:** obligativitatea dimensiunilor se impune de motor, pe cont.
- **Depinde de:** F1.1.2
- **Terminat:** `company_account.required_dimensions` există; postarea într-un cont care cere o
  dimensiune fără ea este refuzată **de motor**, nu de interfață. Este mecanismul pe care
  [ADR-029](../decisions/029-dimensiuni-analitice.md) l-a apărat respingând varianta `jsonb`.
- **Blocat de:** —

---

## F1.2 — Ledgerul

### F1.2.1 — `journal_entry` și `journal_line`

- **Obiectiv:** registrul există, append-only, cu echilibrul impus în bază.
- **Fișiere:** `backend/evidenta/accounting/ledger/models.py`, migrații, politici
- **Depinde de:** F1.1.2, **F1.3.1** *(`accounting_event_id NOT NULL`)*, **F1.5.1**
  *(`period_id NOT NULL`)*
- **Review:** `schema-reviewer`, `accounting-reviewer`, `tenancy-guard`
- **Terminat:** `debit` și `credit` separate, `NOT NULL DEFAULT 0`, cu
  `CHECK ((debit = 0) <> (credit = 0))`; `Σ debit = Σ credit` prin trigger de constrângere amânată
  (`R11`); `accounting_date NOT NULL` ca **cheie de partiționare** ([ADR-032](../decisions/032-cheia-de-partitionare.md));
  fără chei străine **intrând** (`R21`); `bigint` ca PK (`C6`); indecșii încep cu
  `(tenant_id, company_id, accounting_date)`.
- **Blocat de:** —

### F1.2.2 — Cele trei date și cele patru câmpuri de valută

- **Obiectiv:** linia poartă din prima zi ce nu se mai poate adăuga ieftin într-un registru imutabil.
- **Depinde de:** F1.2.1
- **Terminat:** `accounting_date`, `document_date` și `rate_date` există, primele două indexate;
  `currency`, `amount_currency`, `exchange_rate` obligatorii, cu `exchange_rate = 1` pentru moneda
  funcțională. Soldul unui cont se calculează **atât în MDL, cât și în moneda originală**.
  Vezi [ADR-039](../decisions/039-valuta-si-perioade.md) §3, §9.
- **Blocat de:** —

### F1.2.3 — Dimensiunile analitice

- **Obiectiv:** lista închisă plus cele cinci sloturi generice.
- **Depinde de:** F1.2.1
- **Terminat:** cele zece coloane din Spec B §1.7 plus `dim_1_id` … `dim_5_id`; `company_dimension`
  leagă slotul de semnificația lui per companie, cu `UNIQUE (company_id, slot)` și
  `UNIQUE (company_id, name)`. **Cinci, nu „un plafon din modelul de volum"** —
  [ADR-029](../decisions/029-dimensiuni-analitice.md).
- **Blocat de:** —

### F1.2.4 — Storno

- **Obiectiv:** corecția se face prin storno și reînregistrare, niciodată prin `UPDATE`.
- **Depinde de:** F1.2.1, F1.3.1
- **Review:** `accounting-reviewer`
- **Terminat:** o înregistrare de storno are **două legături** — spre documentul sursă și spre
  înregistrarea anulată (`R14`); niciun `UPDATE` pe linii postate este posibil, verificat prin test
  care încearcă și eșuează (`R10`).
- **Blocat de:** —

---

## F1.3 — Evenimentele contabile

### F1.3.1 — `accounting_event` și idempotența — **TERMINAT** (2026-08-25)

- **Obiectiv:** stratul dintre modulele business și ledger, idempotent pe eveniment.
- **Fișiere:** `backend/evidenta/accounting/events/`, migrații, politici
- **Depinde de:** — *(doar tenant și companie; Spec B §1.1)*
- **Review:** `accounting-reviewer`, `schema-reviewer`
- **Terminat:** `UNIQUE (company_id, idempotency_key)` — inima lui `R19`; aceeași cheie cu același
  payload întoarce rezultatul primei execuții fără efect nou; **aceeași cheie cu payload diferit
  este eroare cu cod stabil**, fiindcă acela e cazul care semnalează un bug la apelant, iar tăcerea
  l-ar ascunde.
- **Blocat de:** — *(`DNB-10`, fereastra de reutilizare a cheii **din API**, nu blochează: pe
  eveniment unicitatea e permanentă)*
- **Livrat:** unicitatea e **per companie**, nu globală — două companii ale unui tenant pot folosi
  legitim aceeași cheie, fiind seturi de registre separate. Amprenta payloadului se ia cu
  `sort_keys`, fiindcă ordinea cheilor JSON nu e semantică și o reordonare inofensivă ar fi
  raportată apelantului drept bug al lui. Evenimentul postat e imutabil prin trigger, cu o singură
  tranziție rămasă deschisă — `superseded`, și doar a stării: un eveniment înlocuit rămâne, fiindcă
  rămâne și registrul pe care l-a produs.

### F1.3.2 — Registrul de `event_type` — **TERMINAT** (2026-08-25)

- **Obiectiv:** vocabularul e închis și fiecare tip are handler.
- **Depinde de:** F1.3.1
- **Terminat:** modulele **își înregistrează** tipurile — direcția inversă, deci `D2` nu e atinsă;
  validarea rulează **în CI și la pornirea proceselor care servesc, nu în `AppConfig.ready()`**,
  unde ar cădea și `migrate`; intervalele de valabilitate ale handlerelor unui tip nu se suprapun și
  nu lasă goluri. Vezi [ADR-038](../decisions/038-vocabularul-de-evenimente.md) §3–§5.
- **Blocat de:** —
- **Livrat:** verificarea rulează în `config/wsgi.py` și la configurarea Celery, **nu** în
  `AppConfig.ready()`. Golul dintre două handlere e raportat separat de suprapunere, fiindcă e mai
  rău: suprapunerea refuză la postare, în fața cuiva; golul e tăcut până cade un document în el,
  poate ani după ce s-a scris înregistrarea. Registrul e gol azi — un vocabular gol e servibil, iar
  testul e cel care va refuza prima înregistrare fără handler, la F1.4.4.

### F1.3.4 — Ciclul de viață al evenimentului și coada de repostare — **TERMINAT** (2026-08-25)

- **Obiectiv:** un eveniment care n-a putut fi postat este muncă pe care cineva o poate termina.
- **Depinde de:** F1.3.1
- **Terminat:** matrice de tranziții ca **date**, nu lanț de `if`-uri; `failed` **nu e terminal** —
  cauza obișnuită e un handler lipsă sau un rol de cont nelegat, iar amândouă se închid printr-un
  deployment, nu prin re-emitere din modulul sursă (re-emiterea s-ar ciocni de propria cheie de
  idempotență). Coada se ordonează după `accounting_date`, nu după data creării: un document
  întârziat pentru o perioadă anterioară se postează înaintea unuia mai nou, altfel perioada se
  poate închide peste un gol.
- **Blocat de:** —

> **Sarcină apărută la implementare, nu în descompunere.** Commitul care lega emiterea de registru
> descria comportamentul cozii — `status = 'failed'` cu `posting_error`, „operatorul are o coadă din
> care să lucreze" — iar nimic nu-l implementa. Un docstring care descrie o coadă inexistentă e o
> promisiune, nu documentație.

### F1.3.3 — Lineage complet

- **Obiectiv:** `R13` navigabil în ambele sensuri.
- **Depinde de:** F1.3.1, F1.2.1
- **Review:** `accounting-reviewer`
- **Terminat:** un test parcurge lanțul `Journal Line → Journal Entry → Accounting Event → Source
  Document → Sursă` și înapoi, cu sume și conturi.
- **Blocat de:** —

---

## F1.4 — Posting Engine

### F1.4.1 — Rezoluția regulilor

- **Obiectiv:** un eveniment produce exact o postare, sau eșuează zgomotos.
- **Fișiere:** `backend/evidenta/accounting/posting/`
- **Depinde de:** F1.3.2, F1.1.3
- **Review:** `accounting-reviewer`, `fiscal-reviewer`
- **Terminat:** selecția e `event_type + accounting_date ∈ [valid_from, valid_to)`, filtrată pe
  condiții și **pe profilul de capabilități** — `R26` cere ca acesta să fie **input explicit**, nu
  o citire laterală; **zero sau ≥2 reguli este eroare**, niciodată alegere implicită.
- **Blocat de:** —

### F1.4.2 — Rolurile de cont și legarea

- **Obiectiv:** handlerele referă sloturi semantice, nu conturi.
- **Depinde de:** F1.4.1, F1.1.2
- **Terminat:** un rol nelegat este **eroare la postare**, nu postare pe un cont de rezervă;
  legarea are `valid_from`/`valid_to` și nu afectează postările existente. Granița din
  [ADR-036](../decisions/036-forma-postarii.md) §5.1 e respectată: maparea **impusă de lege** stă în
  `fiscal_parameter`, global; subcontul propriu al tenantului e configurare.
- **Blocat de:** **`OD-55`** — mulțimea cheilor de context la legarea condiționată rol → cont.
  Registrul o dă cu termen „înainte de F1.4", iar diferența nu e cosmetică: chei definibile de
  client înseamnă un evaluator de expresii peste `payload`, adică chiar DSL-ul respins ca opțiunea 1
  în ADR-036 §2. **Forma tabelei de legare depinde de răspuns.** Și, peste asta,
  [ADR-036](../decisions/036-forma-postarii.md) este `Propus`: §6.1 — rolurile de cont — *este*
  conținutul acestei sarcini, iar cazurile `C1`–`C5` din §11 cer confirmare contabilă.

> **`Blocat de: —` era greșit, și e clasa inversă celei curățate în §12.** Nu un blocaj expirat, ci
> unul **nescris**: registrul îl avea, backlogul nu. Cine ar fi luat sarcina citind doar backlogul ar
> fi construit tabela de legare înainte să se știe ce formă are. Găsit de sesiunea care a livrat
> F1.4.1, când s-a oprit înainte s-o continue.

### F1.4.3 — Cei șase invarianți

- **Obiectiv:** motorul refuză, nu handlerul.
- **Depinde de:** F1.4.1
- **Terminat:** toți șase din [ADR-036](../decisions/036-forma-postarii.md) §5 sunt verificați de
  motor, fiecare cu un test care îl încalcă deliberat și vede refuzul.
- **Blocat de:** —

### F1.4.4 — Primele handlere

- **Obiectiv:** tratamentele concrete.
- **Depinde de:** F1.4.3
- **Review:** `accounting-reviewer`, `fiscal-reviewer`
- **Terminat:** fiecare handler are teste proprii și interval de valabilitate.
- **Blocat de:** **cazurile `C1`–`C5` din [ADR-036](../decisions/036-forma-postarii.md) §11** —
  metoda de cost la ieșire, amortizarea, cheltuielile de transport-aprovizionare, diferențele de
  curs, repartizarea indirectelor. Cer lista permisă de SNC, **citată**, nu dedusă.
  **Citarea există de la `3c3fccc` (2026-08-26)** —
  [`_input/cercetare/c1-c3-c5-stocuri.md`](../_input/cercetare/c1-c3-c5-stocuri.md),
  [`c2-amortizarea.md`](../_input/cercetare/c2-amortizarea.md),
  [`c4-diferente-de-curs.md`](../_input/cercetare/c4-diferente-de-curs.md). Ce lipsește nu mai e
  lectura standardului, ci **clasificarea** din §11, care e a proprietarului.

---

## F1.5 — Perioade și închidere

### F1.5.1 — Perioada contabilă

- **Obiectiv:** stările și refuzul la nivel de motor.
- **Depinde de:** — *(nu F1.2.1: `journal_entry.period_id` arată spre `period`, deci ordinea e
  inversă — vezi nota de la F1.2.1)*
- **Terminat:** `open` / `closed` / `locked`, cu redeschidere posibilă doar cât exercițiul e deschis,
  cu motivare și urmă în audit; după `locked`, niciodată. **Postarea într-o perioadă închisă e
  refuzată de motor, nu de interfață** (`R12`).
- **Blocat de:** —

> **Livrat parțial la 2026-08-25, și partea care lipsește e numită.** Tabelele, stările, cele trei
> tranziții, refuzul de a ieși din `locked` — și în serviciu, și prin trigger — plus auditul cu
> motivarea redeschiderii: **25 de teste sub rolul de aplicație**. Ce **nu** se poate demonstra încă
> este chiar jumătatea din criteriu care spune „de motor": nu există motor. În locul ei s-a livrat
> primitiva pe care motorul o va apela — `assert_postable(company_id, accounting_date)`, care
> întoarce perioada sau refuză cu `periods.period_not_open` / `periods.period_locked`. A doua
> barieră din Spec B §6.3, triggerul `BEFORE INSERT` pe `journal_entry`, aparține lui **F1.2.1**,
> unde se creează tabela pe care stă. Până atunci refuzul se poate ocoli printr-un `INSERT` direct.
>
> Deschis pe drum: **`OD-58`** (a patra stare, `closing`, pe care Spec B §6.1 o listează și ADR-039
> §8 nu) și **`OD-57`** (clauza de îngustare pe companie din ADR-004, prezentă în patru politici din
> unsprezece). `DNB-07` **rămâne deschisă**: nu există `period_module_lock` și nici coloană de
> modul, deci nici varianta (B) nu e închisă tacit — dar comportamentul de azi *este* varianta (A),
> iar asta e spus în modul, nu lăsat să fie descoperit.

### F1.5.2 — Exercițiul fiscal — **livrat 2026-08-25**

- **Obiectiv:** `start_date`/`end_date` explicite, implicit calendaristic.
- **Depinde de:** F1.5.1 *(livrat împreună: exercițiul generează perioadele, deci nimeni nu tastează
  o lună și presupunerea calendaristică nu are pe unde intra)*
- **Terminat:** presupunerea „douăsprezece luni, ianuarie–decembrie" **nu apare nicăieri** în
  închidere, agregare sau raportare — verificat prin test cu un exercițiu aprilie–martie, care este
  cazul normal pentru subsidiarele cu proprietar străin (art. 24 alin. (1) lit. b).
- **Blocat de:** —

### F1.5.3 — Perioada fiscală TVA, distinctă

- **Obiectiv:** perioada contabilă și cea fiscală sunt două concepte.
- **Depinde de:** F1.5.1
- **Terminat:** un test acoperă cazul anulării înregistrării, unde perioada fiscală TVA **depășește
  o lună calendaristică** (art. 114 alin. (2)). În 99% din cazuri coincid — testul e pentru restul.
- **Blocat de:** —

### F1.5.4 — Închiderea

- **Obiectiv:** două `event_type`, cu clasa 8 ca invariant.
- **Depinde de:** F1.5.2, F1.4.1
- **Review:** `accounting-reviewer`
- **Terminat:** `period.month.closed` blochează și **validează invariantul clasei 8** (sold zero la
  data raportării); `period.year.closed` postează lanțul de închidere a conturilor de rezultate.
  Închiderea produce **postări normale, prin motor** (`R9`).
- **Blocat de:** **`OD-22`** — conturile concrete din lanț sunt **mapări de conturi**, deci parametri
  fiscali (`R15`): se încarcă din `fiscal_parameter` cu act normativ, nu se scriu în handler. Un
  număr de cont scris din memorie în codul care produce rezultatul anului este un rezultat pe care
  nimeni nu-l poate apăra la un control.

---

## F1.6 — Logica fiscală, primul strat

- **Obiectiv:** registrul de algoritmi are primele implementări reale.
- **Depinde de:** F1.4.1
- **Review:** `fiscal-reviewer`
- **Terminat:** cel puțin un algoritm real e selectat după data efectivă a perioadei și trece
  corpusul de regresie. Registrul însuși **există din F0.8**; ce lipsește sunt implementările.
- **Blocat de:** **`OD-22`** *(valorile)* și **`DNB-08`** *(rotunjirea —
  [ADR-037](../decisions/037-conventii-de-platforma.md))*.

  **`DNB-08` NU e blocată pe ghidul de integrare SFS.** Rândul de mai sus spunea asta și contrazicea
  ADR-ul propriu: [ADR-037](../decisions/037-conventii-de-platforma.md) §5 constată explicit că
  `DNB-08` *fusese înregistrată* pe `OD-24` și că doar `V2` — schema XML e-Factura — depinde de acel
  acces; `V1` (Ordinul MF nr. 118 din 28.08.2017, Anexele 1 și 1a) și `V3` (Codul fiscal) sunt
  documente publice. Corectat 2026-08-28.

  **Structura e decisă și implementată** (2026-08-28, decizia proprietarului): *linia este
  autoritativă — TVA se calculează și se rotunjește pe fiecare linie, iar totalul documentului e suma
  liniilor, niciodată o recalculare pe bază de total.* În acest model diferența de rotunjire din
  ADR-037 §3.1 nu poate exista: nu există două calcule concurente. Cod:
  `accounting.currency.services.amounts.line_amounts`.

  **Ce mai blochează, măsurat:**
  1. **`V1`** — precizia prescrisă pe formular. Ipoteza de lucru: patru zecimale la prețul unitar,
     două la sume. Textul consolidat al Instrucțiunii nu s-a putut citi de aici (`legis.md` 403,
     `sfs.md` 403, `contabilsef.md` cu abonament); din surse primare s-a obținut doar identitatea
     actului — **MO 2017, nr. 340-351, art. 1750**, citat verbatim într-un document al MF.
  2. **`OD-67`** — *nou pe acest drum*: `fiscal_parameter` are politică doar de **citire**
     (`0027_fiscal.up.sql`), deci precizia nu se poate încărca pe nicio cale în afară de superuser.
     Mecanismul e complet și inert până când `P-4` există. Aceeași familie ca `0044`, care a trebuit
     să adauge o politică de scriere pentru planul de conturi.

  `accounting.money_rounding` are acum **două implementări** în cod — `half_up` și `half_even` — și
  **niciun rând** în `fiscal_logic_version`. Prezența amândurora nu e o alegere între ele: alegerea e
  rândul din registru, după dată. `convert()` refuză în continuare — starea corectă, afirmată printr-un
  test din F0.9.

---

## F1.7 — Note contabile manuale și solduri inițiale

### F1.7.1 — Nota manuală

- **Obiectiv:** chiar și o notă manuală trece prin motor.
- **Depinde de:** F1.4.3
- **Terminat:** tipul e `manual.journal_entry`; motorul validează echilibrul, conturile, perioada
  deschisă și dimensiunile obligatorii, apoi postează **fără să derive** liniile. Nu există a doua
  cale către ledger.
- **Blocat de:** —

### F1.7.2 — Soldurile inițiale

- **Obiectiv:** șase seturi de linii, câte unul per domeniu.
- **Depinde de:** F1.7.1, F1.5.1
- **Review:** `accounting-reviewer`
- **Terminat:** GL, clienți, furnizori, stocuri, active, angajați; `opening.balance.posted` într-o
  perioadă de deschidere; **perioada de start rămâne ireversibilă** ([ADR-039](../decisions/039-valuta-si-perioade.md) §11),
  iar alegerea ei trece prin `P-9` și Spec A §12.
- **Blocat de:** —

### F1.7.3 — Șabloanele de operațiuni tipice

- **Obiectiv:** absorb presiunea de personalizare, fără divergență semantică.
- **Depinde de:** F1.7.1
- **Terminat:** produc `manual.journal_entry`, **nu tipuri proprii**, și nu pot fi folosite pentru
  postarea automată a documentelor ([ADR-036](../decisions/036-forma-postarii.md) §8).
- **Blocat de:** —

---

## F1.8 — Rapoartele contabile

- **Obiectiv:** balanță de verificare, Cartea Mare, fișa contului, jurnale, rulaje, cu drill-down
  complet.
- **Depinde de:** F1.2.2, F1.5.1, **F1.G1**
- **Review:** `accounting-reviewer`
- **Terminat:** balanța se reconciliază **la leu** contra extrasului 1C; **totalurile vin de la
  server** (`C19`) — niciun total calculat în client peste un set virtualizat; exporturile se
  generează server-side, din aceeași sursă ca afișarea (`C20`); drill-down până la documentul sursă.
- **Blocat de:** `OD-29` *(țintele de performanță — modelul de volum există din F0.11, deci decizia
  e deblocată, nu luată)*, `OD-35` *(scara de densitate; `C21` e activă, iar acesta e primul ecran cu
  grilă)*

---

## F1.9 — Importatorul 1C, fundament

- **Obiectiv:** conector, extragere plan de conturi, parteneri, solduri.
- **Depinde de:** F1.1.2, F1.7.2
- **Review:** `accounting-reviewer`
- **Terminat:** liniile importate sunt **vizibil distincte** în registru; suma din sursă e
  autoritativă și nu se recalculează, dar cei șase invarianți se verifică la fel — un import care nu
  echilibrează e refuzat, ceea ce e chiar verificarea utilă la migrare
  ([ADR-038](../decisions/038-vocabularul-de-evenimente.md) §7.3).
- **Blocat de:** **`OD-28`** *(ce versiuni 1C, prin ce metodă de extragere)*

---

## F1.10 — Corpusul de regresie fiscală

- **Obiectiv:** cazuri reale, anonimizate, cu rezultat cunoscut.
- **Depinde de:** F1.6
- **Review:** `fiscal-reviewer`
- **Terminat:** rulează în CI la fiecare modificare de parametru sau algoritm (`C14`).
- **Blocat de:** **contabilul practicant** — cazurile cu rezultat verificat nu se pot fabrica. Este
  singura măsură de risc contabil rămasă după [ADR-010](../decisions/010-fara-a-doua-semnatura.md),
  iar F0 s-a încheiat cu ea încă goală.

---

## F1.G1 și F1.G2 — grilele

Rămân descrise în detaliu în `07-f1-grile.md`, care le specifică deja bine. **Nu se copiază aici:**
o a doua copie a aceleiași sarcini diverge de prima, iar F0 a produs destule exemple.

| Sarcină | Poziție în secvență | Blocat de |
|---|---|---|
| **F1.G1** `DataGrid` | după F1.2, înainte de F1.8 | `OD-35`; *`OD-19` închisă prin [ADR-031](../decisions/031-stack-frontend.md)* |
| **F1.G2** `EntryGrid` | după F1.2, înainte de F1.7 | **`OD-36`** — contractul de tastatură se scrie și se aprobă înainte de cod |

`F1.G0` — setul de date 1C — este aceeași precondiție ca `OD-28`.

---

## Ce poate începe acum, în paralel

Patru fire independente. Niciunul nu așteaptă o decizie deschisă:

```
Firul A   F1.1.1 → F1.1.2 → F1.1.3        planul de conturi (structura)
Firul B   F1.3.1 → F1.3.2 → F1.3.3        evenimentele contabile
Firul C   F1.5.1 → F1.5.2 → F1.5.3        perioadele
                    ↓ toate trei
Firul D   F1.2.1 → F1.2.2 → F1.2.3 → F1.2.4    ledgerul
```

> **Corectură, făcută prin citirea schemei, nu prin raționament.** Prima versiune a acestei secțiuni
> spunea că `F1.2.1` e punctul de sincronizare pe care îl așteaptă celelalte fire. **Este exact
> invers.** `journal_entry` are `period_id NOT NULL REFERENCES period` și
> `accounting_event_id NOT NULL REFERENCES accounting_event` (Spec B §1.2), plus `account_id` către
> `company_account` — deci ledgerul le așteaptă pe toate trei. `accounting_event`, în schimb,
> depinde doar de tenant și companie (§1.1), la fel perioada.
>
> Greșeala a durat un commit. Merită păstrată aici fiindcă e chiar clasa de eroare pe care
> descompunerea trebuie s-o prindă: o ordine plauzibilă, dedusă din nume în loc de din coloane.

**Ce nu poate începe, și de ce e util să fie vizibil:** F1.4.4 (handlerele concrete) așteaptă
`C1`–`C5` cu SNC citat; F1.5.4 și F1.6 așteaptă `OD-22`; F1.8 așteaptă `OD-35`; F1.9 și grilele
așteaptă `OD-28`; F1.10 așteaptă cazuri reale. **Cinci din zece sarcini de nivel superior sunt
blocate pe lucruri care nu se rezolvă scriind cod** — patru pe domeniu contabil sau acces extern,
una pe o decizie de produs.

---

## Criteriul de ieșire din F1

- [ ] Balanță de verificare corectă pe date reale importate din 1C
- [ ] Diferență zero la reconciliere
- [ ] Storno și reînregistrare funcționează, cu lineage coerent
- [ ] Postarea într-o perioadă închisă este refuzată
- [ ] Corpusul de regresie rulează în CI

**Trei dintre cele cinci depind de un extras 1C real.** Aceeași dependență externă care a rămas
deschisă toată F0, acum pe drumul critic al criteriului de ieșire.

---

## Tabelul de blocaje — se verifică, nu se citește

| Sarcină | Decizie | Natura |
|---|---|---|
| F1.4.2 | `OD-55`; ADR-036 `Propus` | Arhitectură + domeniu contabil — forma tabelei de legare depinde de amândouă |
| F1.4.4 | `C1`–`C5` din ADR-036 §11 | Domeniu contabil — SNC citat |
| F1.5.4, F1.6 | `OD-22` | Domeniu contabil — Planul general de conturi, ordinul care îl aprobă |
| F1.6 | `DNB-08` → ADR-037 | **Structura: decisă și implementată** (linia e autoritativă). Rămâne `V1` — document **public**, nu ghidul SFS — plus `OD-67`, calea de scriere a parametrilor fiscali |
| F1.8 | `OD-29` | Produs — ~~`OD-35`~~ închisă prin [ADR-042](../decisions/042-scara-de-densitate.md); rămâne ținta numerică de performanță |
| F1.9, F1.G0 | `OD-28` | Extern — acces la o bază 1C reală |
| F1.G2 | `OD-36` | Produs — contractul de tastatură |
| F1.10 | — | Domeniu contabil — cazuri cu rezultat verificat |

Când o decizie se închide, **rândul de aici se taie în același commit**. Regula există fiindcă la
F0 nu a existat.
