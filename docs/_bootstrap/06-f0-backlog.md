# 06 — Backlog F0

- **Data:** 2026-08-24
- **Sursa ordinii:** `_input/evidenta-implementation-spec.md` §6.1. **Ordinea F0.1 → F0.10 este
  obligatorie și nu se rearanjează.** În special: rolurile de bază de date (F0.1) și suitele de
  verificare (F0.2) preced orice model.
- **Obiectivul fazei:** platforma poate izola corect doi tenanți și un engagement, demonstrat prin
  teste automate.
- **Regula de dimensionare:** o sarcină care atinge mai mult de un modul sau care nu poate fi
  verificată printr-un criteriu clar este prea mare. Fiecare sarcină de mai jos încape într-o
  sesiune Claude Code.

## Cum se citește o sarcină

```
F0.x.y — titlu
Obiectiv:   o propoziție
Fișiere:    ce se creează sau se modifică
Depinde de: sarcinile anterioare necesare
Review:     agenții invocați la final
Terminat:   criteriu verificabil, nu „funcționează"
Blocat de:  decizii deschise, dacă există
```

**Definition of Done** se aplică fiecărei sarcini, peste criteriul propriu: zero CRITICAL de la
agenții invocați, ambele suite de izolare verzi, nicio decizie deschisă închisă tacit.

## Două abateri de la documentul de intrare, semnalate

1. **F0.0 nu există în `§6.1`.** Sarcinile F0.1–F0.10 presupun un proiect Django care rulează.
   Acesta nu există. F0.0 este scheletul minim necesar; nu rearanjează ordinea, o precedă.
2. **F0.11 nu există în `§6.1`**, dar „modelul de volum de date este livrat" apare în criteriul de
   ieșire din F0 (eroarea E-4 din `00-inventory.md`). Îl adaug ca sarcină, la final, pentru că
   nimic din F0 nu depinde de el.

---

## F0.0 — Schelet de proiect

> Ambele decizii care blocau F0.0 s-au închis: versiunile prin
> [ADR-005](../decisions/005-stack-versions.md), tooling-ul prin
> [ADR-011](../decisions/011-tooling-python.md).

### F0.0.1 — Dependențe și tooling

- **Obiectiv:** proiectul are un manifest de dependențe, un linter, un formatter și un type checker,
  toate rulabile local și în CI.
- **Fișiere:** `backend/pyproject.toml`, `.pre-commit-config.yaml`, `Makefile` (țintele `lint`,
  `test`)
- **Depinde de:** —
- **Review:** —
- **Terminat:** `make lint` rulează și trece pe un repo gol; versiunile sunt fixate, nu deschise.
- **Blocat de:** — *(OD-14 prin [ADR-005](../decisions/005-stack-versions.md): Django 5.2 LTS,
  Python 3.13, PostgreSQL 18, Node 24 LTS; OD-15 prin
  [ADR-011](../decisions/011-tooling-python.md): uv, ruff, pytest, mypy strict selectiv)*
- **Livrat:** `backend/pyproject.toml`, `backend/.python-version`, țintele `sync`, `lint`, `format`,
  `typecheck`, `test` din `Makefile`
- **Livrat suplimentar:** `backend/uv.lock` (57 KB) — Python 3.13.15, Django 5.2.17, psycopg 3.3.4,
  Celery 5.6.3, DRF 3.18.0, ruff 0.16.4, mypy 2.3.1, pytest 9.1.1
- **Verificat:** `uv run ruff check` trece curat; flagurile de strictețe per-modul funcționează
  (probate izolat, fără pluginul Django). `mypy` complet și `pytest` rămân blocate de **F0.0.2** —
  ambele cer `config.settings.dev`, care nu există

### F0.0.2 — Proiect Django și Celery ✔

- **Obiectiv:** există un proiect Django care pornește, cu setări separate pe medii și cu aplicația
  Celery configurată.
- **Fișiere:** `backend/manage.py`, `backend/config/settings/{base,dev,staging,prod}.py`,
  `backend/config/{urls,celery,wsgi}.py`
- **Depinde de:** F0.0.1
- **Review:** —
- **Terminat:** `manage.py check` — zero probleme; `ruff` curat; `mypy` — 14 fișiere, zero erori;
  `pytest` colectează; aplicația Celery se încarcă cu configurarea corectă. Niciun app de business
  înregistrat. **Verificat end-to-end:** Django se conectează ca `evidenta_app` la o bază cu
  bootstrap-ul aplicat, iar `app.current_tenant_id()` ridică excepție fără context și returnează
  valoarea cu context.
- **Blocat de:** —

> **Două decizii luate aici, ambele consemnate în cod, nu doar făcute:**
>
> **`django.contrib.auth` nu este instalat.** Ar aduce `Group` și `Permission` — un model de
> autorizare întreg — în timp ce vocabularul de roluri este decizie deschisă (`DN-08`). Instalarea
> l-ar închide accidental. În plus, `auth_user`, `auth_group` și `auth_permission` **nu** se
> potrivesc tiparului `django_*` din lista de excepții, deci suita 2 ar eșua pe ele — iar remediul
> greșit (lărgirea listei) e mai ușor decât cel corect. Se reia la F0.3.7.
>
> **Două conexiuni la aceeași bază:** `default` ca `evidenta_app`, `migration` ca `evidenta_owner`.
> Migrațiile rulează explicit cu `--database=migration`. Fără separare, R5 ar fi o intenție.

### F0.0.3 — Imagini de container

- **Obiectiv:** backend, worker și frontend pornesc din `docker compose --profile app`.
- **Fișiere:** `infra/docker/backend.Dockerfile`, `infra/docker/frontend.Dockerfile`
- **Depinde de:** F0.0.2
- **Review:** —
- **Terminat:** `docker compose --profile app up` pornește toate serviciile cu healthcheck verde.
  *Este sarcină de producție și CI, nu de dezvoltare locală: local se rulează nativ, prin `make
  setup` (vezi `README.md`).*
- **Blocat de:** —

### F0.0.4 — CI ✔

- **Obiectiv:** fiecare commit rulează lint, teste și, de la F0.2, ambele suite de izolare, sub
  rolul de aplicație.
- **Fișiere:** `infra/ci/*`
- **Depinde de:** F0.0.2
- **Review:** —
- **Terminat:** un commit de probă declanșează pipeline-ul; jobul de izolare eșuează explicit cu
  „suite absente", nu tăcut.
- **Blocat de:** OD-16

### F0.0.5 — Contracte de dependență între module ✔

- **Obiectiv:** regulile D1–D6 din `CLAUDE.md` sunt verificate mecanic, nu prin convenție.
- **Fișiere:** `infra/modules/dependencies.toml`, `backend/tests/deps_guard/`, ținta `make
  deps-check`, pasul din jobul rapid de CI
- **Depinde de:** F0.0.1, F0.0.4
- **Review:** —
- **Terminat:** `make deps-check` trece; un import deliberat interzis, adăugat temporar, îl face să
  eșueze.
- **Blocat de:** — *(OD-17 prin [ADR-024](../decisions/024-gardian-de-dependente.md): gardian
  propriu, în suită, nu `import-linter`)*
- **Livrat:** gardian AST cu contract citit dintr-un singur fișier; `D0` (pachet nedeclarat), `DG`,
  `D1`–`D6`. 19 teste, fiecare regulă cu probă că poate eșua, ~0,1 s, fără bază de date
- **Verificat:** criteriul „un import interzis îl face să eșueze" nu e ipotetic — fiecare regulă are
  proba ei pe o ierarhie de fișiere construită pentru ea. Peste ele, gardianul a prins la prima
  rulare pe arborele real două chei străine scrise în aceeași oră, ceea ce a schimbat forma
  excepției `D6` (vezi ADR-024)

---

## F0.1 — Roluri de bază de date și infrastructură RLS

> Primul lucru, înaintea oricărui model. Django presupune implicit un singur utilizator de bază de
> date cu drepturi complete; dacă acest pas se sare, RLS va fi activat și complet inefectiv.

### F0.1.0 — Baza și verificarea colației

- **Obiectiv:** baza există cu provider ICU și colația `ro`, iar o bază creată greșit oprește
  lanțul înainte să se construiască ceva peste ea.
- **Fișiere:** `infra/bootstrap/0000_locale_guard.sql` ✔, ținta `create-db` din `Makefile` ✔,
  `POSTGRES_INITDB_ARGS` în `docker-compose.yml` ✔
- **Depinde de:** —
- **Review:** `schema-reviewer`
- **Terminat:** o bază cu provider `libc` oprește lanțul cu eroare explicită; una cu `ro-x-icu` trece
  cu avertisment; una cu `ro` trece curat. **Verificat pe toate trei pe PostgreSQL 18.6.**
- **Blocat de:** —

> Colația nu se poate corecta printr-o migrare. Verificarea rulează prima tocmai pentru că e
> singurul moment în care greșeala mai e ieftină.

### F0.1.1 — Roluri și granturi

- **Obiectiv:** rolul de migrare deține obiectele, rolul de aplicație nu, și aplicația rulează sub
  al doilea.
- **Fișiere:** `backend/config/db_roles.sql`, `infra/bootstrap/0001_roles.sql`,
  `backend/config/settings/base.py` (conexiuni)
- **Depinde de:** F0.0.2
- **Review:** `schema-reviewer`
- **Terminat:** `SELECT current_user` din aplicație returnează rolul de aplicație; rolul de
  aplicație nu are `BYPASSRLS` și nu deține nicio tabelă (verificat prin interogare, nu prin
  inspecție vizuală).
- **Blocat de:** —

### F0.1.2 — Funcțiile de context, fail-closed

- **Obiectiv:** contextul de tenant se citește din sesiune și absența lui produce eroare, nu acces.
- **Fișiere:** `infra/bootstrap/0002_app_context.sql` (schemele `app` și `rls`,
  `current_tenant_id`, `current_user_id`, `current_actor_firm_id`)
- **Depinde de:** F0.1.1
- **Review:** `tenancy-guard`, `schema-reviewer`
- **Terminat:** apelul funcției fără context ridică excepție cu cod stabil; cu context, returnează
  valoarea. Test dedicat, sub rolul de aplicație.
- **Blocat de:** — *(deblocată: ADR-004; `app.current_company_id()` returnează `NULL` la lipsă, spre deosebire de `current_tenant_id()`)*

### F0.1.3 — Predicatele de acces

- **Obiectiv:** cele două căi de acces — membru al tenantului și engagement activ — sunt exprimate
  într-un singur loc, folosibil de toate politicile.
- **Fișiere:** `infra/bootstrap/0003_access_predicates.sql`
- **Depinde de:** F0.1.2
- **Review:** `tenancy-guard`, `schema-reviewer`
- **Terminat:** funcțiile există, sunt `SECURITY DEFINER` cu `search_path` fixat, și au teste
  proprii care acoperă: membru activ, membru suspendat, engagement activ, expirat, revocat, firmă
  nerevendicabilă.
- **Blocat de:** — *(deblocată: [ADR-003](../decisions/003-rls-tenancy-tables.md) și [ADR-004](../decisions/004-company-context.md))*

> Aceste funcții sunt singurul loc din sistem unde o greșeală deschide toate datele tuturor
> tenanților. Testele lor nu sunt parte din suita de izolare; sunt suplimentare.

### F0.1.4 — Middleware de tranzacție și context ✔

- **Obiectiv:** fiecare request rulează într-o tranzacție cu context setat prin `SET LOCAL`, sau
  este refuzat.
- **Fișiere:** `backend/evidenta/platform/rls/{context,guard,apps,middleware}.py`,
  `backend/config/settings/base.py`, `backend/tests/isolation/manual_context_probe.py`
- **Depinde de:** F0.1.2
- **Review:** `tenancy-guard`
- **Terminat:** testul demonstrează că **nu există cale de acces la date fără context**, enumerând
  căile care ocolesc middleware-ul și verificând că fiecare eșuează:
  - viziune care interoghează înainte de deschiderea tranzacției
  - `StreamingHttpResponse` care produce rânduri după commit
  - comandă de management
  - shell Django
  - `SET` fără `LOCAL`, interzis de lint (IZ-35)

  Plus IZ-30…IZ-34 și IZ-38.
- **Blocat de:** —
- **Livrat și verificat** pe PostgreSQL 18.6 / Django 5.2.17, opt verificări, toate PASS:
  interogare fără context → `MissingTenantContextError`; tranzacție fără context → tot refuzată;
  în context → trece, iar baza vede același tenant; după ieșire → refuzată din nou; context setat
  în afara tranzacției → `OutsideTransactionError`; `unguarded('motiv')` permite; conexiunea de
  migrare nu e păzită; resolverul implicit refuză. Verificat separat că garda e activă și pe calea
  de **shell** și pe cea de **comandă de management**.

> **Cum se obține garanția.** Un `execute_wrapper` instalat prin `AppConfig.ready()` refuză orice
> interogare pe conexiunea de aplicație în afara unui context. Nu înlocuiește RLS și nu e control
> de securitate — un proces compromis îl poate scoate. Prinde mai devreme și cu mesaj lizibil exact
> clasa de bug pentru care există RLS: calea accidentală către date fără context. Baza refuză când
> se evaluează o politică, deci doar pe tabele protejate; garda refuză la prima interogare, orice
> ar atinge, și spune care cale a produs-o.

> **Două detalii care par mărunte și nu sunt.** Contextul se setează prin
> `SELECT set_config(%s, %s, true)`, nu prin `SET LOCAL` cu interpolare — `SET` nu acceptă
> parametri, deci varianta naivă construiește SQL prin concatenare din valori venite din request.
> Iar `_apply` refuză dacă nu e într-o tranzacție: `SET LOCAL` în afara uneia nu e „mai puțin sigur",
> e fără efect, și fiecare interogare ulterioară ar rula fără context.

> **Forma slabă, de refuzat la review.** Un test care setează contextul, interoghează și verifică
> rezultatul corect trece verde fără să demonstreze nimic: arată că *funcționează cu* context, nu că
> *nu funcționează fără*. A doua e cerința. Sarcina nu e terminată cu prima.

> Aceeași observație, pusă altfel: dacă testul nu conține niciun caz care se așteaptă să **eșueze**,
> nu testează izolarea.

### F0.1.5 — Context pentru task-uri Celery ✔

- **Obiectiv:** fiecare task primește `tenant_id` explicit și setează contextul înainte de orice
  interogare. **Absența contextului produce eșec zgomotos, nu rezultat gol.**
- **Fișiere:** `backend/evidenta/platform/rls/tasks.py`, `backend/tests/isolation/manual_task_probe.py`
- **Depinde de:** F0.1.4
- **Review:** `tenancy-guard`
- **Terminat:** IZ-40…IZ-45, cu accent pe forma eșecului:
  - task fără `tenant_id` → **excepție la pornire**, înainte de orice interogare
  - task care interoghează înainte de a seta contextul → excepție, nu zero rânduri
  - două task-uri consecutive pe același worker, tenanți diferiți → contextul primului nu se scurge
  - eșec și retry → contextul se curăță pe ambele căi
  - task cu utilizator de sistem, fără `membership` → zero acces pe calea normală *(se activează
    la F0.3.2, când există `membership`)*
- **Blocat de:** —
- **Livrat și verificat**, 11 verificări toate PASS pe PostgreSQL 18.6 / Celery 5.6.3:
  fără `tenant_id` → `MissingTenantArgumentError`, **și niciun query emis înainte de refuz**;
  fără `user_id` → refuzat (nu există cale anonimă); apel pozițional incomplet → prins la fel;
  task în context → vede tenantul primit; task fără decorator → refuzat de gardă; două task-uri
  consecutive → fiecare cu tenantul lui, fără scurgere; contextul nu supraviețuiește task-ului;
  cale de eroare și **cale de retry cu `bind=True`** → context curățat pe amândouă.

> **Verificarea care contează cel mai mult** nu e că refuză, ci **când**: proba numără interogările
> emise și confirmă că sunt zero înainte de excepție. Un decorator care refuză *după* ce a atins
> baza ar fi trecut testul „refuză" și ar fi ratat exact scopul.

> **De ce argumentele se leagă prin semnătura reală** (`inspect.signature(...).bind_partial`), nu
> citind `kwargs`: o verificare pe `kwargs` e ocolită tăcut de `task.delay(tid, uid)`. Apelul
> pozițional este verificat explicit în probă.

> **`bind=True` are verificare proprie.** Retry-ul îl cere, iar retry-ul îl cer toate task-urile
> care vorbesc cu SFS sau cu o bancă. Un decorator care ar fi mers doar în forma simplă ar fi făcut
> decoratorul inutilizabil exact pentru task-urile cu cel mai mare risc.

> **Forma slabă, de refuzat la review.** Un decorator care, la `tenant_id` lipsă, lasă interogarea
> să ruleze și se bazează pe RLS ca să returneze zero rânduri **trece toate testele de izolare** —
> nu se scurge nicio dată. Și e greșit: un task de amortizare care rulează pe zero rânduri raportează
> succes și nu postează nimic. Defectul se descoperă la închiderea lunii, nu în CI.
>
> Regula: **fail-closed nu e suficient; trebuie și fail-loud.** Testul verifică tipul excepției, nu
> doar că nu s-au returnat date.

> Măsurat deja, ca precedent: fără `BYPASSRLS` pe rolul de rezolvare, sistemul eșuează exact așa —
> corect și complet tăcut ([ADR-003](../decisions/003-rls-tenancy-tables.md), „Verificat empiric",
> punctul 2). Acela e tiparul de evitat, nu unul teoretic.

### F0.1.6 — Aplicarea SQL-ului manual

- **Obiectiv:** politicile RLS și rolurile se aplică determinist, în ordine, împreună cu migrațiile
  Django.
- **Fișiere:** `backend/evidenta/platform/rls/sql.py` ✔, `infra/migrations/README.md` ✔,
  `infra/bootstrap/README.md` ✔, țintele `bootstrap` și `migrate` din `Makefile` ✔
- **Depinde de:** F0.1.1
- **Review:** `schema-reviewer`
- **Terminat:** o bază goală ajunge la starea completă prin `make migrate`; ordinea e
  reproductibilă; o tabelă nouă fără politică este imposibil de introdus fără ca suita 2 să
  eșueze; un fișier SQL modificat după aplicare face să eșueze **orice** comandă `manage.py`.
- **Blocat de:** — *(OD-18 prin [ADR-012](../decisions/012-sql-in-django-migrations.md))*
- **Rămas:** helperul nu a fost executat — cere Django instalat (`uv.lock`). Sintaxa e validată,
  calea către `infra/migrations/` e verificată, comportamentul nu.

---

## F0.2 — Suitele de verificare

> Înaintea modelelor, nu după. Suitele se scriu **roșii**: cazurile care depind de entități
> inexistente eșuează, iar asta este comportamentul corect. Se activează pe măsură ce entitățile
> apar în F0.3–F0.7.

> **Regula de migrare — îndeplinită.** Toate cele trei probe au fost retrase, fiecare când propriile
> ei scenarii au avut echivalente care trec. Maparea probei SQL, verificabilă prin `grep`:
>
> | Scenariu | Echivalent |
> |---|---|
> | IZ-01, IZ-03, IZ-08 | `test_tenant_isolation.py` |
> | IZ-10, IZ-11, IZ-18 | `test_engagement_access.py` |
> | IZ-30 | `test_context_enforcement.py` |
> | IZ-50 | `test_company_access.py` |
>
> Fiecare test citează identificatorul în docstring, deci maparea nu depinde de memoria cuiva.
> Proba din `infra/rls/smoke_test.sql` acoperă azi șapte scenarii, verificate pe PostgreSQL 18.6:
> **IZ-01, IZ-03, IZ-08, IZ-10, IZ-11, IZ-18, IZ-30, IZ-50.**
> **F0.2 nu este terminată până când fiecare dintre ele are echivalent Python care trece.**
> Varianta SQL se șterge **abia atunci, într-un singur commit** — același commit care adaugă
> echivalentele, ca diferența să fie vizibilă la review.
>
> Motivul: momentul migrării este locul clasic unde se pierde acoperire. Se rescriu cinci din
> șapte scenarii, restul „se fac mai târziu", și nimeni nu observă — pentru că suita nouă e verde.
> O suită verde care acoperă mai puțin decât cea pe care o înlocuiește este o regresie deghizată
> în progres.

### F0.2.1 — Harness sub rolul de aplicație ✔

- **Obiectiv:** testele de izolare rulează sub rolul de aplicație și refuză să ruleze altfel.
- **Fișiere:** `backend/tests/conftest.py`, `backend/tests/isolation/conftest.py`
- **Depinde de:** F0.1.1
- **Review:** `tenancy-guard`
- **Terminat:** rularea ca superuser sau owner oprește suita cu eroare explicită (IZ-74); rolul
  efectiv este verificat prin interogare la pornire.
- **Livrat:** `backend/tests/conftest.py`, `backend/tests/test_harness.py`. **Verificat:** 5 teste
  de auto-probare trec; rulat ca `evidenta_owner` → suita **refuză**; rulat ca `postgres` → refuză
  enumerând toate patru motivele (rol greșit, superuser, BYPASSRLS, deține 68 de tabele).

> **Trei privilegii, nu două.** Constrângerea era că `evidenta_app` e `NOCREATEDB` intenționat, iar
> `pytest-django` creează baza prin conexiunea `default`. Ieșirea comodă — `default` pe owner
> pentru teste — trece verde și nu demonstrează nimic: owner-ul e supus politicilor doar prin
> `FORCE ROW LEVEL SECURITY`, deci un singur `FORCE` uitat ar face toată suita să treacă pe o
> tabelă neprotejată. Harness-ul separă: **admin** (superuser, doar infrastructură de test) creează
> baza, **owner** aplică bootstrap-ul și migrațiile, **app** rulează testele.
>
> Adminul vine din variabile proprii, nu din `evidenta_owner` cu `CREATEDB` adăugat — o nevoie de
> test nu lărgește un rol de producție.

> **Bootstrap-ul se aplică prin `psql`**, exact cum face `make bootstrap`. Fișierele folosesc
> variabile psql și `\set ON_ERROR_STOP`; aplicate altfel, testele ar exercita altă cale de
> bootstrap decât cea reală, iar un bootstrap stricat ar trece neobservat.

> **Garda păzește corpul testului, nu infrastructura.** Curățenia făcută de pytest la teardown nu
> are tenant și nici nu va avea. O gardă care ar poliția-o ar face testele tranzacționale
> imposibil de rulat — și așa se șterge o verificare utilă.
- **Blocat de:** —

### F0.2.2 — Suita 2, gardian de model ✔

- **Obiectiv:** orice tabelă fără context de tenant, fără politică RLS sau fără
  `FORCE ROW LEVEL SECURITY` face CI să eșueze.
- **Fișiere:** `backend/tests/schema_guard/audit.py` (auditul), `test_model_guard.py` (regulile +
  auto-proba), `infra/rls/exceptions.toml`, `infra/schema/append_only.toml`
- **Depinde de:** F0.2.1
- **Review:** `tenancy-guard`, `schema-reviewer`
- **Terminat:** acoperă IZ-70…IZ-77; o tabelă de probă fără `tenant_id` face suita să eșueze; lista
  de excepții trăiește într-un singur loc, `infra/rls/exceptions.toml`.
  **Plus verificarea colației (`C34`, ADR-015), în ambele sensuri:** o coloană de denumire cu
  `COLLATE "C"` eșuează; o coloană de cod fără colație explicită eșuează. Locul potrivit este
  gardianul de model, nu suita de penetrare: nu e o problemă de izolare, e o proprietate a schemei,
  iar ordonarea greșită nu produce eroare — deci nu o prinde niciun test funcțional.
- **Blocat de:** — *(deblocată: lista trăiește în `infra/rls/exceptions.toml`, ADR-003)*

### F0.2.3 — Suita 1, penetrare de bază *(parțial)*

- **Obiectiv:** un tenant nu poate atinge datele altuia prin nicio cale directă.
- **Fișiere:** `backend/tests/isolation/test_cross_tenant_read.py`, `test_cross_tenant_write.py`,
  `test_missing_context.py`
- **Depinde de:** F0.2.1
- **Review:** `tenancy-guard`
- **Terminat:** acoperă IZ-01…IZ-08, IZ-30…IZ-38, IZ-50…IZ-53. **Include și echivalentele pytest
  pentru cele opt verificări din `backend/tests/isolation/manual_context_probe.py`**, care se șterge
  în același commit — aceeași regulă ca pentru proba SQL, din același motiv. Cazurile care cer entități
  inexistente sunt marcate ca așteptate-să-eșueze, cu trimitere la sarcina care le activează.
  **Migrat deja:** cele opt verificări din `manual_context_probe.py` și cele douăsprezece din
  `manual_task_probe.py` au echivalente pytest care trec; ambele fișiere au fost **șterse în aceeași
  schimbare**, conform regulii. Rămâne de migrat `infra/rls/smoke_test.sql` — cere tabelele de
  tenancy, deci **F0.3**.
- **Blocat de:** —

### F0.2.4 — Suita 1, cazurile de engagement

- **Obiectiv:** engagementul expirat, revocat sau cu scope restrâns nu dă acces.
- **Fișiere:** `backend/tests/isolation/test_engagement_access.py`, `test_engagement_scope.py`
- **Depinde de:** F0.2.3, F0.3.3, F0.3.4
- **Review:** `tenancy-guard`
- **Terminat:** acoperă IZ-10…IZ-21 și IZ-25…IZ-29, toate verzi.
- **Blocat de:** — *(`DN-06` prin [ADR-018](../decisions/018-engagementuri-multiple.md), `DN-07` prin [ADR-019](../decisions/019-vocabular-scope.md))*

### F0.2.5 — Suita 1, task-uri Celery

- **Obiectiv:** un task fără context eșuează, nu returnează date.
- **Fișiere:** `backend/tests/isolation/test_celery_context.py`
- **Depinde de:** F0.2.1, F0.1.5
- **Review:** `tenancy-guard`
- **Terminat:** acoperă IZ-40…IZ-45.
- **Blocat de:** —

### F0.2.6 — Integrarea în CI și retragerea probei SQL ✔

- **Obiectiv:** ambele suite rulează la fiecare commit, sub rolul de aplicație.
- **Fișiere:** `infra/ci/*`, `Makefile` (ținta `isolation-check`)
- **Depinde de:** F0.2.2, F0.2.3, F0.0.4
- **Review:** —
- **Terminat:** `make isolation-check` rulează ambele suite și raportează separat; pipeline-ul
  eșuează dacă oricare eșuează. **Toate cele opt scenarii din proba SQL au echivalent Python care
  trece**, iar `infra/rls/smoke_test.sql` și `smoke_fixture.sql` se șterg în acest commit.
- **Blocat de:** OD-16

---

## F0.3 — Tenancy și identitate

> Conform Spec A. Fiecare sarcină de aici adaugă tabele; fiecare tabelă adaugă politici în aceeași
> sarcină. O tabelă și politica ei nu se separă în două commituri.

### F0.3.1 — `Tenant` și `Company` ✔

- **Obiectiv:** rădăcina de tenancy și entitatea juridică cu ledger propriu există, cu politici RLS.
- **Fișiere:** `backend/evidenta/platform/tenancy/models.py`, `migrations/0001_initial.py`,
  `infra/migrations/0010_tenancy_policies.sql`
- **Depinde de:** F0.1.3, F0.2.2
- **Review:** `tenancy-guard`, `schema-reviewer`
- **Terminat:** suita 2 trece cu cele două tabele prezente; `company_vat_registration` are
  constrângere de neîntrepătrundere; subdomeniul respectă formatul și lista de rezervate.
- **Blocat de:** DN-02, DN-03 *(DN-12 închisă prin ADR-003)*

### F0.3.2 — `User` și `Membership` ✔

- **Obiectiv:** identitatea globală și apartenența la tenant există, cu indicii pe care se sprijină
  predicatele.
- **Fișiere:** `backend/evidenta/platform/identity/models.py`, `migrations/`,
  `infra/migrations/0011_identity_policies.sql`
- **Depinde de:** F0.3.1
- **Review:** `tenancy-guard`, `schema-reviewer`
- **Terminat:** `user` nu are `tenant_id` și apare în lista de excepții; `membership (user_id,
  status)` există; predicatele din F0.1.3 devin verzi pe calea 1.
- **Blocat de:** — *(DN-12 închisă prin ADR-003)*

### F0.3.3 — `Firm`, `Engagement` și scope ✔

- **Obiectiv:** relația delegată firmă → tenant există, cu valabilitate, stare și scope.
- **Fișiere:** `backend/evidenta/platform/engagement/models.py`, `migrations/`,
  `infra/migrations/0012_engagement_policies.sql`
- **Depinde de:** F0.3.2
- **Review:** `tenancy-guard`, `schema-reviewer`
- **Terminat:** predicatele devin verzi pe calea 2; un engagement expirat nu dă acces **fără** ca
  vreun job să fi rulat (IZ-11).
- **Blocat de:** — *(`DN-06` prin [ADR-018](../decisions/018-engagementuri-multiple.md), `DN-07` prin [ADR-019](../decisions/019-vocabular-scope.md); `DN-12` prin ADR-003)*

### F0.3.4 — `CompanyAccess` și revocarea în cascadă ✔

- **Obiectiv:** accesul la companie există și nu supraviețuiește relației care l-a produs.
- **Fișiere:** `backend/evidenta/platform/engagement/services/revocation.py`,
  `platform/identity/models.py` (CompanyAccess), migrații
- **Depinde de:** F0.3.3
- **Review:** `tenancy-guard`, `accounting-reviewer` *(nu are efect financiar, dar atinge
  trasabilitatea — se invocă doar dacă apar evenimente)*
- **Terminat:** șase teste. Apartenența la tenant **nu** e acces la companie; `company_access` dă
  acces exact la o companie; IZ-50 (inserare într-un tenant străin) refuzată; revocarea unui
  engagement stinge accesele derivate în aceeași tranzacție (IZ-19); revocarea a doua oară e
  refuzată; calea privilegiată refuză un apelant fără drept.
- **Nelivrat, marcat explicit:** evenimentele de audit la revocare (F0.4) și invalidarea sesiunilor
  (IZ-20, cere F0.3.7). Ambele scrise în docstring-ul serviciului, nu omise tăcut.
- **Blocat de:** —

> **Politica `self_row` are o consecință pe care revocarea o lovește direct:** un administrator nu
> poate revoca accesul altcuiva prin ORM — rândurile altor utilizatori îi sunt invizibile. Nu e o
> scăpare, e forma aplicată consecvent. Dar accesul nu are voie să supraviețuiască relației care
> l-a produs, deci cascada trece printr-o **funcție `SECURITY DEFINER` îngustă**: nu primește nume
> de tabele, nu acceptă SQL, revocă doar accesele unui engagement anume, și **verifică dreptul
> apelantului prin același predicat ca politica de pe `engagement`**. Ultima condiție e cea care o
> face cale, nu portiță — testată separat.

> **Funcția stă în schema `rls`, nu în `app`.** Prima încercare a eșuat: o funcție `SECURITY
> DEFINER` trebuie deținută de rolul sub care vrem să ruleze, iar `app` e deținută de
> `evidenta_owner` — care, sub `FORCE ROW LEVEL SECURITY`, e supus chiar politicilor pe care
> funcția trebuie să le ocolească. Ar fi revocat zero rânduri și ar fi raportat succes.

### F0.3.5 — Rezoluția subdomeniului ✔

- **Obiectiv:** contextul de tenant vine exclusiv din subdomeniu.
- **Fișiere:** `backend/evidenta/platform/tenancy/middleware.py`, teste
- **Depinde de:** F0.3.1, F0.1.4
- **Review:** `tenancy-guard`
- **Terminat:** 15 teste. Extragerea etichetei din `Host` (12 cazuri, majoritatea malformate);
  rezoluția prin calea privilegiată; IZ-36 (tenant declarat de client, în query sau în header, care
  contrazice gazda → refuz) și IZ-37 (subdomeniu inexistent și tenant inactiv → **același** mesaj).
- **Blocat de:** OD-20 rămâne deschisă, dar nu blochează: privește doar cum se rezolvă subdomeniile
  pe `localhost`, nu mecanismul.

> **Rezoluția e anterioară contextului, prin natura ei.** Ca să afli ce tenant e, trebuie să
> citești `tenant` — a cărui politică cere deja `app.current_tenant_id()`. Deci o cale privilegiată
> îngustă: o funcție care primește un subdomeniu și întoarce identificatorul și starea. Nimic
> altceva. Divulgă existența unui subdomeniu, care e oricum observabilă din DNS; nu divulgă
> denumirea juridică, contactul sau numărul de companii.

> **Garda de interogare a găsit singură excepția.** Rezolvatorul rulează înainte de context, deci
> garda l-a refuzat — corect. E singurul loc din calea de request care numește `unguarded`, cu
> motivul scris. Exact comportamentul care justifică garda: excepția a trebuit **declarată**, nu
> presupusă.

> **A treia oară cu `evidenta_rls`:** are `BYPASSRLS` dar niciun privilegiu de tabelă. Funcția
> ocolea politicile și era tot refuzată la tabelă. Cele două sunt mecanisme diferite și se confundă
> ușor — `BYPASSRLS` spune „politicile nu se aplică", `GRANT` spune „ai voie să atingi tabela".

> **Un caz care merită numit:** `notevidenta.md` se termină cu `evidenta.md`. Un test naiv cu
> `endswith` ar da o etichetă de tenant oricui înregistrează domeniul vecin. Verificarea e pe
> sufixul cu punct, și are test propriu.

### F0.3.6 — Ciclul de viață al engagementului ✔

- **Obiectiv:** invitație, acceptare, suspendare, revocare, transfer funcționează conform matricei
  de tranziții.
- **Fișiere:** `backend/evidenta/platform/engagement/services/lifecycle.py`, teste
- **Depinde de:** F0.3.4
- **Review:** `tenancy-guard`
- **Terminat:** 12 teste. Matricea din Spec A §4.2 e **date, nu ramuri**: o pereche absentă se
  refuză, iar adăugarea uneia e o editare vizibilă în tabel. Fiecare refuz are cod stabil (C10).
  Transferul nu mută date.
- **Blocat de:** — *(DN-13, DN-14 și DN-15 rămân deschise, dar fiecare are un răspuns fail-closed
  implementat, nu o presupunere)*

> **Ce fac deciziile deschise, concret:**
> - `DN-14` (poate firma revoca unilateral?) — firma **nu** e în lista de actori pentru revocare.
>   Refuzul e răspunsul sigur: o firmă care nu poate revoca e o neplăcere, una care revocă când nu
>   trebuia e un client fără contabil în ziua depunerii.
> - `DN-13` (expirarea invitațiilor) — invitația nu primește termen. Ocupă slotul dintre firmă și
>   tenant, dar nu acordă nimic.
> - `DN-15` (suprapunerea la transfer) — transferul e **succesiune**, cum fixează ADR-018 până la
>   închiderea deciziei. Ordinea contează: engagementul care pleacă eliberează modulele înainte ca
>   cel care vine să le revendice; invers, indexul de nesuprapunere ar refuza chiar transferul pe
>   care există să-l facă ordonat.

> **Partea care sună evident și nu e:** cel care invită nu poate accepta. O invitație pe care o
> firmă și-o trimite și și-o acceptă nu e delegare, iar modelul n-ar mai putea spune ulterior dacă
> clientul a fost vreodată de acord.

> **`mark_expired` mută eticheta, nu taie accesul** — acesta încetase deja, prin predicat. Testul
> afirmă ambele lucruri împreună, deliberat: dacă cineva face vreodată accesul să depindă de job,
> a doua jumătate a testului e cea care cade.

### F0.3.7 — Autentificare

- **Obiectiv:** utilizatorii se autentifică, cu MFA conform politicii alese.
- **Fișiere:** `backend/evidenta/platform/identity/auth/`, endpoint-uri, teste
- **Depinde de:** F0.3.2
- **Review:** `tenancy-guard`
- **Terminat:** conturile cu drept de revocare a engagementului sau de redeschidere a perioadei nu
  pot funcționa fără MFA; rate limiting activ pe autentificare.
- **Blocat de:** — *(`DN-08` prin [ADR-020](../decisions/020-roluri-ca-date.md), `DN-09` prin
  [ADR-021](../decisions/021-mfa-obligatoriu.md))*

> **Împărțită în două, fiindcă ADR-020 aduce un model întreg înaintea autentificării:**
>
> **F0.3.7a — modelul de roluri ✔.** `permission` (catalog global, alimentat din cod), `role` și
> `role_permission` per tenant; `membership.role` și `company_access.role` au devenit chei străine.
> Trei protecții, fiecare acolo unde nu poate fi ocolită: chei străine **compuse** pentru granița de
> tenant și potrivirea de nivel, triggere pentru rolurile de sistem, serviciu pentru ultimul
> administrator. 12 teste noi.
>
> **F0.3.7b — autentificare și MFA.** Parolă, TOTP, coduri de rezervă, recuperare prin al doilea
> administrator, rate limiting, regula „ultimul `owner` nu poate rămâne fără MFA" (ADR-021).

---

## F0.4 — Audit

### F0.4.1 — `audit_event` ✔

- **Obiectiv:** există o tabelă de audit append-only, de volum mare, conform disciplinei R21–R22.
- **Fișiere:** `backend/evidenta/platform/audit/models.py`, migrații,
  `infra/migrations/0020_audit_policies.sql`
- **Depinde de:** F0.3.2
- **Review:** `schema-reviewer`, `tenancy-guard`
- **Terminat:** `occurred_at NOT NULL`; cheie primară `bigint`; **nicio** cheie străină nu arată
  spre ea (verificat de IZ-77); politica RLS activă.
- **Blocat de:** —

> **Notă ulterioară (`OD-43`).** `actor_user_id` este `NOT NULL`, iar asta e corect și pentru cazul
> în care munca o face un asistent automat: asistentul este instrument, nu actor — răspunde omul
> care l-a activat. Ce lipsește pentru a putea răspunde la „ce a făcut asistentul" este o coloană
> nulabilă către activarea capabilității, de aceeași formă cu `actor_firm_id`. Este ieftină cât
> tabela e goală în producție; după, e migrare pe o tabelă append-only de volum mare.

### F0.4.2 — Captarea evenimentelor ✔

- **Obiectiv:** acțiunile cu efect asupra datelor produc evenimente de audit, explicit, din servicii.
- **Fișiere:** `backend/evidenta/platform/audit/services.py`, integrare în serviciile din F0.3
- **Depinde de:** F0.4.1
- **Review:** `tenancy-guard`
- **Terminat:** niciun signal Django folosit (C4); fiecare tranziție de engagement și fiecare
  modificare de acces produce un rând.
- **Blocat de:** —

### F0.4.3 — Corelatorul și enumerarea efectelor ✔

- **Obiectiv:** efectele unei sesiuni, ale unui utilizator sau ale unui interval se pot enumera
  complet.
- **Fișiere:** `backend/evidenta/platform/audit/services/enumeration.py`, propagarea `request_id`
  în middleware și în decoratorul Celery, teste
- **Depinde de:** F0.4.2, F0.1.4, F0.1.5
- **Review:** `tenancy-guard`
- **Terminat:** interogarea din Spec A §9.3 returnează mulțimea completă a efectelor pentru un
  interval dat, cu indexul care o susține prezent.
- **Blocat de:** DN-20

> Această sarcină este ce face refuzul cererii „restaurează-mi compania la starea de vineri" onest.
> Fără ea, produsul refuză fără să ofere alternativa.

> **Livrat, 9 teste.** Append-only impus prin **absența grantului**, nu prin trigger: spre deosebire
> de ledger (R10), unde există o tranziție legitimă de protejat (`draft → posted`), aici nu există
> niciuna — deci lipsa lui `UPDATE`/`DELETE` e suficientă și mai ieftină decât un trigger pe fiecare
> scriere din sistem. Testat că ambele sunt refuzate.
>
> **Politica de inserare cere `actor_user_id = app.current_user_id()`.** Fără ea, un utilizator ar
> putea scrie în audit o acțiune atribuită unui coleg — exact falsificarea împotriva căreia există
> auditul. Testat.
>
> **`actor_firm_id` e coloana care face „cine a avut acces în martie 2027" un răspuns.** Fără ea,
> actorul e un id de utilizator fără relație, iar după ce firma dispare nu mai există din ce
> reconstrui.
>
> **Enumerarea grupează pe `request_id`**, nu pe rând: o cerere e un act, iar stornarea unei jumătăți
> de act e mai rea decât a niciuneia. Transferul între firme e cazul care o demonstrează — două
> rânduri, un singur act.
>
> `DN-20` rămâne deschisă (granularitatea sesiunii). Implementat `request_id`, care e opțiunea A;
> adăugarea unui `session_id` rămâne aditivă.

---

## F0.5 — Capabilități și feature flags

### F0.5.1 — `CapabilityActivation`

- **Obiectiv:** activarea unei capabilități este entitate cu dată efectivă și stare de inițializare.
- **Fișiere:** `backend/evidenta/platform/capabilities/models.py`, `services.py`, migrații, politici
- **Depinde de:** F0.3.1
- **Review:** `tenancy-guard`, `schema-reviewer`
- **Terminat:** constrângerea de neîntrepătrundere funcționează; o capabilitate de conformitate nu
  poate primi `effective_to` (test dedicat); alinierea la granița perioadei e verificată în serviciu,
  cu notă că se mută în bază la F1.5.
- **Blocat de:** DN-10 *(vocabularul de capabilități)*

> **`OD-43`.** Activarea este și răspunsul la „cine a pornit asistentul", dacă vreo capabilitate
> ajunge să acționeze în numele unui utilizator. Nu cere nimic în plus aici — cere ca `audit_event`
> să poată trimite înapoi la activare.

### F0.5.2 — Feature flags și release rings

- **Obiectiv:** diferențierea tehnică se face prin flags și ringuri, niciodată prin versiuni per
  tenant.
- **Fișiere:** `backend/evidenta/platform/flags/models.py`, `services.py`, migrații, politici
- **Depinde de:** F0.3.1
- **Review:** `tenancy-guard`, `schema-reviewer`
- **Terminat:** `feature_flag` și `release_ring` sunt globale, `tenant_release_ring` și
  `feature_flag_override` sunt tenant-scoped; fiecare override are `reason` și `expires_at`
  obligatorii.
- **Blocat de:** —

---

## F0.6 — Document core, numerotare, atașamente

### F0.6.1 — Document core

- **Obiectiv:** conceptele comune tuturor documentelor există într-un singur loc.
- **Fișiere:** `backend/evidenta/platform/documents/models.py`, migrații, politici
- **Depinde de:** F0.3.1
- **Review:** `tenancy-guard`, `schema-reviewer`
- **Terminat:** stările generice `Draft → Confirmed → Posted → Completed` sunt exprimate ca mașină
  de stări testată; câmpurile comune (număr, dată, companie, stare, valută, contraparte, sursă,
  creat de, aprobat de, stare de postare) există.
- **Blocat de:** —

### F0.6.2 — Numerotare

- **Obiectiv:** numerele de document se alocă determinist, per companie, tip, an și serie.
- **Fișiere:** `backend/evidenta/platform/numbering/models.py`, `services.py`, migrații, politici
- **Depinde de:** F0.6.1
- **Review:** `tenancy-guard`, `schema-reviewer`
- **Terminat:** alocarea concurentă a două numere nu produce duplicate (test cu tranzacții
  paralele); comportamentul la anulare este cel decis, nu cel implicit.
- **Blocat de:** **OD-02** *(per companie sau per filială — și „filiala" nu e o entitate definită)*

### F0.6.3 — Atașamente

- **Obiectiv:** fișierele se stochează izolat per tenant, cu metadate în bază.
- **Fișiere:** `backend/evidenta/platform/attachments/models.py`, `storage.py`, migrații, politici
- **Depinde de:** F0.6.1
- **Review:** `tenancy-guard`
- **Terminat:** un utilizator al tenantului A nu poate obține un URL semnat pentru un fișier al
  tenantului B (caz din IZ-06); limitele de dimensiune și tip sunt impuse la încărcare.
- **Blocat de:** DN-16, OD-14 *(providerul S3)*

### F0.6.4 — `document_events`

- **Obiectiv:** istoricul de stări al documentelor există ca tabelă append-only.
- **Fișiere:** `backend/evidenta/platform/documents/models.py` (event), migrații, politici
- **Depinde de:** F0.6.1
- **Review:** `schema-reviewer`
- **Terminat:** `occurred_at NOT NULL`, `bigint`, nicio cheie străină intrând (IZ-77).
- **Blocat de:** — *(scopul tabelei nu e descris în documentele de intrare — G-19; se specifică în
  această sarcină și se consemnează ca ADR)*

### F0.6.5 — Notificări

- **Obiectiv:** utilizatorii primesc notificări in-app și pe e-mail.
- **Fișiere:** `backend/evidenta/platform/notifications/`, migrații, politici
- **Depinde de:** F0.3.2
- **Review:** `tenancy-guard`
- **Terminat:** notificarea de revocare a engagementului (Spec A §4.6) ajunge la destinatari; nicio
  notificare nu conține date de business ale altui tenant.
- **Blocat de:** — *(modulul e marcat F0 în hartă și în V2 §10, dar nu are sarcină în `§6.1` —
  conflictul X-9)*

---

## F0.7 — Master data

### F0.7.1 — `CounterpartyRegistry`

- **Obiectiv:** registrul global după IDNO există și se poate alimenta.
- **Fișiere:** `backend/evidenta/masterdata/counterparties/models.py`, migrații, politici
- **Depinde de:** F0.2.2
- **Review:** `tenancy-guard`, `schema-reviewer`
- **Terminat:** tabelă globală, în lista de excepții; citire liberă, scriere doar prin calea
  privilegiată P-5.
- **Blocat de:** OD-12 *(efectul de rețea vs. interdicția cross-tenant)*, sursa publică de date

### F0.7.2 — `Partner`

- **Obiectiv:** partenerul la nivel de tenant există, cu legătură opțională către registru.
- **Fișiere:** `backend/evidenta/masterdata/partners/models.py`, migrații, politici
- **Depinde de:** F0.7.1
- **Review:** `tenancy-guard`, `schema-reviewer`
- **Terminat:** într-un holding, același partener se introduce o singură dată și e vizibil
  companiilor tenantului; IDNO unic per tenant.
- **Blocat de:** DN-03

### F0.7.3 — `CompanyPartner`

- **Obiectiv:** configurarea per companie a unui partener există.
- **Fișiere:** `backend/evidenta/masterdata/partners/models.py`, migrații, politici
- **Depinde de:** F0.7.2
- **Review:** `tenancy-guard`, `schema-reviewer`
- **Terminat:** conturile de creanțe și datorii se pot configura per companie; sunt câmpurile pe
  care le va consulta rezoluția de cont din Posting Engine (Spec B §3.3).
- **Blocat de:** —

### F0.7.4 — `Item` și `UnitOfMeasure`

- **Obiectiv:** nomenclatorul de articole și unitățile de măsură există, cu indicatorii care fac
  posibile loturile și seriile mai târziu.
- **Fișiere:** `backend/evidenta/masterdata/items/models.py`, `masterdata/uom/models.py`, migrații
- **Depinde de:** F0.3.1
- **Review:** `tenancy-guard`, `schema-reviewer`
- **Terminat:** articolul are indicator de urmărire pe lot și pe număr de serie, fără ca gestiunea
  loturilor să existe; conversiile între unități funcționează și sunt testate.
- **Blocat de:** —

### F0.7.5 — `Warehouse`

- **Obiectiv:** depozitul există ca model, fără funcționalitate.
- **Fișiere:** `backend/evidenta/masterdata/warehouses/models.py`, migrații, politici
- **Depinde de:** F0.3.1
- **Review:** `tenancy-guard`, `schema-reviewer`
- **Terminat:** modelul există și trece suita 2; niciun serviciu de mișcări de stoc.
- **Blocat de:** **OD-11** *(harta îl dă la F4, sarcina F0.7 îl cere în F0; regula „fără app-uri
  goale" nu spune unde locuiește)*

### F0.7.6 — Dimensiunile analitice: consemnare, nu implementare

- **Obiectiv:** lista închisă a dimensiunilor și regulile lor de obligativitate sunt fixate înainte
  ca linia de jurnal să existe.
- **Fișiere:** ADR în `docs/decisions/`, actualizare Spec B §1.7
- **Depinde de:** —
- **Review:** —
- **Terminat:** lista celor zece dimensiuni e consemnată ca decizie, cu răspunsul la DNB-02
  (dimensiuni definite de utilizator). Niciun cod.
- **Blocat de:** DNB-02

> „Dimensiuni la F0" înseamnă că linia de jurnal va avea câmpurile de la început, nu că modulul de
> centre de cost există. Linia de jurnal se creează la F1.2; ce se face acum este decizia.

---

## F0.8 — Parametri fiscali și registru

### F0.8.1 — `fiscal_parameter` și proveniența

- **Obiectiv:** parametrii fiscali există ca date versionate, fiecare cu sursa lui.
- **Fișiere:** `backend/evidenta/fiscal/parameters/models.py`, `services.py`, migrații
- **Depinde de:** F0.2.2
- **Review:** `fiscal-reviewer`, `schema-reviewer`, `tenancy-guard`
- **Terminat:** un parametru fără `source_id` nu poate ajunge `active` (constrângere, nu convenție);
  neîntrepătrunderea pe interval funcționează; tabelă globală, în lista de excepții.
- **Blocat de:** DNB-06 *(forma parametrilor care nu sunt scalari)*

### F0.8.2 — Registrul de selecție după dată efectivă

- **Obiectiv:** implementările de logică fiscală se selectează după data perioadei calculate, nu
  după data curentă.
- **Fișiere:** `backend/evidenta/fiscal/registry/models.py`, `resolver.py`, migrații
- **Depinde de:** F0.8.1
- **Review:** `fiscal-reviewer`
- **Terminat:** `resolve(logic_key, effective_date)` returnează exact o implementare sau eșuează;
  un test demonstrează că o dată din trecut selectează implementarea de atunci, nu pe cea curentă.
  Niciun algoritm real încă.
- **Blocat de:** —

> Valorile fiscale efective (OD-22) **nu** fac parte din F0. F0 livrează structura. Introducerea
> unei singure cote „ca exemplu" este exact felul în care o valoare inventată ajunge în producție.

---

## F0.9 — Multi-valută

### F0.9.1 — Modelul de sumă

- **Obiectiv:** reprezentarea sumei în valută există în core, reutilizabilă de orice modul.
- **Fișiere:** `backend/evidenta/accounting/currency/money.py`, teste
- **Depinde de:** F0.0.2
- **Review:** `accounting-reviewer`
- **Terminat:** cele patru elemente (sumă în valută, valută, curs, sumă în moneda funcțională) sunt
  reprezentate împreună; conversia și rotunjirea sunt testate pe cazurile din DNB-08.
- **Blocat de:** — *(parțial deblocată: `numeric` cu scală explicită, niciodată `float`; rotunjirea ca logică fiscală versionată, nu utilitar. Valorile așteaptă ghidul SFS — `OD-24`)*

### F0.9.2 — `exchange_rate`

- **Obiectiv:** cursurile există ca tabelă globală versionată pe dată.
- **Fișiere:** `backend/evidenta/accounting/currency/models.py`, migrații
- **Depinde de:** F0.9.1
- **Review:** `schema-reviewer`, `tenancy-guard`
- **Terminat:** tabelă globală în lista de excepții; `UNIQUE (currency, rate_date, rate_type)`;
  scrierea doar prin calea privilegiată P-3.
- **Blocat de:** —

### ~~F0.9.3~~ — Conectorul BNM → mutat în F1

- **Obiectiv:** cursul oficial se preia automat.
- **Fișiere:** `backend/evidenta/integrations/bnm/`, task Celery
- **Depinde de:** F0.9.2, F0.1.5
- **Review:** `fiscal-reviewer`, `tenancy-guard`
- **Terminat:** cursul zilei se preia și se stochează; comportamentul în zile nelucrătoare este cel
  documentat de BNM, nu presupus; task-ul rulează prin calea privilegiată și se auditează.
- **Blocat de:** OD-26 *(contractul BNM)*
- **Notă:** `OD-10` s-a închis — multi-valuta e **modelată F0**, integrarea BNM și funcționalitatea
  de bază sunt **F1**, reevaluarea și diferențele de curs **F2**. Sarcina rămâne descrisă aici până
  se scrie backlogul F1, dar **nu face parte din criteriul de ieșire din F0**.

---

## F0.10 — Convenții API și schelet frontend

### F0.10.1 — Convenții API

- **Obiectiv:** structura de rutare, erorile și idempotența sunt fixate înainte de primul endpoint
  de business.
- **Fișiere:** `backend/config/urls.py`, `backend/evidenta/platform/api/` (excepții, paginare,
  middleware `Idempotency-Key`), documentație
- **Depinde de:** F0.1.4
- **Review:** `tenancy-guard`
- **Terminat:** `/api/v1/` este singura cale; fiecare eroare are cod stabil; un endpoint de probă cu
  efect financiar refuză cererea fără `Idempotency-Key`.
- **Blocat de:** —

### F0.10.2 — Autentificare la nivel de API

- **Obiectiv:** clienții se autentifică și primesc contextul corect din subdomeniu.
- **Fișiere:** `backend/evidenta/platform/identity/api/`
- **Depinde de:** F0.10.1, F0.3.7
- **Review:** `tenancy-guard`
- **Terminat:** cazurile IZ-04, IZ-05, IZ-36, IZ-37 trec prin stratul API, nu doar prin ORM.
- **Blocat de:** DN-09

### F0.10.3 — Schelet frontend

- **Obiectiv:** aplicația React pornește, rezolvă tenantul din subdomeniu, autentifică și afișează
  un layout de bază.
- **Fișiere:** `frontend/package.json`, `vite.config.ts`, `src/app/`, `src/shared/`, `src/locales/`
- **Depinde de:** F0.10.2 *(nu și F0.0.3: dezvoltarea locală rulează nativ, deci `npm run dev` nu
  așteaptă imaginea de container — vezi `README.md`)*
- **Review:** —
- **Terminat:** un utilizator se autentifică și vede layout-ul; erorile API se afișează după codul
  stabil, nu după mesaj; formatarea numerelor și datelor e cea pentru RM.
- **Blocat de:** OD-19, OD-35 *(`DN-01` închisă prin ADR-014 și ADR-016; `OD-20` stă pe F0.3.5, care
  precedă)*

---

## F0.11 — Model de volum de date

- **Obiectiv:** există scenarii mic / mediu / mare cu date reale, pe baza cărora se poate decide
  partiționarea.
- **Fișiere:** `docs/_bootstrap/11-volume-model.md`, script de generare în `backend/tests/`
- **Depinde de:** F0.3, F0.7 *(pentru forma datelor)*
- **Review:** `schema-reviewer`
- **Terminat:** cele trei scenarii sunt cuantificate; măsurătorile rulează **cu politicile RLS
  active** și sub rolul de aplicație; rezultatul închide OD-01 printr-un ADR.
- **Blocat de:** OD-30 *(firma de contabilitate colaboratoare nu e identificată)*

> Este criteriu de ieșire din F0 fără sarcină în documentul de intrare (E-4). Ordinea nu contează —
> nimic din F0 nu depinde de el — dar absența lui blochează închiderea fazei.

---

## Criteriul de ieșire din F0

Din `_input/evidenta-implementation-spec.md` §6.1, cu sarcina care îl acoperă:

- [ ] Ambele suite de izolare rulează verde în CI, sub rolul de aplicație — *F0.2.6*
- [ ] Se pot crea doi tenanți, o firmă și un engagement, iar accesul se comportă corect în toate
      cele patru combinații (membru, engagement activ, engagement revocat, niciunul) — *F0.2.4*
- [ ] Un task Celery fără context explicit eșuează, nu returnează date — *F0.2.5*
- [ ] Gardianul de model eșuează dacă se adaugă o tabelă fără `tenant_id` — *F0.2.2*
- [ ] Modelul de volum de date este livrat — *F0.11*

## Sinteza blocajelor

Sarcinile care nu pot începe până la închiderea unei decizii:

| Decizie | Blochează |
|---|---|
| ~~DN-12~~ | **închisă** — [ADR-003](../decisions/003-rls-tenancy-tables.md) |
| ~~DN-11~~ | **închisă** — [ADR-004](../decisions/004-company-context.md) |
| ~~OD-14~~ | **închisă** — [ADR-005](../decisions/005-stack-versions.md) |
| ~~OD-15~~ | **închisă** — [ADR-011](../decisions/011-tooling-python.md) |
| OD-16 *(CI)* | F0.0.4, F0.2.6 |
| ~~OD-17~~ | **închisă** — [ADR-024](../decisions/024-gardian-de-dependente.md) |
| ~~OD-18~~ | **închisă** — [ADR-012](../decisions/012-sql-in-django-migrations.md) |
| DN-06, DN-07 *(scope de engagement)* | F0.2.4, F0.3.3 |
| DN-08, DN-09 *(roluri, MFA)* | F0.3.7, F0.10.2 |
| DN-10 *(vocabular de capabilități)* | F0.5.1 |
| OD-02 *(numerotare per companie/filială)* | F0.6.2 |
| DN-16 *(nivel atașamente)* | F0.6.3 |
| OD-11 *(unde locuiesc modelele „F0")* | F0.7.5 |
| OD-12 *(efect de rețea e-Factura)* | F0.7.1 |
| DNB-06 *(forma parametrilor)* | F0.8.1 |
| DNB-08 *(valorile de rotunjire; invariantele sunt fixate)* | calculele din F1, nu F0.9.1 |
| OD-26 *(contractul BNM)* | conectorul BNM, mutat în F1 |
| OD-19, OD-20, DN-01 *(frontend, limbă)* | F0.10.3 |
| OD-30 *(date reale de volum)* | F0.11 |

**Prima sarcină executabilă: F0.1.1** — roluri de bază de date. Este SQL, nu depinde de tooling-ul
Python (`OD-15`), iar cele două decizii care blocau lanțul RLS s-au închis prin ADR-003 și ADR-004.
Lanțul executabil imediat: **F0.1.1 → F0.1.2 → F0.1.3**.

F0.0 (scheletul Python) rămâne blocat de `OD-15`, ceea ce **nu** oprește F0.1: rolurile, funcțiile
de context și predicatele de acces sunt fișiere SQL în `infra/migrations/`.
