# Evidenta.md

Platformă cloud de contabilitate și ERP construită pentru Republica Moldova.

**Formularea internă:** entitățile core sunt ERP-ready, livrarea este accounting-first.
**Poziționare:** „De la prima factură până la ERP."

Ce vinde produsul este conformitatea — SNC, TVA, e-Factura, IPC, rapoartele către SFS, CNAS, CNAM
și BNS. Restul modulelor se construiesc peste un nucleu care nu se blochează structural.

---

## Stare curentă

**Faza:** inițializare. **Nu se scrie cod de producție.**

Se construiesc structura, regulile, agenții de review, specificațiile și planul de lucru. Starea la
zi și sarcina curentă stau în [docs/PROGRESS.md](docs/PROGRESS.md).

Implementarea începe cu **F0.1 — roluri de bază de date și infrastructură RLS**, urmată de
**F0.2 — suitele de verificare**. Ambele preced orice model Django. Ordinea nu se rearanjează.

---

## Documentație

| Document | Conținut |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Regulile permanente: invarianți, convenții, dependențe între module, ce nu se face |
| [docs/PROGRESS.md](docs/PROGRESS.md) | Starea proiectului, sarcina curentă, blocaje, întrebări deschise |
| [docs/specs/](docs/specs/) | Spec A (tenancy, identitate, engagement, billing) și Spec B (accounting core) |
| [docs/decisions/](docs/decisions/) | ADR-uri și registrul deciziilor deschise |
| [docs/_bootstrap/](docs/_bootstrap/) | Inventarul invarianților, modulelor, deciziilor și golurilor; backlogul F0 |
| [docs/_input/](docs/_input/) | Documentele de strategie și arhitectură. **Read-only** |

---

## Structura repo-ului

```
evidenta/
├── CLAUDE.md              reguli permanente, citite la fiecare sesiune
├── docker-compose.yml     producție și paritate; local se rulează nativ
├── Makefile               comenzi de bază
├── .env.example           configurarea mediului local
│
├── .claude/
│   ├── agents/            subagenți de review (read-only) și de test
│   └── commands/          workflow-uri repetabile
│
├── backend/
│   ├── config/            settings, urls, celery, db_roles.sql
│   ├── evidenta/          modulele (platform, masterdata, fiscal, accounting, ...)
│   └── tests/
│       ├── isolation/     suita 1 — penetrare între tenanți
│       ├── schema_guard/  suita 2 — gardian de model
│       └── integration/   lanțul complet document → journal line
│
├── frontend/src/          app, shared, locales
│
└── infra/
    ├── docker/            Dockerfile-uri
    ├── migrations/        SQL manual: roluri, politici RLS
    └── ci/                configurare CI
```

Directoarele de module nu se creează în avans. Un modul apare când sarcina care îl implementează
începe — vezi regula „ce nu se face" din [CLAUDE.md](CLAUDE.md).

---

## Dezvoltare locală

**Local se rulează nativ, fără docker.** PostgreSQL 18 și Redis sunt servicii pe mașină; `uv`
gestionează mediul Python. Docker rămâne pentru producție — `docker-compose.yml` și `infra/docker/`.

Se cer instalate: PostgreSQL 18 cu `psql`, Redis, [uv](https://docs.astral.sh/uv/) și acces de
superuser la clusterul local (creează baza și rolurile).

```bash
cp .env.example .env    # completează parola superuserului local
make doctor             # verifică uv, psql, PostgreSQL, Redis, baza
make setup              # mediu Python + bază + bootstrap + migrații — o singură dată
```

`make setup` face trei lucruri, în ordinea din [ADR-012](docs/decisions/012-sql-in-django-migrations.md):
creează baza cu colația ICU din [ADR-015](docs/decisions/015-colatie-icu.md), aplică
`infra/bootstrap/` (roluri, scheme, predicate de acces) și rulează migrațiile Django pe conexiunea
de owner. Fiecare pas există și separat: `make create-db`, `make bootstrap`, `make migrate`.

După setup:

```bash
make test         # suita completă, sub rolul de aplicație
make psql-app     # shell psql ca evidenta_app — vede exact ce vede aplicația, cu RLS activ
make rls-report   # per tabelă: RLS activ, FORCE, politici, coloana de tenant
make schema-dump  # structura schemei, fără date
make run          # serverul de dezvoltare
make worker       # workerul Celery
make help         # toate comenzile
```

`make run` pornește serverul, dar **nicio cerere nu ajunge la date**: nu există rezolvator de
subdomeniu, deci middleware-ul refuză tot, cu mesaj explicit, până la F0.3.5. Iar `urlpatterns` este
gol până la F0.10. Ce se poate verifica azi este baza — izolarea, bootstrap-ul și migrațiile — prin
`make test`, `make psql-app` și `make rls-report`.

Orice comandă `manage.py` se dă prin `make manage ARGS="..."`, ca să primească mediul din `.env`:
Django nu citește fișierul singur, iar cu parolele implicite se conectează la altceva decât baza ta.
Comenzile care citesc schema merg pe conexiunea de owner — `make manage ARGS="showmigrations
--database=migration"` — fiindcă garda de interogare refuză, corect, orice citire fără context de
tenant pe conexiunea aplicației.

---

## Convenții

- Cod, comentarii și mesaje de commit în **engleză**; interfață și documentație în **română**.
- O sesiune de lucru = un modul sau o capabilitate. Niciodată „implementează Faza 0".
- `docs/PROGRESS.md` se actualizează la începutul și la sfârșitul fiecărei sesiuni.
- Nicio decizie deschisă nu se închide tacit în cod.
