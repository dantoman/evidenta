# Imaginea de backend — servește și pentru worker (aceeași imagine, comenzi diferite).
#
# NEVERIFICATĂ LA RULARE. Docker nu e instalat pe mașina de dezvoltare, deci
# `docker compose --profile app up` n-a fost executat niciodată. Fișierul e scris
# după documentația uv și după practica obișnuită de imagine Python, dar nimeni
# n-a văzut containerul pornind. Vezi `docs/PROGRESS.md` — F0.0.3 e livrată
# explicit ca **scrisă, nerulată**, nu ca bifă.

FROM python:3.13-slim-bookworm AS base

# uv din imaginea lui oficială, la versiune fixată. `curl | sh` ar aduce ultima
# versiune la fiecare build, adică un build nereproductibil dintr-un motiv care
# n-are legătură cu codul nostru.
COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /uvx /usr/local/bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# `libpq5` pentru psycopg în varianta binară; `curl` pentru healthcheck.
# Fără recomandate: fiecare pachet în plus e suprafață de atac într-o imagine
# care rulează cod de aplicație.
RUN apt-get update \
 && apt-get install --no-install-recommends -y libpq5 curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- dependențe --------------------------------------------------------------
#
# Într-un strat propriu, înaintea codului: se reface doar când se schimbă
# lockfile-ul, nu la fiecare editare.
#
# `--locked` refuză să rezolve din nou. Dacă `uv.lock` nu se potrivește cu
# `pyproject.toml`, build-ul cade — exact ce trebuie: C28 spune că `uv.lock` este
# pinul exact, iar o imagine care rezolvă singură nu mai e reproductibilă.
COPY backend/pyproject.toml backend/uv.lock /app/
RUN uv sync --locked --no-install-project --no-dev

COPY backend/ /app/

# --- utilizator --------------------------------------------------------------
#
# Non-root. Nu e igienă generală: procesul ăsta se conectează la bază ca
# `evidenta_app`, rol fără `BYPASSRLS` și fără ownership (R5) — o imagine care
# rulează ca root ar contrazice la nivel de container exact disciplina pe care
# rolurile o impun la nivel de bază.
RUN useradd --system --uid 10001 --home-dir /app --no-create-home evidenta \
 && chown -R evidenta:evidenta /app /opt/venv
USER evidenta

EXPOSE 8000

# Liveness, nu readiness: `/healthz` nu atinge baza. Un healthcheck de container
# care interoghează baza repornește o aplicație sănătoasă când baza clipește,
# adică transformă o pană recuperabilă într-o buclă de repornire fix în momentul
# în care baza suportă cel mai greu valul de reconectări. Readiness (`/readyz`)
# e treaba orchestratorului, nu a lui Docker.
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

# Fără `migrate` la pornire, deliberat. Migrațiile rulează ca `evidenta_owner`
# (R5), aplicația ca `evidenta_app`; un entrypoint care migrează ar cere
# containerului de aplicație acreditările owner-ului, ceea ce ar face separarea
# rolurilor decorativă. Migrarea e un serviciu propriu în `docker-compose.yml`.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
