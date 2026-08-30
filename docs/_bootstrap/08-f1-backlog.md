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

> **Al doilea strat, 2026-08-29** ([ADR-048](../decisions/048-formula-si-sloturile-tipizate.md)):
> contul declară **ce poartă**, în patru sloturi tipizate (`company_account.slot_n_dimension`, copiate
> din `coa_template_account`), iar `required_dimensions` rămâne ce e **obligatoriu**, ținut în
> interiorul declarației de o constrângere. Cele 15 coloane ale liniei nu se schimbă: slotul spune
> în care dintre ele aterizează o valoare pentru contul acela. **Nicio declarație în CSV-ul planului** —
> care conturi poartă ce e decizia contabilă a proprietarului, și un test asertează că fișierul e gol.

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
- **Blocat de:** — *(deblocată 2026-08-29: `OD-55` închisă prin
  [ADR-051](../decisions/051-chei-de-context-enumerate.md) — cheile enumerate în cod, valorile date;
  forma tabelei e în ADR-051 §3. ADR-036 e `Acceptat`.)*

  *Textul blocajului, păstrat:* `OD-55` — mulțimea cheilor de context la legarea condiționată rol
  → cont; chei definibile de client ar fi însemnat un evaluator de expresii peste `payload`, adică
  chiar DSL-ul respins ca opțiunea 1 în ADR-036 §2. **Forma tabelei de legare depindea de răspuns.**

> **`Blocat de: —` era greșit, și e clasa inversă celei curățate în §12.** Nu un blocaj expirat, ci
> unul **nescris**: registrul îl avea, backlogul nu. Cine ar fi luat sarcina citind doar backlogul ar
> fi construit tabela de legare înainte să se știe ce formă are. Găsit de sesiunea care a livrat
> F1.4.1, când s-a oprit înainte s-o continue.

> **Livrat la 2026-08-29, sub sarcina aceasta, fără să o închidă: rolurile și legarea există**
> (`accounting/slots`, `AccountRoleBinding`, `resolve_role`, 37 de roluri cu subcontul din plan ca
> date), iar **motorul le consumă prin formule** — [ADR-048](../decisions/048-formula-si-sloturile-tipizate.md):
> `posting.formula.bind_roles` transformă o `RoleFormula` în conturi la data postării și refuză un rol
> nelegat cu `slots.role_not_bound`. Ce rămâne deschis din sarcină e exact ce o bloca: legarea
> **condiționată** după cheie de context (`OD-55`) — tabela de legare de azi e necondiționată.

### F1.4.3 — Cei șase invarianți

- **Obiectiv:** motorul refuză, nu handlerul.
- **Depinde de:** F1.4.1
- **Terminat:** toți șase din [ADR-036](../decisions/036-forma-postarii.md) §5 sunt verificați de
  motor, fiecare cu un test care îl încalcă deliberat și vede refuzul.
- **Blocat de:** —

> **Contractul handlerului are formă de la 2026-08-29** ([ADR-048](../decisions/048-formula-si-sloturile-tipizate.md)):
> un handler produce **formule** — *n* per linie de document, nu un număr fixat — fiecare o
> corespondență debit/credit cu sumă în lei și în valută, curs, cotă TVA ca atribut și dimensiuni
> tipizate; motorul plasează dimensiunile după declarația contului, contopește, verifică cei șase
> invarianți peste expansiunea în linii și scrie `journal_formula` lângă `journal_line`, cu cele trei
> versiuni pe antet. **Niciun handler concret nu există** — blocajul de mai jos rămâne intact; ce s-a
> livrat e capacitatea, cu `tests/isolation/test_formulas.py` ca singurul ei consumator.

### F1.4.4 — Primele handlere

- **Obiectiv:** tratamentele concrete.
- **Depinde de:** F1.4.3
- **Review:** `accounting-reviewer`, `fiscal-reviewer`
- **Terminat:** fiecare handler are teste proprii și interval de valabilitate.
- **Blocat de:** — *(deblocată 2026-08-29: clasificarea `C1`–`C5` aprobată de proprietar,
  [ADR-036](../decisions/036-forma-postarii.md) §11, `Acceptat`. Ce rămâne în afara acestei sarcini,
  explicit: amortizarea fiscală — HG 704/2019 neobținută; handlerul de reevaluare — Anexa 1 din SNC
  „Diferențe de curs" neextrasă; cotele reale — `OD-22`.)*

  **Ordinea handlerelor, decisă de proprietar (2026-08-29, după F1.5.4) — mai multe sesiuni, nu una:**

  1. **C4 la decontare — LIVRAT 2026-08-30** ([ADR-057](../decisions/057-diferentele-realizate-la-decontare.md)):
     `Document.rate_term` cu implicitul actului (`payment_date`, pct. 6 și 8), handlerul
     `settlement.differences.v1` pe `receivables.settlement_created` / `payables.settlement_created`,
     discriminatorul refuzat nu presupus, trei perechi ca roluri (patru roluri noi în catalog, 45),
     ramura „zero postări" și avansul ca teste, prima ștampilă de parametru scrisă de un handler.
     Reevaluarea la raportare — nu (Anexa 1). Textul sarcinii, păstrat mai jos.

     Diferențele de curs realizate. Primul fiindcă e singurul dintre cele cinci
     care produce formule pe care **nu le cere nicio linie de document**: diferența apare din
     compararea a două momente, nu dintr-o linie de intrare; dacă motorul poate emite asta, restul
     sunt cazuri mai simple. Ce e fixat deja și se testează, nu se omite: **trei perechi de conturi**
     (6226/7224 curs, 6227/7225 sumă, 6127/7147 ecartul BNM–bancă, în rezultatul operațional), iar
     cursul contractual de pe antet poate face ca diferența să **nu apară deloc** (pct. 21) — ramura
     „zero postări" e un caz de test. Handlerul de **reevaluare** nu intră: Anexa 1 neextrasă.
     **Precondiție, măsurată 2026-08-29 la cererea proprietarului:** antetul documentului
     (`platform/documents/models.py`, `Document`) are `currency` și `exchange_rate` — MDL per unitate,
     input explicit — dar **nu are termenul contractual privind cursul** (pct. 19: la data achitării,
     la data livrării, sau fix, stabilit de părți). Fără el, handlerul nu poate ști dacă la decontare
     apare o diferență sau niciuna (pct. 21). **Se adaugă întâi**, ca migrare aditivă pe antet:
     `rate_term` din vocabularul închis al pct. 19; pentru `fixed` și `delivery_date`, cursul de pe
     antet e cel care rămâne; pentru `payment_date`, diferența se calculează la decontare.
     **Implicitul, decis de proprietar (2026-08-30): „la data achitării"** — nu un implicit tăcut, ci
     regula normei când contractul tace (recalcularea la cursul din ziua achitării, pct. 6 și 8);
     celelalte două sunt stipulații contractuale care se **înscriu** pe antet. Ce mai lipsește pe
     drum: discriminatorul dintre *diferență de curs* și *diferență de sumă* e contrapartea
     (rezident, contract în valută sau unități convenționale — pct. 4, 17), nu formula.
  2. **C5, indirectele — LIVRAT 2026-08-30** ([ADR-058](../decisions/058-repartizarea-costurilor-indirecte.md)):
     regula pct. 30 ca logică versionată (`production.overhead_absorption` → `normal_capacity_v1`,
     selectată la ultima zi a perioadei; fără rând, refuzul e al registrului fiscal), baza pct. 31 ca
     valori pe fapt, nevalidată contra unei liste — bază goală **refuzată**, nu împărțită egal; o
     formulă `Dt 811[item] / Ct 821` per produs, restul constant nerepartizat la 714 (rol nou,
     catalogul la 46); ultima cotă ia restul; sursa `production` în vocabular (`0003`). Rândul de
     logică e `draft` pe baza de dezvoltare — activarea e a proprietarului. Textul sarcinii, păstrat:
     formula de subabsorbție e scrisă în standard (pct. 30), fără ambiguitate; baza de repartizare
     vine din nomenclator, listă deschisă (pct. 31). Validează că o regulă cu calcul propriu
     funcționează cu date deschise.
  3. **C2, amortizarea** — per obiect, lunar, strat 3 pe metodă (pct. 19, 22). Validează strategia
     de calcul al valorii, separată de formă. **Fără partea fiscală** (HG 704/2019).
  4. **C1 ultimul** — cel mai mare: două handlere de moment (permanent / periodic), plus costul
     standard, plus prețul cu amănuntul; și singurul care depinde de un modul de stocuri care nu
     există încă.

  *Textul blocajului, păstrat:* cazurile `C1`–`C5` cereau lista permisă de SNC, **citată**, nu
  dedusă — citarea există de la `3c3fccc` (2026-08-26) în
  [`c1-c3-c5-stocuri.md`](../_input/cercetare/c1-c3-c5-stocuri.md),
  [`c2-amortizarea.md`](../_input/cercetare/c2-amortizarea.md),
  [`c4-diferente-de-curs.md`](../_input/cercetare/c4-diferente-de-curs.md) — și **clasificarea**,
  care era a proprietarului.

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

### F1.5.4 — Închiderea — **LIVRATĂ** (2026-08-29, [ADR-056](../decisions/056-inchiderea-lunii-si-a-exercitiului.md))

- **Obiectiv:** două `event_type`, cu clasa 8 ca invariant.
- **Depinde de:** F1.5.2, F1.4.1
- **Review:** `accounting-reviewer`
- **Terminat:** `period.month.closed` blochează și **validează invariantul clasei 8** (sold zero la
  data raportării); `period.year.closed` postează lanțul de închidere a conturilor de rezultate.
  Închiderea produce **postări normale, prin motor** (`R9`).
  *Îndeplinit: `period.month_closed` și `period.year_closed` sunt în registru (numele cu două
  segmente, forma impusă de Spec B §1.4 — ADR-056 §3.3); luna validează clasa 8 pe primitivă și
  înregistrează evenimentul fără postare; exercițiul postează pașii 1, 3, 4 ai lanțului într-o
  înregistrare `closing`, prin `post_formulas`, cu 731 corespondență proprie, 351 la zero; pasul 5 e
  `OD-73`. Zece teste în `test_closing.py`.*
- **Blocat de:** — *(deblocată 2026-08-29 prin
  [ADR-050](../decisions/050-lantul-de-inchidere-ca-roluri.md): conturile lanțului — 351, 731, 333,
  334, 332 — vin din Planul general de conturi, act propriu, deci sunt **roluri de cont** din
  catalogul ADR-048, nu parametri fiscali; sunt în `roles_snc_2020.csv`. Ordinea lanțului e aprobată
  și obligatorie, în ADR-050 §3.2 — 731 **nu** se închide odată cu restul clasei 7. Cota impozitului
  pe venit din pasul 2 rămâne parametru fiscal, `OD-22`.)*

  *Textul blocajului, păstrat, fiindcă era o definiție greșită și merită văzut ca atare:* „conturile
  concrete din lanț sunt mapări de conturi, deci parametri fiscali (`R15`): se încarcă din
  `fiscal_parameter` cu act normativ". Nu: un cont din Planul general de conturi nu se schimbă
  printr-o modificare de Cod fiscal. Ce rămâne adevărat: un număr de cont scris din memorie în
  handler e un rezultat pe care nimeni nu-l poate apăra la un control — de aceea sunt roluri.

---

## F1.6 — Logica fiscală, primul strat

- **Obiectiv:** registrul de algoritmi are primele implementări reale.
- **Depinde de:** F1.4.1
- **Review:** `fiscal-reviewer`
- **Terminat:** cel puțin un algoritm real e selectat după data efectivă a perioadei și trece
  corpusul de regresie. Registrul însuși **există din F0.8**; ce lipsește sunt implementările.
- **Blocat de:** — **Livrată 2026-08-29** în structură și în valori: rotunjirea e în registru,
  selectată după dată; `accounting.money_rounding` v1 = `half_up` (decizia proprietarului, ADR-037
  §3.3), `amount_scale = 2`, `unit_price_scale = 4` — toate trei **active** pe baza de dezvoltare,
  aprobate cu identitatea proprietarului, `provisional` cu motivul pe rând (formularul tace);
  precizia cantității e a unității (ADR-055). Criteriul de terminare — *trece corpusul de regresie* —
  se închide odată cu F1.10. ~~`V1`~~ citită; ~~`OD-67`~~ ADR-049; ~~`OD-22`~~ F2 (ADR-054).

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
- **Blocat de:** — *(`OD-29` închisă prin [ADR-053](../decisions/053-tinta-de-performanta.md):
  fișa contului agregă implicit pe document, cu drill-down la formule; datele din modelul de volum;
  pragurile propuse, de confirmat. `OD-35` închisă prin ADR-042.)* Rămâne dependența de **F1.G1**.

> **Livrat la 2026-08-30, cu ce rămâne numit.** Fișa contului (un rând per document, corespondența
> din `journal_formula`, soldul curent al serverului), Cartea Mare (pe lunile companiei, rulaje în
> corespondență, restul neexplicat numit), rulajele pe corespondențe (șahul), drill-down-ul
> înregistrării până la sursă (`R13`), toate cu totaluri pe server (`C19`) și export **CSV** pe server
> din același rezultat (`C20`, `C38`). Balanța există din A5 și primește exportul. **Rămân:** jurnalele
> de vânzări/cumpărări — sunt „pe document prin definiție" (ADR-053) și nu au ce lista până nu
> postează un document (F1.4.4 / Etapa 8); exportul Excel/PDF (`OD-74`); **reconcilierea la leu contra
> 1C**, care e criteriul de ieșire și așteaptă extrasul real (F3, ADR-054). Ținta ADR-053 §3.3 pentru
> fișă are prima măsurătoare, la scara implicită: 22,7 ms pe o lună a contului celui mai încărcat din
> 2.000 de documente, prin `journal_line_account_idx` (`tests/volume/test_account_ledger.py`).

---

## ~~F1.9 — Importatorul 1C, fundament~~ → **F3, Migration Center**

*Mutat 2026-08-29 prin [ADR-054](../decisions/054-importul-e-distributie-corpusul-e-intern.md):
instrument de distribuție, nu fundație — nimic din F1 nu-l consumă. Sarcina rămâne scrisă aici ca
istoric; se reia în backlogul F3, lângă `migration/mapping` (F2) și `migration/reconciliation` (F3),
unde spec-ul le pusese de la început.*

- **Obiectiv:** conector, extragere plan de conturi, parteneri, solduri.
- **Depinde de:** F1.1.2, F1.7.2
- **Review:** `accounting-reviewer`
- **Terminat:** liniile importate sunt **vizibil distincte** în registru; suma din sursă e
  autoritativă și nu se recalculează, dar cei șase invarianți se verifică la fel — un import care nu
  echilibrează e refuzat, ceea ce e chiar verificarea utilă la migrare
  ([ADR-038](../decisions/038-vocabularul-de-evenimente.md) §7.3).
- **Blocat de:** **`OD-28`** *(ce versiuni 1C, prin ce metodă de extragere)* — **blochează F3, nu F1.**

---

## F1.10 — Corpusul de regresie

- **Obiectiv:** *circa douăzeci de cazuri construite intern*, fiecare cu documentul, postarea
  așteptată — conturi și sume —, și **citarea** care o susține (SNC, Planul general de conturi,
  ADR-036 §11). Un caz care nu poate cita nu intră. **Ce testează corpusul:** că implementarea
  corespunde actelor citate — nu că înțelegerea corespunde practicii. Un caz greșit e un caz cu
  citare greșită, ceea ce se vede.
- **Depinde de:** F1.4.4 (primele handlere), F1.5.4 (lanțul de închidere — cel puțin un caz de
  închidere de lună fără nicio linie pe 351 și unul de închidere de an cu lanțul din ADR-050 §3.2)
- **Review:** `fiscal-reviewer`, `accounting-reviewer`
- **Terminat:** rulează în CI la fiecare modificare de parametru sau algoritm (`C14`); balanța,
  Cartea Mare și fișa contului dau același răspuns pe fiecare caz (criteriul de ieșire, punctele 1–2).
  **Livrată 2026-08-30** (sesiunea `evidenta-04`): `backend/tests/corpus/` — 33 de cazuri în șase
  module (C5 pe SNC „Stocuri" Anexa 1, C4 pe Exemplele 1, 2, 5 din SNC „Diferenţe de curs", închiderea
  pe Exemplul 7 din SNC „Capital propriu", nota manuală și stornoul pe Exemplul 8 din SNC „Venituri",
  soldurile inițiale pe normele de sold ale Planului), fiecare cu citarea sa transcrisă în
  [`f1-10-corpus-citari.md`](../_input/cercetare/f1-10-corpus-citari.md) și verificată mecanic de
  `test_corpus_integrity.py`; `agree(book)` la sfârșitul fiecărui caz reconciliază balanța, fișa
  contului, Cartea Mare și șahul; convențiile se citesc din fișierele de parametri livrate; cele două
  valori `regression_case_set` arată acum spre seturi cu cazuri; convențiile intră prin
  `load_fiscal_parameters` și `activate_fiscal_parameters`, nu prin SQL de fixture. Review:
  `fiscal-reviewer` (un CRITICAL, reparat — golul 2014–2017 n-avea caz pe datele livrate) și
  `accounting-reviewer` (niciun CRITICAL). Cinci lucruri **raportate, nu decise** — în
  `tests/corpus/README.md` și `PROGRESS.md` (întrebările 24–27).
- **Blocat de:** — *(reclasificată 2026-08-29 prin
  [ADR-054](../decisions/054-importul-e-distributie-corpusul-e-intern.md): nu mai e blocată pe un
  contabil extern; e o sarcină de construit cazuri, a sesiunii de implementare. Ce nu prinde corpusul
  intern — divergența dintre înțelegerea noastră și practică — se prinde la primul client real, F3.)*

  *Textul blocajului, păstrat:* „contabilul practicant — cazurile cu rezultat verificat nu se pot
  fabrica. Este singura măsură de risc contabil rămasă după ADR-010, iar F0 s-a încheiat cu ea încă
  goală." Prima jumătate era o definiție: *verificat* însemna *de altcineva*; ADR-010 spusese deja că
  a doua semnătură nu mai e verificare independentă.

---

## F1.G1 și F1.G2 — grilele

Rămân descrise în detaliu în `07-f1-grile.md`, care le specifică deja bine. **Nu se copiază aici:**
o a doua copie a aceleiași sarcini diverge de prima, iar F0 a produs destule exemple.

| Sarcină | Poziție în secvență | Blocat de |
|---|---|---|
| **F1.G1** `DataGrid` | după F1.2, înainte de F1.8 | — *(`OD-19` prin [ADR-031](../decisions/031-stack-frontend.md); `OD-35` prin ADR-042; ținta prin ADR-053; fixture-ul F1.G0 sintetic, ADR-054)*. **Servește F1.8 de la 2026-08-30** — fișa contului, șahul, balanța — cu drill-down în loc de virtualizare (ADR-053 §4); virtualizarea rămâne gol numit în componentă |
| **F1.G2** `EntryGrid` | după F1.2, înainte de F1.7 | — *(contractul: [ADR-052](../decisions/052-contractul-de-tastatura.md))*. **Livrată 2026-08-30**: contractul §3 rând cu rând, cu un test Vitest per tastă; nota manuală și soldurile inițiale (GL) pe ea, fără handler propriu de taste (`C40`) — vezi `07-f1-grile.md` |

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

**Ce nu poate începe, și de ce e util să fie vizibil** *(recalculat 2026-08-29, după ADR-049–054 și
`V1`)*: **nimic din F1 nu așteaptă ceva din afară — și nici pe proprietar.** `V1` e citită, cele trei
convenții sunt aprobate și active, `OD-70` e închisă; F1.6 e livrată. F1.9 a plecat la F3; F1.G0 se
construiește sintetic; F1.10 e sarcină, nu blocaj. Tot restul poate începe.

**Ordinea, decisă de proprietar (2026-08-29): ~~F1.5.4~~ livrată, apoi F1.4.4, apoi F1.10.** Trei motive: rolurile și
ordinea lanțului sunt în ADR-050, deci nu mai e nicio decizie în față, pe când handlerele concrete
vor ridica întrebări de mapare pe drum; închiderea produce `period.month.closed`, care lipsește din
registrul de evenimente — singura verificare mecanică că F1.5.4 e neterminată, și merită să devină
pozitivă; și închiderea validează invariantul clasei 8 și blocarea perioadei, precondiții pentru
orice handler care postează — un handler scris înainte se testează într-un mediu unde perioada nu se
închide niciodată. F1.10 vine după oricare, fiindcă cazurile ei cer handlerele.

*Versiunea anterioară a paragrafului:* F1.4.4 aștepta `C1`–`C5`; F1.5.4 și F1.6 așteptau `OD-22`;
F1.8 aștepta `OD-35`; F1.G2 aștepta `OD-36` — cinci din zece sarcini blocate pe lucruri care nu se
rezolvă scriind cod. Patru dintre ele s-au închis într-o zi, prin instrucțiune scrisă, iar una
(F1.5.4) era blocată pe o definiție greșită.

---

## Criteriul de ieșire din F1

*Rescris 2026-08-29 prin [ADR-054](../decisions/054-importul-e-distributie-corpusul-e-intern.md):
extrasul 1C a ieșit din criteriu — cele trei puncte care îl numeau validau de fapt registrul, iar
„balanță pe date importate" testa motorul și cititorul de format deodată.*

- [x] Balanță de verificare corectă **pe corpusul intern** (F1.10) — `backend/tests/corpus/`,
      33 de cazuri citate, 2026-08-30
- [x] Diferență zero la reconciliere **între balanță, Cartea Mare și fișa contului**, pe același corpus —
      `tests/corpus/book.py::agree`, apelat la sfârșitul fiecărui caz și cerut de gardianul corpusului
- [x] Storno și reînregistrare funcționează, cu lineage coerent — `tests/integration/test_vertical_slice.py`:
      ambele legături `R14`, al doilea storno refuzat, balanța la zero; și în corpus,
      `tests/corpus/test_storno.py` pe SNC „Politici contabile" pct. 33
- [x] Postarea într-o perioadă închisă este refuzată — `test_posting_invariants.py`
      (`closed`, `locked` cu cod propriu), `test_periods.py::test_posting_into_a_closed_period_is_refused`
- [x] Corpusul de regresie rulează în CI (`C14`) — cu suita întreagă (`uv run pytest -q`), selectabil
      cu `-m fiscal_regression`

**Criteriul e îndeplinit (2026-08-30).** Ce nu prinde el — divergența dintre înțelegerea noastră și
practică — e a primului client real (F3, ADR-054 §3). `CLAUDE.md` §4 nu mai blochează codul de modul.

**Niciun punct nu mai depinde de ceva din afară.** Rămâne `V1` — un document public, o oră — pe F1.6.

*Versiunea anterioară:* „Balanță de verificare corectă pe date reale importate din 1C; diferență
zero la reconciliere; […] **Trei dintre cele cinci depind de un extras 1C real.**"

---

## Tabelul de blocaje — se verifică, nu se citește

| Sarcină | Decizie | Natura |
|---|---|---|
| ~~F1.4.2~~ | ~~`OD-55`; ADR-036 `Propus`~~ | Închise 2026-08-29: [ADR-051](../decisions/051-chei-de-context-enumerate.md); ADR-036 `Acceptat` |
| ~~F1.4.4~~ | ~~`C1`–`C5` din ADR-036 §11~~ | Închis 2026-08-29: clasificarea aprobată, ADR-036 §11. Rămân în afara sarcinii: HG 704/2019, Anexa 1 SNC „Diferențe de curs" |
| ~~F1.5.4~~ | ~~`OD-22`~~ | Dizolvat 2026-08-29: [ADR-050](../decisions/050-lantul-de-inchidere-ca-roluri.md) — conturile lanțului sunt roluri din Planul general de conturi, nu parametri fiscali |
| ~~F1.6~~ | ~~direcția la echidistanță~~ | Decisă `half_up` 2026-08-29; toate cele trei convenții active. F1.6 livrată; corpusul e F1.10 |
| ~~F1.8~~ | ~~`OD-29`~~ | Închisă 2026-08-29: [ADR-053](../decisions/053-tinta-de-performanta.md) |
| ~~F1.9~~ | ~~`OD-28`~~ | **Mutat la F3** ([ADR-054](../decisions/054-importul-e-distributie-corpusul-e-intern.md)): instrument de distribuție, nu fundație. `OD-28` blochează cititorul și reconcilierea la F3, nimic în F1 |
| ~~F1.G0~~ | ~~`OD-28`, `OD-30`~~ | **Sintetic**, ales explicit (ADR-054 §3.4): volum din modelul F0.11, structură din corpus. Ce se sacrifică e scris în `07-f1-grile.md` și se recuperează la primul extras real |
| ~~F1.G2~~ | ~~`OD-36`~~ | Închisă 2026-08-29: [ADR-052](../decisions/052-contractul-de-tastatura.md) |
| ~~F1.10~~ | ~~contabilul practicant~~ | **Reclasificată** (ADR-054 §3.3): sarcină de construit cazuri, cu citare; nu blocaj |

Când o decizie se închide, **rândul de aici se taie în același commit**. Regula există fiindcă la
F0 nu a existat.
