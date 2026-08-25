# CLAUDE.md — Evidenta.md

Platformă contabilă și ERP pentru Republica Moldova. Django + PostgreSQL cu Row Level Security,
multi-tenant, ledger append-only, conformitate SNC / TVA / e-Factura / CNAS / CNAM / BNS.

**Regulile de mai jos nu sunt recomandări.** Codul care le încalcă nu se comite, indiferent cât de
bine funcționează. Fiecare regulă are un identificator stabil (`R1`, `D3`, `C7`) — folosește-l când
raportezi o încălcare.

**Restul contextului stă în `docs/`** și se citește doar când e relevant: `docs/specs/` (Spec A —
tenancy, Spec B — accounting), `docs/decisions/` (ADR-uri și decizii deschise), `docs/PROGRESS.md`
(starea proiectului), `docs/_input/` (documentele de strategie, read-only).

---

## 1. Invarianți

### 1.1 Izolarea datelor

- **R1** — Fiecare tabelă business are `tenant_id`. Excepțiile sunt enumerate limitativ în
  `infra/rls/exceptions.toml`, singurul loc unde lista trăiește. Nu o duplica în alt document și nu
  adăuga o tabelă acolo ca să faci suita să treacă: modificarea fișierului este ADR.
- **R2** — Fiecare tabelă business are politică RLS activă și `FORCE ROW LEVEL SECURITY`.
  Tabelele cu formă de politică diferită de șablon o declară în același fișier; gardianul de model
  verifică forma declarată, nu sare peste ele.
- **R3** — Contextul de tenant se setează cu `SET LOCAL` în interiorul unei tranzacții. Orice
  request rulează într-o tranzacție.
- **R4** — Absența contextului înseamnă zero rânduri sau eroare. Niciodată acces total.
- **R5** — Trei roluri de bază de date: `evidenta_owner` (migrare, deține tabelele),
  `evidenta_app` (runtime, fără `BYPASSRLS`, fără ownership), `evidenta_rls` (`BYPASSRLS`,
  `NOLOGIN`, deține exclusiv predicatele de acces). Aplicația primește doar `EXECUTE` pe predicate
  și nu este membru al lui `evidenta_rls`.
- **R6** — Fiecare task Celery primește `tenant_id` explicit ca argument și setează contextul
  înainte de orice query. Un task care deduce tenantul din stare globală este defect.
- **R7** — Interogările cross-tenant sunt permise exclusiv în stratul de read models
  (`platform/readmodels`) și în căile privilegiate enumerate în Spec A.
- **R8** — Nicio parte din logica de business nu presupune că doi tenanți sunt fizic în aceeași
  bază de date.
- **R27** — **Delegarea nu este tranzitivă.** `rls.has_tenant_access` nu înlănțuie două relații:
  firma din `app.actor_firm_id` trebuie să aibă ea însăși un engagement viu cu tenantul cerut. Un
  cabinet care ține contabilitatea altui cabinet nu primește nimic din clienții acestuia. Invers
  este permis și nu e excepție: firma poate fi clientul altei firme pentru propria contabilitate
  ([ADR-035](docs/decisions/035-fara-delegare-tranzitiva.md)).

### 1.2 Contabilitate

- **R9** — Niciun modul business nu scrie direct în ledger. Toate emit evenimente contabile către
  Posting Engine.
- **R10** — Ledgerul postat este imutabil. Niciun `UPDATE` pe `journal_entries` sau `journal_lines`
  postate. Corecția se face prin storno și reînregistrare.
- **R11** — Σ Debit = Σ Credit pe fiecare înregistrare, verificat la nivel de bază de date.
- **R12** — Postarea într-o perioadă închisă este refuzată de motor, nu de interfață.
- **R13** — Pentru orice efect financiar există lanțul complet, navigabil în ambele sensuri:
  `Journal Line → Journal Entry → Accounting Event → Source Document → Sursă`.
- **R14** — O înregistrare de storno are două legături: spre documentul sursă **și** spre
  înregistrarea anulată.

### 1.3 Conformitate

- **R15** — Parametrii fiscali sunt **date**: cote, praguri, plafoane, scutiri, coeficienți,
  termene, mapări de conturi. Versionate cu `valid_from` / `valid_to`, cu sursă (act normativ,
  număr Monitorul Oficial, dată publicare, dată intrare în vigoare). O cotă scrisă în cod este
  defect critic.
- **R16** — Logica fiscală este **cod versionat**: algoritmi de calcul, scheme de declarații,
  reguli de validare, comportament API instituțional. Aceasta este corect să fie deployment.
- **R17** — Selecția implementării se face printr-un registru, **după data efectivă a perioadei
  calculate**. Nicio condiție de tipul `if year >= 2027` în codul de business.
- **R18** — Recalcularea unei perioade trecute folosește parametrii și algoritmul valabili atunci.

### 1.4 Integritate operațională

- **R19** — Orice comandă sau eveniment extern cu efect financiar este idempotent. Cheia de
  idempotență stă pe **evenimentul contabil**, nu doar pe endpoint-ul API.
- **R20** — Deduplicarea documentelor economice (același document pe două căi: import bancar +
  introducere manuală, e-Factura + PDF scanat) se face prin chei naturale de business și
  constrângeri unice, separat de idempotență.
- **R21** — Tabelele append-only de volum mare **nu primesc chei străine**. Lista este enumerată
  limitativ în `infra/schema/append_only.toml`, singurul loc unde trăiește; modificarea ei este ADR.
  Legăturile se fac invers. *(O tabelă fără FK-uri intrând se repartiționează; una cu zece FK-uri
  intrând se redesenează.)*
- **R22** — Aceste tabele au coloana naturală de partiționare (`accounting_date` sau `occurred_at`)
  ca `NOT NULL` de la început, și indecșii încep cu contextul de tenant și companie.

### 1.5 Produs

- **R23** — Un singur codebase. Diferențierea prin feature flags și release rings, niciodată prin
  ramuri sau versiuni per tenant.
- **R24** — Conformitatea nu este niciodată capability plătibilă sau dezactivabilă. TVA, e-Factura
  și raportarea SNC funcționează indiferent de plan.
- **R25** — Activarea unei capabilități este o entitate cu dată efectivă și stare de inițializare,
  nu un boolean.
- **R26** — Profilul de capabilități al tenantului este input explicit al Posting Engine. Aceeași
  operațiune se contabilizează diferit după capabilitățile active.

---

## 2. Stack și convenții

### 2.1 Stack

```
Frontend     React + TypeScript + Vite, pe Node 24 LTS
Backend      Django 5.2 LTS + DRF, pe Python 3.13
DB           PostgreSQL 18 (RLS obligatoriu)
Cache/Queue  Redis
Tasks        Celery
Storage      S3-compatible
Deploy       Containere, medii dev / staging / prod
```

Versiunile de mai sus sunt fixate prin `docs/decisions/005-stack-versions.md`. Restul dependențelor
se pinuiesc exact, în lockfile. **Upgrade-ul este sarcină proprie, niciodată în timpul unei faze.**

### 2.2 Django

- **C1** — Un app Django per modul. Fără app-uri `utils` sau `common` care acumulează logică.
- **C2** — Modelele nu conțin logică de business. Serviciile o conțin. Modelele definesc structura
  și constrângerile.
- **C3** — Managerul implicit al modelelor business **nu** filtrează pe tenant. Filtrarea o face
  RLS. Un manager care filtrează creează impresia falsă de siguranță și maschează absența
  contextului.
- **C4** — Fără signals pentru logică financiară. Efectele contabile sunt explicite, apelate din
  servicii.
- **C5** — Migrațiile sunt aditive. Nicio migrare nu șterge o coloană cu date financiare fără plan
  de arhivare aprobat, referit în docstring-ul migrării.
- **C6** — `UUID` ca cheie primară pentru entitățile expuse extern; `bigint` pentru tabelele
  append-only de volum mare (lista din R21).

### 2.3 API

- **C7** — Versionare în cale: `/api/v1/...`. Resursele urmează modulul: `/api/v1/accounting/`,
  `/api/v1/payroll/`.
- **C8** — Contextul de tenant vine din subdomeniu, niciodată din payload sau din parametri de
  query.
- **C9** — Fiecare endpoint care produce efect financiar acceptă `Idempotency-Key`.
- **C10** — Erorile au cod stabil, nu doar mesaj.

### 2.4 Teste

- **C11** — Fiecare modul are teste unitare pentru servicii.
- **C12** — Fiecare efect financiar are test de integrare care verifică lanțul complet până la
  journal line, cu sume și conturi.
- **C13** — Suitele de izolare rulează la fiecare commit:
  `backend/tests/isolation/` (penetrare) și `backend/tests/schema_guard/` (gardian de model).
- **C14** — Corpusul de regresie fiscală rulează la fiecare modificare de parametru sau algoritm.
- **T1** — Toate testele de izolare rulează **sub rolul de aplicație**, niciodată ca superuser sau
  ca owner de tabelă. Un test rulat ca owner ocolește RLS și nu demonstrează nimic. Dacă rolul nu
  poate fi confirmat, spune asta — nu scrie un test care dă asigurare falsă.
- **T2** — Suita de penetrare acoperă obligatoriu: engagement expirat, engagement revocat,
  engagement cu scope restrâns, task Celery fără context setat.

### 2.5 Tooling

- **C28** — Mediul și dependențele se gestionează cu **uv**; lint și formatare cu **ruff**; teste cu
  **pytest**. `uv.lock` este pinul exact și se comite. `make sync`, `make lint`, `make format`,
  `make typecheck`, `make test`.
- **C29** — **mypy strict rulează doar pe `platform` și `accounting`.** Nu se extinde la alte module
  fără ADR: pe cod unde tipurile nu adaugă nimic, strictețea produce zgomot care se ignoră, iar un
  verificator ignorat nu verifică nimic. Flagurile de strictețe se enumeră explicit în
  `pyproject.toml`, niciodată prin `strict = true` — lista acoperită de `strict` se schimbă între
  versiuni de mypy, iar un upgrade nu are voie să modifice tăcut ce se impune.

### 2.6 Migrații și SQL manual

- **C30** — SQL-ul de politici se aplică **din migrațiile Django**, prin
  `evidenta.platform.rls.sql.run_sql_file()`, ca tabela și politica ei să ajungă în aceeași
  tranzacție. Ordinea în interiorul migrării: `CREATE TABLE` → `ENABLE` → `FORCE ROW LEVEL
  SECURITY` → `CREATE POLICY` → `GRANT`. Fiecare fișier are pereche `.down.sql`; `reverse_sql` nu
  este opțional.
- **C31** — Fișierele din `infra/migrations/` sunt **append-only** odată referite de o migrare
  aplicată: nu se editează, nu se redenumesc, nu se șterg. Corecția este un fișier nou și o migrare
  nouă — aceeași regulă ca pentru ledger, din același motiv. Rolurile, schemele și predicatele stau
  în `infra/bootstrap/`, în afara ciclului de migrare; `CREATE ROLE` într-o migrare Django nu se
  derulează înapoi.

### 2.7 Limbă

- **C32** — Șirurile de interfață stau în fișiere de resurse de la primul ecran, niciodată în
  componente. Nu este i18n: este ce face „adăugăm rusa" să coste o traducere în loc de parcurgerea a
  200 de componente ([ADR-014](docs/decisions/014-limba-rusa.md)).
- **C33** — **Contabilitatea se ține în limba română** — Legea nr. 287/2017, art. 7 alin. (1). Nicio
  traducere de interfață nu ajunge într-un registru contabil, într-o situație financiară sau într-un
  document generat. Nu este preferință de produs: un registru în altă limbă este artefact neconform.
  Denumirile din planul de conturi sunt valoare unică, în română
  ([ADR-016](docs/decisions/016-limba-contabilitatii.md)).
- **C38** — Generarea unui **document legal** — document tipărit, registru, situație financiară,
  declarație, payload e-Factura, descriere de înregistrare contabilă generată de sistem —
  deschide **explicit** contextul lingvistic românesc și nu moștenește limba activă a cererii
  sau a task-ului. Formatarea de numere și date pe documente vine dintr-un modul de document cu
  convenții `ro-MD` fixe, care nu consultă limba activă. *Măsurat: limba activată supraviețuiește
  unității de lucru care a setat-o, deci un worker refolosit o duce în următoarea sarcină — de
  aceea regula numește Celery explicit* ([ADR-033](docs/decisions/033-limba-la-generare.md)).
- **C39** — Pe un document, într-un registru sau într-un export apare **denumirea legală**
  (`item.name`, `partner.legal_name`), niciodată denumirea internă (`internal_name`) — liberă ca
  alfabet, existentă doar pentru interfață, căutare și importuri
  ([ADR-034](docs/decisions/034-denumire-legala-si-interna.md)).
- **C34** — Coloanele de **denumire** folosesc colația implicită a bazei (`ro-x-icu`); coloanele de
  **cod** — IDNO, coduri de conturi și articole, SKU, numere de documente — primesc `COLLATE "C"`
  explicit ([ADR-015](docs/decisions/015-colatie-icu.md)).
- **C15** — Cod, comentarii, nume de variabile, mesaje de commit: **engleză**.
  Interfață, documentație de utilizator, denumiri contabile: **română**.
  Termenii legali își păstrează forma oficială: `IDNO`, `TVA`, `IPC`, `CNAS`, `CNAM`, `SNC`,
  `e-Factura`.

Sursa pentru `C35`–`C37`: [ADR-017](docs/decisions/017-terminologie.md) (Acceptat), unde stau
ambele tabele complete de terminologie. `CLAUDE.md` nu este glosar — aici stă doar ce se încalcă.

- **C35** — `supplier` este **rezervat exclusiv** furnizorului din achiziții. Nu se folosește pentru
  firma de contabilitate, nu se folosește pentru furnizorul platformei, nu se folosește ca sinonim
  comod în niciun alt context.
- **C36** — `firm` este **organizație, nu persoană**. Contabilul individual este o firmă cu un
  singur membru, nu un al doilea tip de actor. Cod care ramifică pe „contabil persoană fizică" este
  defect.
- **C37** — Termenii de model **nu apar niciodată în interfață**: `tenant`, `firm`, `engagement`,
  `assignment`. Nici în etichete, nici în mesaje de eroare, nici în e-mailuri, nici în documente
  generate. Stratul de model și cel de interfață sunt independente, legate printr-o hartă fixă în
  ADR-017 — nu se aliniază unul după celălalt. *Fiindcă `C32` cere șirurile în fișiere de resurse,
  regula se verifică printr-un grep peste acele fișiere.*

### 2.8 Frontend

Sursa: `docs/decisions/001-grila-de-date.md` (Acceptat). Grila de date este componenta dominantă a
frontend-ului într-un ERP contabil, nu un detaliu de prezentare — regulile de mai jos o tratează ca
atare.

- **C16** — Singurele puncte de intrare pentru grile sunt `DataGrid` (citire) și `EntryGrid`
  (introducere). Niciun ecran nu importă `@tanstack/react-table` direct. Impus prin ESLint
  (`no-restricted-imports`), cu excepție doar pentru fișierele celor două componente.
- **C17** — Nu se adaugă o a treia componentă de grilă. Dacă un ecran are nevoie de altceva, se
  extinde una dintre cele două.
- **C18** — Formatarea numerică și monetară trece printr-un singur modul. Fără formatare locală în
  componente. Acesta este strat de **afișare**; precizia și rotunjirea de calcul stau pe server.
- **C19** — Totalurile, subtotalurile și agregatele vin de la server. Niciun total calculat în
  client peste un set virtualizat sau paginat. Într-un raport contabil, un total greșit este defect
  grav, nu inconsecvență cosmetică.
- **C20** — Exporturile (Excel, CSV, PDF) se generează pe server, din aceeași sursă ca afișarea, ca
  să nu poată diverge de ce vede utilizatorul.
- **C21** — Spațierea în ecranele cu grile folosește scara de densitate. Fără valori hardcodate.
  *Scara însăși nu e încă stabilită — `OD-35`. Regula este activă de acum; valorile se completează
  la închiderea deciziei. Până atunci, spațierea nouă se ridică, nu se inventează.*
- **C22** — Documentele tipărite — factura, ordinul de plată, balanțele, situațiile financiare,
  declarațiile — nu se randează din React. Au format impus, uneori strict; se generează printr-un
  pipeline server-side separat.

Sursa pentru `C23`–`C27`: `docs/decisions/009-componente-si-stil.md` (Acceptat).

- **C23** — Componentele shadcn sunt **cod copiat**, nu dependență. Nu există pachet `shadcn/ui` în
  manifest și nu se „actualizează" din amonte. Fixurile din amonte se preiau manual sau deloc.
- **C24** — O componentă copiată se modifică **în `frontend/src/shared/`**, niciodată printr-o
  copie locală per ecran. O a doua copie făcută ca să fie modificată pentru un singur ecran este
  defect, nu adaptare.
- **C25** — Stilul se scrie în Tailwind. CSS scris de mână există **doar** în `DataGrid` și
  `EntryGrid`, unde virtualizarea cere control fin. Excepția este enumerată aici tocmai ca să rămână
  excepție: CSS de mână în altă parte se ridică, nu se adaugă.
- **C26** — Culorile, spațierea și tipografia sunt tokeni — variabile CSS în configurația Tailwind,
  consumate peste tot. Fără valori literale în componente. Scara de densitate din `C21` este un set
  de tokeni, nu o convenție verbală.
- **C27** — Orice coloană numerică folosește cifre tabulare (`font-variant-numeric: tabular-nums`),
  aplicate de `DataGrid` și `EntryGrid` prin token, nu presărate prin ecrane. Fără ele, coloanele de
  sume se mișcă vizual de la un rând la altul.

*Contractul de introducere cu tastatura (`OD-36`) nu este încă scris, deci nu are regulă numerotată.
Până când există, se aplică o singură constrângere: ecranele nu adaugă handlere proprii de taste
peste `EntryGrid`. Comportamentul de tastatură aparține componentei.*

---

## 3. Reguli de dependență între module

Graful de dependențe este **aciclic**. Direcția permisă:

```
platform     ←  totul poate depinde de platform
fiscal       ←  nu depinde de niciun modul business
masterdata   ←  depinde doar de platform
accounting   ←  depinde de platform, masterdata, fiscal
operations   ←  depinde de toate cele de mai sus
```

- **D1** — `fiscal` nu importă din niciun modul business.
- **D2** — `accounting` nu importă din `sales`, `purchases`, `payroll`, `inventory`. Contabilitatea
  nu cunoaște sursa; primește evenimente.
- **D3** — Modulele operaționale nu importă `accounting.ledger`. Doar `accounting.events`.
- **D4** — `payroll` nu importă din `tax`. Ambele consumă `fiscal`.
- **D5** — Nimic nu importă din `firmspace`. Este strat de prezentare peste read models.
- **D6** — Comunicarea între module se face prin evenimente contabile, servicii publice ale
  modulului sau read models. Niciodată prin import direct de modele.

---

## 4. Ce nu se face

- Nu se creează app-uri Django goale pentru module din faze viitoare. „Modelat în F0" înseamnă că
  structura din faza curentă nu face imposibil modulul viitor, nu că app-ul există acum.
- Nu se scriu module din F2+ înainte de criteriul de ieșire din faza curentă.
- Nu se implementează CRM, producție, MRP, WMS sau POS. Nu sunt în scop.
- Nu se folosesc signals Django pentru logică financiară.
- Nu se adaugă managere de model care filtrează pe tenant.
- Nu se scrie `if year >= X` în logică fiscală.
- Nu se adaugă chei străine către tabelele append-only de volum mare.
- Nu se face `UPDATE` pe date contabile postate.
- Nu se creează endpoint-uri care ocolesc Posting Engine.
- Nu se pornesc microservicii.
- Nu se rulează teste de izolare sub superuser sau owner de tabelă.
- Nu se adaptează un test ca să treacă peste un bug din codul de producție.
- Nu se închide tacit o decizie deschisă. Dacă o sarcină cere una, se oprește și se întreabă;
  decizia luată se consemnează în `docs/decisions/`.
- Nu se deduc reguli fiscale, praguri, cote, termene sau formate de raportare din memorie.
- Nu se adaugă o regulă obligatorie în acest fișier fără un ADR `Acceptat` în spate. O regulă
  fără ADR nu are autoritate și se șterge la prima revizuire — vezi `docs/decisions/002`.
- Nu se randează documente tipărite din componente React.
- Nu se generează un document legal în limba activă a cererii sau a task-ului. Contextul
  românesc se deschide explicit, la intrarea în pipeline.
- Nu se extinde predicatul de acces ca să înlănțuie două engagementuri.
- Nu se calculează totaluri contabile în client.

---

## 5. Starea sesiunii

`docs/PROGRESS.md` se citește la începutul fiecărei sesiuni de implementare și se actualizează la
sfârșitul ei: ce s-a făcut, unde s-a oprit, ce blochează, ce întrebare a rămas deschisă. O sesiune
care nu actualizează starea lasă proiectul într-o poziție din care următoarea sesiune reconstruiește
contextul ghicind.

O sesiune = un modul sau o capabilitate. Niciodată „implementează Faza 0" — sarcinile largi produc
cod plauzibil care încalcă invarianți subtil.
