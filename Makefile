# Comenzi de bază.
#
# Dezvoltarea locală rulează NATIV: PostgreSQL și Redis sunt servicii pe mașină, nu containere.
# Docker rămâne pentru producție — `docker-compose.yml` și `infra/docker/` (F0.0.3). Motivul e
# practic, nu ideologic: local se rulează `manage.py`, `pytest` și `psql` direct, iar un strat de
# containere între ele adaugă doar indirecție.
#
# Numele variabilelor de mai jos sunt exact cele pe care le citesc settings-urile Django
# (`backend/config/settings/base.py`) și harness-ul de test (`backend/tests/conftest.py`), ca să
# existe un singur vocabular. Se suprascriu din `.env` (negitat; model în `.env.example`) sau din
# linia de comandă: `make migrate POSTGRES_PORT=5433`.
#
# Țintele marcate „nedefinit încă" așteaptă decizii sau sarcini din F0 — eșuează cu mesaj explicit
# în loc să facă ceva plauzibil dar greșit.

-include .env

# --- conexiune ---------------------------------------------------------------

POSTGRES_DB       ?= evidenta
POSTGRES_HOST     ?= localhost
POSTGRES_PORT     ?= 5432

OWNER_DB_USER     ?= evidenta_owner
OWNER_DB_PASSWORD ?= evidenta_owner
APP_DB_USER       ?= evidenta_app
APP_DB_PASSWORD   ?= evidenta_app
# Rolul de încărcare a datelor de referință (ADR-049, `0004_refdata_role.sql`): scrie tabelele
# globale de referință și nimic altceva. Ca și celelalte, numele nu e configurabil — doar parola.
REFDATA_DB_USER     ?= evidenta_refdata
REFDATA_DB_PASSWORD ?= evidenta_refdata

# Superuserul creează baza și aplică `0000`/`0001` (ADR-012). Este credențial de infrastructură
# locală, niciodată unul de aplicație — de aceea are propriile variabile.
DB_ADMIN_USER     ?= postgres
DB_ADMIN_PASSWORD ?=

# Harness-ul de test folosește același superuser: creează și șterge baza de test, apoi predă
# conexiunea rolului de aplicație (T1).
TEST_DB_ADMIN_USER     ?= $(DB_ADMIN_USER)
TEST_DB_ADMIN_PASSWORD ?= $(DB_ADMIN_PASSWORD)

REDIS_URL     ?= redis://localhost:6379/0
BACKEND_PORT  ?= 8000

export

PSQL ?= psql -v ON_ERROR_STOP=1 -h $(POSTGRES_HOST) -p $(POSTGRES_PORT)

# Suprascrie `ADMIN_PSQL` în `.env` dacă superuserul local se accesează prin peer, nu prin parolă:
#   ADMIN_PSQL=sudo -u postgres psql -v ON_ERROR_STOP=1
# `PGPASSWORD` se pune doar dacă parola e completată: setat și gol, libpq îl consideră parolă
# validă și nu mai citește `~/.pgpass`. Cu variabila lipsă, `.pgpass`, peer și trust funcționează.
ADMIN_PSQL ?= $(if $(DB_ADMIN_PASSWORD),PGPASSWORD=$(DB_ADMIN_PASSWORD) )$(PSQL) -U $(DB_ADMIN_USER)
OWNER_PSQL ?= $(if $(OWNER_DB_PASSWORD),PGPASSWORD=$(OWNER_DB_PASSWORD) )$(PSQL) -U $(OWNER_DB_USER)
APP_PSQL   ?= $(if $(APP_DB_PASSWORD),PGPASSWORD=$(APP_DB_PASSWORD) )$(PSQL) -U $(APP_DB_USER)

.DEFAULT_GOAL := help

.PHONY: help
help: ## Afișează comenzile disponibile
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# --- mediu local -------------------------------------------------------------

.PHONY: doctor
doctor: ## Verifică ce cere dezvoltarea locală: uv, psql, PostgreSQL, Redis, baza
	@command -v uv >/dev/null || { echo "uv lipsește — https://docs.astral.sh/uv/"; exit 1; }
	@command -v psql >/dev/null || { echo "psql lipsește — instalează postgresql-client"; exit 1; }
	@pg_isready -h $(POSTGRES_HOST) -p $(POSTGRES_PORT) >/dev/null \
		|| { echo "PostgreSQL nu răspunde pe $(POSTGRES_HOST):$(POSTGRES_PORT)"; exit 1; }
	@echo "PostgreSQL  $(POSTGRES_HOST):$(POSTGRES_PORT) — OK"
	@if command -v redis-cli >/dev/null; then \
		redis-cli -u $(REDIS_URL) ping >/dev/null 2>&1 \
			&& echo "Redis       $(REDIS_URL) — OK" \
			|| { echo "Redis nu răspunde pe $(REDIS_URL)"; exit 1; }; \
	else \
		echo "Redis       neverificat (redis-cli lipsește)"; \
	fi
	@$(APP_PSQL) -d $(POSTGRES_DB) -Atc "select 1" >/dev/null 2>&1 \
		&& echo "Baza        $(APP_DB_USER)@$(POSTGRES_DB) — OK" \
		|| echo "Baza        $(POSTGRES_DB) nu acceptă $(APP_DB_USER) — rulează: make setup"

.PHONY: setup
setup: ## Prima rulare: mediu Python, bază, bootstrap, migrații
	$(MAKE) check-roles
	$(MAKE) sync
	$(MAKE) create-db
	$(MAKE) migrate

# --- bază de date ------------------------------------------------------------

.PHONY: create-db
create-db: ## Creează baza cu colația din ADR-015 (o singură dată, pe clusterul local)
	@if $(ADMIN_PSQL) -d postgres -Atc \
			"select 1 from pg_database where datname = '$(POSTGRES_DB)'" 2>/dev/null | grep -q 1; then \
		echo "Baza $(POSTGRES_DB) există deja. Colația ei o verifică 0000_locale_guard.sql."; \
	else \
		$(ADMIN_PSQL) -d postgres -c \
			"CREATE DATABASE $(POSTGRES_DB) LOCALE_PROVIDER icu ICU_LOCALE 'ro' TEMPLATE template0;"; \
	fi

.PHONY: check-roles
check-roles: ## Verifică că numele rolurilor din .env sunt cele pe care le creează bootstrap-ul
	@for pair in "OWNER_DB_USER $(OWNER_DB_USER)" "APP_DB_USER $(APP_DB_USER)" \
	            "REFDATA_DB_USER $(REFDATA_DB_USER)"; do \
		set -- $$pair; \
		grep -qE "CREATE ROLE $$2([[:space:]]|;)" infra/bootstrap/0*.sql || { \
			echo "$$1=$$2 nu este un rol pe care îl creează infra/bootstrap/."; \
			echo "Numele rolurilor NU sunt configurabile: apar literal în fiecare politică RLS și"; \
			echo "în fiecare GRANT din infra/migrations/. Configurabile sunt doar parolele."; \
			echo "Rolurile așteptate: $$(grep -ohE 'CREATE ROLE [a-z_]+' infra/bootstrap/0*.sql \
				| cut -d' ' -f3 | tr '\n' ' ')"; \
			exit 1; \
		}; \
	done

.PHONY: bootstrap
bootstrap: check-roles ## Aplică infra/bootstrap/ — fiecare fișier cu rolul care îi trebuie (ADR-012)
	@for f in infra/bootstrap/0*.sql; do \
		case "$$f" in \
			*0000_*|*0001_*|*0004_*) \
				echo "--> $$f (ca $(DB_ADMIN_USER))"; \
				$(ADMIN_PSQL) -d $(POSTGRES_DB) \
					-v owner_password="$(OWNER_DB_PASSWORD)" \
					-v app_password="$(APP_DB_PASSWORD)" \
					-v refdata_password="$(REFDATA_DB_PASSWORD)" -f "$$f" ;; \
			*) \
				echo "--> $$f (ca $(OWNER_DB_USER))"; \
				$(OWNER_PSQL) -d $(POSTGRES_DB) -f "$$f" ;; \
		esac || exit 1; \
	done

.PHONY: migrate
migrate: ## bootstrap + migrațiile Django, pe conexiunea de owner (ADR-003)
	$(MAKE) bootstrap
	cd backend && uv run python manage.py migrate --database=migration

.PHONY: psql
psql: ## Shell psql ca evidenta_owner
	$(OWNER_PSQL) -d $(POSTGRES_DB)

.PHONY: psql-app
psql-app: ## Shell psql ca evidenta_app — vede exact ce vede aplicația, cu RLS activ
	$(APP_PSQL) -d $(POSTGRES_DB)

.PHONY: reset-db
reset-db: ## Șterge și reconstruiește baza locală (DISTRUCTIV — cere CONFIRM=yes)
	@test "$(CONFIRM)" = "yes" \
		|| { echo "Șterge baza $(POSTGRES_DB) de pe $(POSTGRES_HOST). Rulează: make reset-db CONFIRM=yes"; exit 1; }
	$(ADMIN_PSQL) -d postgres -c "DROP DATABASE IF EXISTS $(POSTGRES_DB) WITH (FORCE);"
	$(MAKE) create-db
	$(MAKE) migrate

# --- rulare ------------------------------------------------------------------

.PHONY: run
run: ## Pornește serverul de dezvoltare
	cd backend && uv run python manage.py runserver $(BACKEND_PORT)

# Frontend. Node se ia din `.nvmrc` — 24 LTS, fixat prin ADR-005 — ca shell-ul local și jobul de CI
# să nu poată diverge. `npm ci`, nu `npm install`: refuză să rezolve ce lockfile-ul nu pinuiește deja.
NPM := cd frontend && npm

.PHONY: dev-code
dev-code: ## Codul TOTP curent pentru utilizatorul de dezvoltare (dev@example.md)
	@test -n "$(DEV_TOTP_SECRET)" || { \
	  echo "DEV_TOTP_SECRET nu este setat în .env — model în .env.example"; exit 1; }
	@cd backend && uv run python -c "import pyotp, time; t=pyotp.TOTP('$(DEV_TOTP_SECRET)'); \
	print(t.now(), '— valabil', 30 - int(time.time()) % 30, 'secunde')"

.PHONY: web-install
web-install: ## Instalează dependențele frontend din lockfile
	$(NPM) ci

.PHONY: web
web: ## Pornește Vite pe evidenta.localhost:5173 (tenantul vine din subdomeniu — ADR-025)
	@echo "Deschide http://<subdomeniu>.evidenta.localhost:5173 — de ex. http://alpha.evidenta.localhost:5173"
	$(NPM) run dev

.PHONY: web-check
web-check: ## Tipuri, lint (inclusiv C16) și build, exact ce rulează CI
	$(NPM) run typecheck
	$(NPM) run lint
	$(NPM) run build

.PHONY: worker
worker: ## Pornește workerul Celery
	cd backend && uv run celery -A config worker -l info

.PHONY: shell
shell: ## Shell Django, sub rolul de aplicație (garda de interogare refuză fără context de tenant)
	cd backend && uv run python manage.py shell

.PHONY: manage
manage: ## Orice comandă manage.py, cu mediul din .env: make manage ARGS="showmigrations"
	@test -n "$(ARGS)" || { echo 'Folosire: make manage ARGS="showmigrations"'; exit 1; }
	cd backend && uv run python manage.py $(ARGS)

# --- inspecția schemei -------------------------------------------------------
#
# Cele două comenzi read-only pe care `schema-reviewer` are voie să le ruleze, și singurele. Un
# fișier de migrare citit nu este schema pe care a produs-o; diferența e locul unde stau erorile.

.PHONY: schema-dump
schema-dump: ## Structura schemei, fără date (read-only)
	@$(if $(OWNER_DB_PASSWORD),PGPASSWORD=$(OWNER_DB_PASSWORD) )pg_dump --schema-only --no-owner \
		-h $(POSTGRES_HOST) -p $(POSTGRES_PORT) -U $(OWNER_DB_USER) -d $(POSTGRES_DB)

.PHONY: rls-report
rls-report: ## Per tabelă: RLS activ, FORCE, număr de politici, coloana de tenant (read-only)
	@$(OWNER_PSQL) -d $(POSTGRES_DB) -f infra/rls/report.sql

# --- verificare --------------------------------------------------------------

.PHONY: check
check: ## Preflight Django (`manage.py check`) — nu atinge baza
	cd backend && uv run python manage.py check

.PHONY: isolation-check
isolation-check: ## Rulează suitele de izolare, sub rolul de aplicație (T1)
	cd backend && uv run pytest -q tests/isolation tests/test_harness.py

.PHONY: test
test: ## Rulează suita de teste (backend și frontend)
	cd backend && uv run pytest
	$(NPM) run test

.PHONY: web-test
web-test: ## Doar testele de frontend (Vitest)
	$(NPM) run test

.PHONY: create-tenant
create-tenant: ## Creează un tenant și utilizatorul lui (SUBDOMAIN=..., NAME=..., EMAIL=...)
	@test -n "$(SUBDOMAIN)" -a -n "$(NAME)" -a -n "$(EMAIL)" || { \
	  echo "folosire: make create-tenant SUBDOMAIN=alpha NAME=\"Alpha SRL\" EMAIL=cineva@example.md"; exit 1; }
	cd backend && uv run python manage.py create_tenant \
	  --subdomain "$(SUBDOMAIN)" --legal-name "$(NAME)" --email "$(EMAIL)"

.PHONY: seed-coa
seed-coa: ## Încarcă planul general de conturi (SNC 2020) — idempotent, sub rolul de date de referință (ADR-049)
	cd backend && uv run python manage.py load_coa_template

.PHONY: check-committed
check-committed: ## Se compilează ce e COMIS? (verificările obișnuite citesc discul, unde fișierul uitat există)
	./scripts/check-committed.sh

.PHONY: hooks
hooks: ## Instalează cârligele git (cere trailerul `Session:` pe fiecare commit)
	git config core.hooksPath .githooks
	@echo "core.hooksPath = .githooks — commiturile cer acum trailerul \`Session:\`."
	@echo "Cârligul repară UITAREA, nu minciuna: prezența trailerului e impusă, adevărul lui nu."

.PHONY: drift-check
drift-check: ## Compară baza VIE cu contractele RLS (suita rulează pe baza de test, care nu poate vedea deriva)
	cd backend && uv run python manage.py check_schema_drift

.PHONY: lint
lint: ## Lint + verificarea formatării (ruff)
	cd backend && uv run ruff check .
	cd backend && uv run ruff format --check .

.PHONY: format
format: ## Formatează codul (ruff)
	cd backend && uv run ruff format .
	cd backend && uv run ruff check --fix .

.PHONY: typecheck
typecheck: ## mypy — strict pe platform și accounting (ADR-011)
	cd backend && uv run mypy .

.PHONY: sync
sync: ## Instalează mediul din uv.lock
	cd backend && uv sync --locked

.PHONY: deps-check
deps-check: ## Verifică regulile de dependență între module (D1-D6 din CLAUDE.md)
	cd backend && uv run python -m tests.deps_guard.audit
