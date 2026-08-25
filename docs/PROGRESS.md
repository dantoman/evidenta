# Stare proiect

> Acest fișier este mecanismul prin care munca supraviețuiește resetării contextului între sesiuni.
> Se citește la începutul fiecărei sesiuni și se actualizează la sfârșit. O sesiune care nu îl
> actualizează lasă proiectul într-o poziție din care următoarea sesiune reconstruiește contextul
> ghicind.

## Faza curentă

**F0 — Fundament.** Inițializarea s-a terminat; implementarea a început cu **F0.1 — roluri de bază
de date și infrastructură RLS**.

## Ultima sesiune

**2026-08-25, corecții pe stratul de rezoluție** — mesaje care trimiteau la o fază terminată:

- `refuse_all` și comentariul din `settings/base.py` spuneau amândouă „la F0.3.5", dar F0.3.5 e
  livrat. Spun acum ce lipsește de fapt: `RLS_CONTEXT_RESOLVER` e un dotted path către un callable,
  iar `SubdomainTenantResolver` cere `base_domain` în constructor — deci cablarea cere o setare și o
  factory, nu o linie de settings. Plus utilizatorul autentificat, fără de care rezolvatorul refuză
  oricum (F0.3.7b)
- **de urmărit**: F0.3.5 e bifat, dar rezolvatorul nu e pe calea de request a niciunui mediu. Se
  exercită doar prin suita de izolare, care îl instanțiază direct. Bifa nu spune asta
- `resolver_for_testing` șters din `platform/rls/middleware.py`: zero referințe în repo, iar ce
  făcea era să deducă tenantul din anteturi `X-Test-*` — calea pe care `C8` o interzice. Cod mort
  care citește identitatea dintr-un antet este exact ce se cablează din greșeală mai târziu
- **`makemigrations` nu rulează** sub gardă: `check_consistent_history()` citește
  `django_migrations` pe conexiunea aplicației și garda refuză — aceeași clasă de problemă ca la
  `runserver`, dar fără exemptare declarată. Spre deosebire de `runserver`, verificarea e apelată
  inline în `handle()`, deci un `makemigrations` propriu ar trebui să declare `unguarded()` peste
  toată comanda, nu peste o singură interogare. Nedecis; până atunci comanda cade
- suita completă verde la măsurătoare: **121 de teste**, `ruff` și `mypy` curate

**2026-08-25, F0.3.7a** — modelul de roluri, ADR-020 aplicat:

- `permission` (catalog global, cheie primară naturală, alimentat din cod prin migrare), `role` și
  `role_permission` per tenant; `membership.role` și `company_access.role` au devenit chei străine
- **cheile străine compuse** sunt ce nu se putea exprima în Django: `(tenant_id, role_id)` pe
  membership și company_access, iar pe `role_permission` una singură — `(tenant_id, role_id, scope)`
  → `role (tenant_id, id, level)` — care ține două invariante deodată: același tenant și același
  nivel. Un rol de tenant nu poate primi o permisiune de companie, iar baza o refuză
- **triggere** pentru cele două ștergeri care ar bloca un tenant în afara lui însuși: rolul de
  sistem nu se șterge, și nu poate pierde `tenant.manage_roles`
- **serviciul** a intrat direct în `OD-37` — găsit de `tenancy-guard` la review, nu de mine la
  scris: `membership` are politica `user_id = app.current_user_id()`, deci o sesiune își vede un
  singur rând. Două consecințe, ambele acum refuzate cu cod stabil în loc să pară că funcționează:
  `assign_role` nu poate muta rolul altui membru (rândul e invizibil, iar ORM-ul ar fi raportat
  „nu există", ceea ce e alt fapt), iar regula anti-blocare din ADR-020 nu poate fi **verificată**,
  fiindcă a demonstra că mai există un administrator înseamnă a citi alte membership-uri. Garda
  scrisă inițial ar fi găsit mereu zero și ar fi trecut testele exact ca una care funcționează
- catalogul are 8 chei, fiecare cu calea de cod care o impune scrisă lângă ea — o permisiune fără
  punct de impunere ar citi ca protecție într-un ecran și n-ar bloca nimic
- două defecte găsite rulând, nu citind: `RunPython` scria pe conexiunea implicită (tabela nici nu
  era vizibilă, iar aplicația n-are grant de scriere pe catalog), iar triggerul de protecție
  bloca chiar curățarea fixture-urilor — harness-ul îl dezactivează acum explicit, pentru curățare
- **121 de teste trec**; `ruff` și `mypy` curate; migrarea aplicată și pe baza de dezvoltare
- `tenancy-guard` a dat două CRITICAL, ambele reale și ambele reparate. Peste ele, un test care
  arată că refuzul este o **limită**, nu regula cerută: cu doi administratori activi în tenant,
  răspunsul e același. Fără el, testul anterior trecea din motivul greșit
- `schema-reviewer` a dat un CRITICAL, tot real: protecția rolurilor de sistem se declanșa **doar
  pe DELETE**, iar aplicația are `UPDATE`. Două instrucțiuni obișnuite o ocoleau complet —
  `UPDATE role SET is_system = false` urmat de `DELETE`, sau rescrierea lui `permission_key` fără
  ca vreun rând să dispară. Testele probau ștergerea, adică fix calea acoperită. Închis prin
  `0020_roles_hardening` (fișier nou, nu editarea lui `0019`, care e aplicat — C31), cu probă
  pentru fiecare dintre cele două căi
- două corecții mai mici din același review: `role_permission.permission_key` nu avea `COLLATE "C"`
  deși e cod (C34) — cu efect vizibil, un index în plus creat de Django ca să compenseze; și
  `GRANT SELECT ON permission` era fără efect, fiindcă privilegiile implicite din bootstrap dau deja
  CRUD. Comentariul promitea două straturi acolo unde exista unul; `0021` adaugă `REVOKE`-ul
- **123 de teste trec.** Rămase de decis, nu tăcute: `module_key` (F0.3.3) are aceeași lipsă de
  colație; gardianul de model nu poate prinde niciuna, fiindcă `CODE_COLUMN_SUFFIXES` nu conține
  `key`; cheile străine cu o singură coloană generate de Django dublează inutil cele compuse

**2026-08-25, poziție consemnată** — răspunderea pentru un asistent automat (`OD-43`):

- registrul avea `OD-41` și `OD-42` folosite fiecare pentru **două** decizii diferite, din lucru
  în paralel. Numerele vechi rămân la deciziile vechi — `OD-42` e citat în ADR-017, care e
  `Acceptat` și nu se editează. Perechea apărută la F0.3.3 a devenit `OD-44` (listarea tenanților)
  și `OD-45` (corecțiile din contractul RLS); `infra/rls/exceptions.toml` actualizat. SQL-ul aplicat
  `0012_tenant_context_binding.up.sql` păstrează numărul vechi: `C31` îl face append-only, iar
  maparea stă în rândul `OD-44`

- asistentul este **instrument, nu actor**: răspunde tenantul, iar cel care l-a activat verifică ce
  a făcut. Aceeași poziție ca pentru un contabil angajat sau o firmă cu engagement — execută unul,
  răspunde altul
- consecință care simplifică modelul: **nu** e nevoie de identitate non-umană.
  `audit_event.actor_user_id` rămâne `NOT NULL`, iar `ADR-020` nu are de acoperit un actor în plus
- „cine a pornit asistentul" **este** activarea capabilității (R25), nu un câmp nou
- rămâne o singură coloană de decis, la `OD-43`: legătură nulabilă din `audit_event` către activare,
  de aceeași formă cu `actor_firm_id`. Ieftină cât tabela e goală în producție

**2026-08-25, decizii** — `DN-06` și `DN-07` închise, prin ADR-018 și ADR-019:

- **DN-06 → opțiunea B:** un tenant poate avea engagementuri vii cu mai multe firme, separate prin
  scope de module. `engagement_live_unique` rămâne cum e — opțiunea A ar fi adăugat o constrângere
  peste ea, B nu adaugă. Regula de arbitraj este *fără suprapunere*: un `module_key` aparține unui
  singur engagement viu per tenant, impus **în bază** — o verificare doar în servicii cade la primul
  import în masă sau la prima scriere concurentă
- **DN-07 → opțiunea A:** `module_key` = numele modulului de business din harta §4.1; `read`/`write`,
  `write` include `read`; `platform/*` nu primește chei de scope; lista într-un singur loc, impusă prin
  `CHECK`. Aleasă fiindcă se extinde spre catalogul fin fără migrare de date, iar B ar fi cerut și
  `DN-08` închisă. Limita acceptată, scrisă în ADR: o firmă cu `payroll` vede salariile individuale
- **`DN-15` rămâne deschisă și atinge direct regula de suprapunere:** dacă transferul între firme lasă
  firmei vechi acces numai-citire pe durata predării, aceea este prin definiție o suprapunere. Excepția
  se scrie atunci, explicit — până atunci transferul se modelează ca succesiune
- F0.3.3 fusese livrat **fără** cele două: modelele lăsau `module_key` fără `CHECK` și numeau decizia
  deschisă în comentariu, în loc să inventeze un răspuns. Acum se poate completa (F0.3.3b), iar F0.2.4
  — cazurile de engagement, IZ-25…IZ-29 — nu mai are nimic în față

**2026-08-25, tooling** — dezvoltarea locală trece pe nativ, fără docker:

- `Makefile` nu mai trece prin `docker compose exec`: `psql` merge direct la clusterul local, iar
  variabilele poartă exact numele citite de settings și de harness-ul de test — un singur vocabular,
  suprascris din `.env` (model în `.env.example`)
- **`make migrate` era defect:** rula `manage.py migrate` fără `--database=migration`, deci pe
  conexiunea `default`, adică `evidenta_app` — rolul care nu deține nimic. Ar fi eșuat cu
  *permission denied* la prima rulare reală. Harness-ul de test o făcea corect, de aceea nu s-a văzut
- ținte noi: `doctor` (uv, psql, PostgreSQL, Redis, baza), `setup`, `psql-app`, `run`, `worker`.
  `reset-db` cere `CONFIRM=yes`: acum șterge o bază reală, nu un volum docker
- docker rămâne pentru producție și CI. `docker-compose.yml` și criteriul F0.0.3 o spun explicit,
  ca sesiunea următoare să nu reintroducă compose în bucla de dezvoltare
- `make schema-dump` și `make rls-report` **există acum**: `schema-reviewer` le declara ca singurele
  două comenzi permise, dar niciuna nu fusese scrisă vreodată. Raportul stă în `infra/rls/report.sql`
- **Verificat pe un cluster de probă construit de la zero:** `make setup` creează baza cu colația
  ICU, aplică bootstrap-ul și cele patru migrații, apoi `make test` trece — 43 de teste, sub
  `evidenta_app`. Nu este raționament despre Makefile, ci rularea lui
- rulat apoi pe mașina de lucru, unde a ieșit un defect real de harness: `PGPASSWORD` și
  `password=` **setate pe gol** sunt tratate de libpq ca parolă validă, deci `~/.pgpass` nu mai era
  citit niciodată. `conftest.py` distinge acum „absent" de „gol" (`_admin_password`), iar Makefile-ul
  pune `PGPASSWORD` doar când are valoare. Pe un cluster cu credențialul în `.pgpass`, suita nu
  putea porni deloc
- `make check-roles`: numele rolurilor nu sunt configurabile — apar literal în fiecare politică și
  fiecare GRANT. Configurate greșit în `.env`, bootstrap-ul eșua abia la `0002`, după ce `0001`
  crease deja rolurile corecte. Acum refuză înainte, cu numele așteptate
- `backend/Makefile` redirecționează către rădăcină, ca `make test` să meargă și din `backend/`
- **43 de teste trec pe baza reală**, sub `evidenta_app`; `ruff` curat, `mypy` fără erori
- **`runserver` nu pornea deloc**, descoperit rulându-l: Django citește `django_migrations` pe
  conexiunea aplicației înainte să lege portul, iar garda refuză — corect, fiindcă nu poate deosebi
  o verificare de pornire de o cerere care a uitat contextul. Excepția e declarată acum îngust, într-un
  `runserver` propriu (`platform/rls/management/commands/`), nu lărgită în gardă: lărgită acolo, ar fi
  scutit citirea pentru toți apelanții, inclusiv cei care sunt defecte
- serverul pornește și răspunde 500 la orice cerere, cu `TenantResolutionError` — starea corectă
  până la F0.3.5: nu există rezolvator de subdomeniu, deci nicio cale de request către date
- `make manage ARGS="..."` — poarta pentru comenzile `manage.py`, care altfel rulează cu parolele
  implicite din settings, nu cu cele din `.env`

**2026-08-25, sesiunea a șasea** — F0.3 aproape complet, F0.4 livrat, trei blocaje închise:

- F0.3.3b, F0.3.5, F0.3.6, F0.4 livrate; 106 teste trec
- **ADR-020** închide DN-08: roluri ca date compozabile, dar peste un **catalog fix de permisiuni**
  în cod — clientul compune roluri, nu inventează drepturi
- **ADR-021** închide DN-09: MFA obligatoriu pentru toți, cu cerințele de recuperare scrise ca
  parte din decizie, nu ca detaliu ulterior
- **ADR-022** închide OD-02: numerotarea e șablon configurabil; filiala **nu** se modelează, iar
  dacă devine cerință reală e decizie nouă cu entitate proprie

**2026-08-24, sesiunea a cincea** — F0.1 completă, F0.2.1 livrat:

- F0.1.4 și F0.1.5: middleware, gardă de interogare și decorator Celery, în forma tare
- F0.0.2: proiect Django, fără `django.contrib.auth` (ar fi închis tacit DN-08)
- F0.2.1: harness cu trei privilegii separate — admin creează baza, owner aplică bootstrap și
  migrații, app rulează testele. Verificat că refuză ca owner și ca superuser
- cele 20 de verificări din probele Python au devenit 22 de teste pytest; probele au fost șterse în
  aceeași schimbare
- F0.2.2: gardianul de model, cu probă că fiecare regulă poate eșua. Două găuri reale găsite rulând:
  `citext` nu era instalat nicăieri, iar `evidenta_owner` nu avea `CREATE` pe bază — o acoperisem
  manual în fiecare probă în loc s-o remediez. Ambele reparate în `0001_roles.sql`

**2026-08-24, sesiunea a patra** — cinci ADR-uri, dintre care trei din corectarea unor premise:

- **ADR-016** — limba contabilității are **temei legal**, nu de piață: Legea nr. 287/2017, art. 7
  alin. (1), „Contabilitatea se ţine în limba română şi în monedă naţională". Am extras textul
  autentic al legii, nu un rezumat. Consecințe: rusa e strat de prezentare exclusiv; `OD-38`
  (ieșire bilingvă) se închide ca **nu se face**; denumirile din planul de conturi rămân valoare
  unică; `DN-01` se închide complet. Art. 7 alin. (2) dă temei legal modelului de sumă multi-valută
- **ADR-015** — `Acceptat`: colația bazei este `ro-x-icu`, decizie „la creare". Coloanele de cod
  primesc `COLLATE "C"` explicit. Parametrii verificați pe PostgreSQL 18.6: `ICU_LOCALE 'ro'`, nu
  `'ro-x-icu'` — al doilea e numele obiectului de colație
- F0.1.4 și F0.1.5 au acum criterii în **forma tare**, cu forma slabă numită explicit: un test care
  arată că *funcționează cu* context nu demonstrează că *nu funcționează fără*; iar un decorator
  fail-closed dar tăcut trece toate testele și raportează succes pe zero rânduri

- **ADR-013** — motivul consemnat pentru Python 3.13 se învechise în 24 de ore: Django 5.2.8,
  psycopg 3.3 și Celery 5.6 suportă 3.14. Pinul rămâne, dar cu motivul real (dependențele din F1–F2
  cu extensii C) și cu o condiție de ieșire verificabilă — corpusul de regresie verde pe versiunea
  nouă, nu citirea unui changelog
- **ADR-014** — `DN-01` restrânsă: „tenantul lucrează în rusă" nu cere schimbare de schemă, deci
  **nu blochează F0.7**. Rămâne deschisă doar forma denumirilor pentru datele de referință livrate
  de noi, cu termen F1.1. `OD-38` nou pentru ieșirea bilingvă, ținut separat deliberat
- **ADR-015** — `Propus`. Premisa („chirilicul se sortează imprevizibil") a căzut la măsurare:
  chirilicul se așază consecvent după latină sub orice colație lingvistică. Ce se rupe e `COLLATE
  "C"`, care sortează greșit **româna**, azi. Al doilea motiv, mai grav: colațiile glibc se schimbă
  între versiuni de SO și corup tăcut indecșii

**2026-08-24, sesiunea a treia** — tooling, mecanismul de migrare, regula de retragere a probei:

- ADR-012 închide OD-18: SQL-ul de politici se aplică din migrațiile Django. **F0.1 este completă
  ca decizii**; rămâne doar execuția, care cere `uv.lock`
- granița bootstrap/migrații este acum o **locație**, nu o convenție: `infra/bootstrap/` (roluri,
  scheme, predicate — idempotente, în afara ciclului) vs. `infra/migrations/` (per tabelă, referite
  din migrări). `schema-reviewer` o verifică mecanic

- ADR-011 închide OD-15: uv, ruff, pytest, mypy strict doar pe `platform` și `accounting`
- `backend/pyproject.toml` + `.python-version`; țintele reale `sync`, `lint`, `format`,
  `typecheck`, `test`. **`uv.lock` lipsește** — `uv` nu e instalat pe mașina de lucru
- ADR-008 a trecut la `Acceptat` (ADR-010 a închis OD-32); ADR-007 rămâne `Propus`, dar pentru trei
  întrebări de tratament contabil, nu din lipsă de semnătură
- proba SQL are acum opt scenarii, cu IZ-11 inclus, reverificate de la zero; **F0.2 nu e terminată
  până când toate au echivalent Python care trece**, iar SQL-ul se șterge în același commit

**2026-08-24, sesiunea a doua** — șase ADR-uri și primele trei migrări SQL:

- ADR-003 … ADR-008. Patru `Acceptat` (RLS pe tenancy, context de companie, versiuni de stack,
  cele două date ale stornoului), două `Propus` în așteptarea contabilului (perioada stornoului,
  retenția)
- lista excepțiilor RLS unificată în `infra/rls/exceptions.toml`, sursă unică pentru gardianul de model
- `infra/bootstrap/0001_roles.sql`, `0002_app_context.sql`, `0003_access_predicates.sql` — scrise
  **și rulate** pe PostgreSQL 18.6, idempotente
- `infra/rls/smoke_fixture.sql` + `smoke_test.sql` — șapte scenarii de izolare, toate cu rezultatul
  așteptat, sub rolul de aplicație
- `schema-reviewer` a primit înapoi `Bash`, restrâns la două comenzi read-only pre-aprobate

**2026-08-24, sesiunea întâi** — inițializare completă, etapele 0–6 din `BOOTSTRAP.md`:

- Etapa 0: citite integral cele trei documente de intrare; produs `_bootstrap/00-inventory.md`
  (invarianți, module, decizii, conflicte, goluri)
- Etapa 1: schelet de repo, `CLAUDE.md`, `README.md`, `.gitignore`, `docker-compose.yml`, `Makefile`
- Etapa 2: șase definiții de agenți în `.claude/agents/`, trei comenzi în `.claude/commands/`
- Etapa 3: structura `docs/`, formatul ADR, registrul deciziilor deschise, acest fișier
- Etapa 4: `specs/spec-a-tenancy.md` — 1625 linii, 25 de puncte „DECIZIE NECESARĂ"
- Etapa 5: `specs/spec-b-accounting.md` — 1018 linii, 11 puncte „DECIZIE NECESARĂ"
- Etapa 6: `_bootstrap/06-f0-backlog.md` — 49 de sarcini de dimensiunea unei sesiuni
- În afara etapelor, sesiune de decizii frontend:
  - **ADR-002** — guvernanța (`Acceptat`): proprietarul aprobă; conținutul contabil, fiscal sau
    juridic cere co-semnătura contabilului practicant și rămâne `Propus` până există unul.
    Regulile obligatorii intră în `CLAUDE.md` **doar** din ADR-uri `Acceptat`. Închide `OD-33`
  - **ADR-001** — grila de date (`Acceptat`): TanStack Table, consumat exclusiv prin `DataGrid`
    (citire) și `EntryGrid` (introducere)
  - `CLAUDE.md` §2.6 „Frontend" — `C16`–`C22`, plus patru intrări în §4
  - `OD-19` restrânsă; adăugate `OD-34` (biblioteca de componente — shadcn/Tailwind recomandat,
    **nedecis**), `OD-35` (scara de densitate), `OD-36` (contractul de tastatură)
  - **ADR-009** — shadcn/ui + Tailwind (`Acceptat`): componente copiate în `shared/`, tokeni ca
    sursă unică, `tabular-nums` pe coloanele numerice. Închide `OD-34`, deblochează `OD-35`
  - **ADR-010** — contabilul practicant (`Acceptat`): rolul e acoperit de proprietar. Închide
    `OD-32`. Măsura de risc trece de la „ADR-uri în `Propus`" la acoperirea corpusului de regresie
  - `CLAUDE.md` §2.6 crește la `C16`–`C27`
  - `_bootstrap/07-f1-grile.md` — cele două sarcini de grilă, extras parțial din backlogul F1
  - `OD-41` — Glide Data Grid evaluat și **păstrat ca variantă de rezervă**, mărginit la
    suprafețele de reconciliere. **Fără declanșator** — un prag măsurabil cere `OD-30`, care nu
    există; se reevaluează la F1.9. Cartea Mare și balanța rămân pe TanStack în orice variantă
  - **ADR-017** — terminologia (`Acceptat`): două straturi independente, cu hartă fixă între ele.
    `CLAUDE.md` §2.7 primește `C35`–`C37` (doar partea scurtă; tabelele stau în ADR). Deschide
    `OD-42` — `assignment` are cuvânt, nu are entitate în Spec A
  - `F1.G2` rescrisă: `EntryGrid` este **primitiva generală de introducere cu tastatura**, nu
    grila de linii de document. Acoperă și maparea conturilor la import și potrivirea extrasului.
    Dacă e proiectată îngust, a doua bibliotecă devine inevitabilă — singurul element din
    discuția despre grile cu cost dacă întârzie

## Sarcini

### Inițializare

- [x] Etapa 0 — Inventar și raport de goluri
- [x] Etapa 1 — Schelet de repo și `CLAUDE.md`
- [x] Etapa 2 — Agenți și comenzi
- [x] Etapa 3 — Infrastructură de documentație și stare
- [x] Etapa 4 — Draft Spec A (tenancy) — **necesită review uman**
- [x] Etapa 5 — Draft Spec B (accounting) — **necesită review uman și validare contabilă**
- [x] Etapa 6 — Backlog F0

Inițializarea este completă. Nimic nu mai poate avansa fără răspunsuri umane — vezi „Întrebări
deschise" mai jos.

### F0 — Fundament (nu a început)

Ordinea este obligatorie și nu se rearanjează. Rolurile de bază de date și suitele de verificare
preced orice model.

- [x] F0.1 — Roluri de bază de date și infrastructură RLS
  - [x] F0.1.0 — baza cu provider ICU + `0000_locale_guard.sql`, verificat pe toate trei variantele
  - [x] F0.1.1 — roluri (`0001_roles.sql`), cu verificări care refuză configurarea greșită
  - [x] F0.1.2 — schemele `app` și `rls`, funcțiile de context fail-closed (`0002_app_context.sql`)
  - [x] F0.1.3 — predicatele de acces (`0003_access_predicates.sql`), cu probă de fum
  - [x] F0.1.4 — middleware, gardă de interogare, context fail-closed; 8 verificări PASS
  - [x] F0.1.5 — decorator Celery fail-loud; 11 verificări PASS, inclusiv calea de retry
  - [x] F0.1.6 — mecanismul de aplicare a SQL-ului manual (`sql.py`, `make bootstrap`, `make migrate`)
- [ ] F0.0 — schelet de proiect
  - [x] F0.0.1 — dependențe și tooling; `uv.lock` comis, `ruff` curat
  - [x] F0.0.2 — proiect Django și Celery; `check`, `ruff`, `mypy`, `pytest` toate verzi
  - [ ] F0.0.3 — imagini de container
  - [x] F0.0.4 — CI pe GitHub Actions; jobul `quality` și jobul `tests`
  - [ ] F0.0.5 — contracte de dependență între module *(blocat de OD-17)*
- [ ] F0.2 — Suitele de verificare (penetrare + gardian de model)    ← ÎN CURS
  - [x] F0.2.1 — harness sub rolul de aplicație; refuză ca owner și ca superuser
  - [x] F0.2.2 — gardianul de model; 11 teste, fiecare regulă cu probă că poate eșua
  - [x] F0.2.3 — penetrare: toate cele opt scenarii SQL au echivalent pytest care trece
  - [x] F0.2.6 — suitele în CI, sub rolul de aplicație; proba SQL retrasă
- [x] F0.3 — Tenancy și identitate
  - [x] F0.3.1 — `Tenant`, `Company`, `CompanyVatRegistration` + politici, într-o migrare
  - [x] F0.3.2 — `User`, `Membership`; `tenant` interogabil pe calea de membru
  - [x] F0.3.3 — `Firm`, `Engagement`, scope-uri; a doua cale de acces, 9 teste
  - [x] F0.3.4 — `CompanyAccess`, `company` interogabilă, revocare în cascadă; 6 teste
  - [x] F0.3.5 — rezoluția subdomeniului, cale privilegiată îngustă; 15 teste
  - [x] F0.3.6 — ciclul de viață: matrice de tranziții ca date, coduri stabile; 12 teste
  - [x] F0.3.7a — modelul de roluri (ADR-020): catalog fix în cod, roluri ca date per tenant,
        chei străine compuse, triggere pe rolurile de sistem; 12 teste
  - [x] F0.3.7b — autentificare și MFA obligatoriu, coduri de rezervă, sesiuni; 13 teste
  - [x] F0.3.3b — ADR-018 și ADR-019 aplicate: vocabular `module_key` cu `CHECK`, regula de
        nesuprapunere impusă prin index unic parțial + triggere de sincronizare; 4 teste
        (`CHECK`, listă într-un singur loc) și regula de arbitraj *fără suprapunere*, în bază
- [x] F0.4 — Audit
  - [x] F0.4.1 — `audit_event` append-only, fără chei străine, `occurred_at NOT NULL`
  - [x] F0.4.2 — captare explicită din servicii, fără signals; engagement cablat
  - [x] F0.4.3 — corelatorul `request_id` și enumerarea efectelor (Spec A §9.3)
- [x] F0.5 — Capabilități și feature flags
  - [x] F0.5.1 — `CapabilityActivation` cu dată efectivă și stare de inițializare;
        nesuprapunere pe `COALESCE(company_id, tenant_id)`; R24 impus prin `CHECK`
  - [x] F0.5.2 — feature flags și release rings; override cu motiv și expirare
        obligatorii; flagurile de conformitate refuzate la suprascriere, prin trigger
- [ ] F0.6 — Document core, numerotare, atașamente *(numerotarea deblocată prin ADR-022)*
- [ ] F0.7 — Master data
- [ ] F0.8 — Parametri fiscali și registru
- [ ] F0.9 — Multi-valută
- [ ] F0.10 — Convenții API și schelet frontend

Descompunerea în 49 de sarcini de dimensiunea unei sesiuni, cu dependențe, agenți de review și
criterii de terminare: `_bootstrap/06-f0-backlog.md`.

**Nicio sarcină F0 nu poate începe încă.** Prima, F0.0.1, cere versiunile stack-ului și tooling-ul
Python (OD-14, OD-15).

**F0.1 este completă, iar F0.2 a început.** Izolarea are ambele straturi: baza refuză prin RLS și
funcții fail-closed, aplicația refuză mai devreme și cu mesaj lizibil — pe request, task, comandă și
shell. Harness-ul de test rulează sub rolul de aplicație și **refuză să pornească altfel**.

**106 de teste pytest trec**, sub `evidenta_app`. Probele manuale Python au fost retrase în aceeași
schimbare care le-a înlocuit; a rămas doar cea SQL, care așteaptă tabelele de tenancy din F0.3.

## Blocaje active

| Ce blochează | Ce nu se poate face | Referință |
|---|---|---|
| Corpusul de regresie fiscală nu are cazuri reale cu rezultat verificat | Nimic nu verifică mecanic conținutul contabil; este singura măsură de risc rămasă după ADR-010 | ADR-010, C14, F1.10 |
| Nu există extras real dintr-o bază 1C | `DataGrid` și `EntryGrid` nu pot fi validate pe structuri neanticipate; volumul se poate simula, structura nu | OD-28, OD-30, `_bootstrap/07-f1-grile.md` |
| Nu există semnătură electronică, entitate de test și acces în e-Factura | `DNB-08` (rotunjirea TVA) și formatele declarațiilor. **Singurul element extern pe drumul critic** | ADR-010, OD-24, OD-25 |

Primele trei rânduri se rezolvă în câteva ore: o instalare și două decizii. Ultimele trei nu se
rezolvă în cod — cer date reale și acces instituțional, iar de aceea sunt cele care contează.

## Decizii luate în această fază

Zece ADR-uri — opt `Acceptat`, două `Propus`. Index complet: `decisions/README.md`.

| ADR | Ce închide | Status |
|---|---|---|
| 001 — grila de date | restrânge `OD-19`; TanStack Table prin `DataGrid` + `EntryGrid` | Acceptat |
| 002 — guvernanța | `OD-33` | Acceptat |
| 003 — politica RLS pentru tabelele de tenancy | `DN-12`, `OD-07` | Acceptat |
| 004 — contextul de companie | `DN-11`, `OD-08` | Acceptat |
| 005 — versiunile stack-ului | `OD-14` *(nu și `OD-15`)* | Acceptat |
| 006 — stornoul are două date | `DNB-09`, partea structurală | Acceptat |
| 007 — perioada stornoului | `DNB-09`, politica | **Propus** |
| 008 — retenția | `DN-22`, mecanismul | **Propus** |
| 009 — componente și stil | `OD-34`; deblochează `OD-35` | Acceptat |
| 010 — contabilul practicant | `OD-32` | Acceptat |
| 018 — engagementuri multiple | `DN-06` | Acceptat |
| 019 — vocabularul de scope | `DN-07` | Acceptat |

**ADR-007 și ADR-008 sunt deblocate de ADR-010**, dar rămân `Propus`: trec în `Acceptat` la
confirmarea proprietarului, nu automat.

Registrul deciziilor deschise: `decisions/000-open-decisions.md` — 42 de intrări
închise, plus 25 de puncte în Spec A §11 și 11 în Spec B §11.

Deciziile închise anterior, prin documentele de intrare, sunt inventariate în
`_bootstrap/00-inventory.md` §3.1. Trei dintre ele au nevoie de ADR retroactiv.

## Întrebări deschise către om

Ordonate după cât de devreme blochează. Lista de mai jos e reconciliată cu ADR-urile 003–011:
`OD-07`, `OD-08`, `OD-10`, `OD-14`, `OD-15`, `OD-18` și `OD-32` sunt **închise** și au ieșit de aici.

1. **OD-16** — platforma CI și cum rulează suitele **sub rolul de aplicație** într-un runner efemer.
   Blochează F0.0.4 și F0.2.6.
2. **ADR-007** — cele trei întrebări de tratament contabil despre perioada stornoului:
   redeschiderea unei perioade închise înainte de depunere; dacă o corecție după depunere impune
   obligatoriu declarație rectificativă; stornoul unei perioade `locked`. Deblocate de `ADR-010`,
   dar nerăspunse.
3. **OD-37** — cum se listează membrii unui tenant, dat fiind că politica pe `membership` este
   `user_id = current_user_id()`. Blochează ecranele de administrare a echipei (F0.3.2).
4. **OD-11** — unde locuiesc modelele „modelate în F0, implementate mai târziu", dat fiind că
   app-urile Django goale sunt interzise.
5. **OD-40** — acoperă art. 7 și conținutul documentelor primare emise? Art. 11 nu prescrie limba
   pentru ele; singura prevedere, alin. (11), privește documentele primite din străinătate și
   acceptă și rusa. Până la răspuns, produsul nu restricționează nimic.
6. **OD-06, OD-22, OD-23** — deblocate de `ADR-010`, dar nerăspunse: valorile fiscale efective și
   planul de conturi SNC cer în continuare actul normativ citat, nu memoria.
7. **Accesul la e-Factura** — semnătură electronică, entitate de test, ghid de integrare.
   Singurul element extern pe drumul critic; de el depinde `DNB-08`.

Peste acestea, punctele „DECIZIE NECESARĂ" rămase din Spec A §11 și Spec B §11. Dintre cele care
cereau contabilul practicant, `DNB-05`, `DNB-07` și `DNB-09` sunt deblocate de `ADR-010`. `DNB-08`
(rotunjirea TVA) **nu** este: depinde de validatorul SFS, nu de expertiză contabilă.
