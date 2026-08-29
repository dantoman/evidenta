"""Settings shared by every environment.

Nothing here reads a secret from a file. Values that must differ between
environments come from the environment; the per-environment modules decide
whether a missing value is fatal (staging, prod) or has a local default (dev).
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


def env(name: str, default: str | None = None) -> str:
    """Read an environment variable, failing loudly when it is required."""
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(
            f"{name} is not set. Settings never carry a default for values that "
            f"differ between environments -- see config/settings/prod.py."
        )
    return value


# --- applications ------------------------------------------------------------
#
# Deliberately empty of business apps, and deliberately without
# django.contrib.auth. Two reasons, both decisions rather than omissions:
#
# 1. Identity is our own (Spec A section 1.5): User is global, has no tenant_id,
#    and carries no business fields. django.contrib.auth would also bring Group
#    and Permission, i.e. a whole authorisation model -- while the role
#    vocabulary is still an open decision (DN-08). Installing it now would close
#    that decision by accident, which CLAUDE.md section 4 forbids.
#
# 2. The schema guard's exception list covers `django_*` tables. The auth app
#    creates `auth_user`, `auth_group`, `auth_permission`, which do NOT match
#    that pattern and have no tenant_id -- so suite 2 would fail on them, and the
#    wrong fix (widening the exception list) is easier than the right one.
#
# The decision is revisited at F0.3.7, together with DN-08 and DN-09.
#
# `platform.rls` is not a business app: it holds no models and creates no tables.
# It is registered so the query guard is installed once at startup, for every
# entry point, instead of each of them remembering to.
INSTALLED_APPS: list[str] = [
    "evidenta.platform.rls.apps.RlsConfig",
    "evidenta.platform.tenancy.apps.TenancyConfig",
    "evidenta.platform.identity.apps.IdentityConfig",
    "evidenta.platform.engagement.apps.EngagementConfig",
    "evidenta.platform.audit.apps.AuditConfig",
    "evidenta.platform.legislation.apps.LegislationConfig",
    "evidenta.platform.capabilities.apps.CapabilitiesConfig",
    "evidenta.platform.flags.apps.FlagsConfig",
    "evidenta.platform.numbering.apps.NumberingConfig",
    # Numbering generates; this consumes from a range the tax service issued.
    # Two mechanisms, deliberately not one (art. 118²).
    "evidenta.platform.strictforms.apps.StrictFormsConfig",
    "evidenta.platform.documents.apps.DocumentsConfig",
    "evidenta.masterdata.counterparties.apps.CounterpartiesConfig",
    "evidenta.masterdata.uom.apps.UomConfig",
    "evidenta.masterdata.partners.apps.PartnersConfig",
    "evidenta.masterdata.items.apps.ItemsConfig",
    "evidenta.fiscal.parameters.apps.FiscalParametersConfig",
    "evidenta.fiscal.registry.apps.FiscalRegistryConfig",
    "evidenta.platform.notifications.apps.NotificationsConfig",
    "evidenta.platform.attachments.apps.AttachmentsConfig",
    "evidenta.accounting.currency.apps.CurrencyConfig",
    "evidenta.accounting.events.apps.AccountingEventsConfig",
    "evidenta.accounting.coa.apps.CoaConfig",
    # The module the event registry waited for: it fills ACCOUNT_ROLES.
    "evidenta.accounting.slots.apps.SlotsConfig",
    "evidenta.accounting.periods.apps.PeriodsConfig",
    "evidenta.accounting.ledger.apps.LedgerConfig",
    "evidenta.accounting.posting.apps.PostingConfig",
    "evidenta.accounting.opening.apps.OpeningConfig",
    # The operational layer: concrete document types over the document core.
    # They register their types with `platform.documents` from `ready()`, so the
    # core never imports them and the graph stays acyclic (D2, D3).
    "evidenta.operations.sales.apps.SalesConfig",
    "evidenta.operations.purchases.apps.PurchasesConfig",
]

MIDDLEWARE: list[str] = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    # Order is the contract, not a preference. Authentication resolves the
    # session and attaches an identity; the tenant context middleware refuses
    # the request if there is none. Swapped, every request would be refused
    # before the cookie was ever read.
    "evidenta.platform.identity.middleware.SessionAuthenticationMiddleware",
    "evidenta.platform.rls.middleware.TenantContextMiddleware",
    # Inside the tenant context, on purpose. An ApiError raised by a service has
    # to roll the transaction back; catching it outside the context would turn a
    # partial write into a tidy 400. C10 is a guarantee about the API, not about
    # a framework, so it cannot live only in DRF's handler -- the authentication
    # endpoints are plain Django.
    "evidenta.platform.api.middleware.ApiErrorMiddleware",
]

# Names a zero-argument **factory** returning the resolver, not the resolver
# itself: SubdomainTenantResolver takes the base domain in its constructor, and a
# dotted path cannot carry an argument. Unset means the default resolver, which
# refuses -- see middleware.refuse_all.
RLS_CONTEXT_RESOLVER: str | None = "evidenta.platform.tenancy.middleware.subdomain_resolver"

# The domain tenant subdomains hang off: `alpha.evidenta.md` is the tenant
# `alpha` only when this says `evidenta.md`. No default here on purpose -- a
# default would be wrong in every environment except the one it was written for,
# and wrong here means requests attributed to the wrong tenant or to none.
# ADR-025 fixes the local value.
TENANT_BASE_DOMAIN: str | None = None

# The only paths served without a tenant context. Exact paths, never prefixes: a
# prefix would silently exempt every route added under it later. What keeps the
# exemption honest is the query guard -- with no context, an exempt view cannot
# touch business data at all, only the privileged authentication path.
TENANT_CONTEXT_EXEMPT_PATHS: tuple[str, ...] = (
    "/api/v1/auth/login",
    # The orchestrator's probes. Exempt because they have to be: a probe arrives
    # on the container's own host, which carries no tenant subdomain, so a
    # context-bound path would answer 404 to a perfectly healthy service. Safe
    # because neither view reads business data -- see config/health.py.
    "/healthz",
    "/readyz",
)

# The session cookie. Host-only and HttpOnly are not configurable; see
# evidenta.platform.identity.cookie for why. `Secure` is, because local
# development has no TLS to require -- and it defaults to on, so an environment
# that forgets to think about it gets the safe answer.
AUTH_COOKIE_NAME = "evidenta_session"
AUTH_COOKIE_SECURE = True

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": False,
        "OPTIONS": {"context_processors": []},
    },
]

# --- database ----------------------------------------------------------------
#
# Two connections to the same database, under two different roles (ADR-003):
#
#   default    evidenta_app    runtime. No BYPASSRLS, owns nothing.
#   migration  evidenta_owner  owns the tables. Used only by `migrate`.
#
# Run migrations explicitly against the second: `manage.py migrate --database=migration`.
#
# Known consequence for F0.2.1: pytest-django creates the test database using the
# `default` connection, and evidenta_app is NOCREATEDB on purpose. The test
# harness must create the database as owner and then connect as the application
# role -- otherwise the isolation suites either fail to start or, worse, get run
# as owner and prove nothing (T1).
#: The test database, named separately so two people working in the same checkout
#: do not share one. Measured the hard way: two suites running at once against
#: `test_evidenta` produced 594 errors reading
#: `AdminShutdown: terminating connection due to administrator command` -- one run
#: had dropped and recreated the database under the other's connections. Neither
#: was a defect in the code, and both looked like one.
#:
#: Default unchanged, so a single-session checkout behaves exactly as before.
TEST_DATABASE_NAME = env("TEST_DB_NAME", f"test_{env('POSTGRES_DB', 'evidenta')}")

#: The installation role, present only where its credentials are configured.
#:
#: Not a third runtime connection: nothing in the product may use it, and the one
#: command that does -- `create_tenant` -- is the same act as running the
#: migrations. It exists because the first tenant cannot be created any other way.
#: Every policy on `tenant`, `user`, `membership` and `role` is written `TO
#: evidenta_app`, so under `FORCE ROW LEVEL SECURITY` the owner has no policy at
#: all and is refused every insert -- measured, not assumed. Creating the first
#: tenant is therefore a DBA act, exactly like `make bootstrap`, and it is
#: spelled that way rather than smuggled in by widening a policy.
_ADMIN_USER = env("DB_ADMIN_USER", "")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "evidenta"),
        "USER": env("APP_DB_USER", "evidenta_app"),
        "PASSWORD": env("APP_DB_PASSWORD", "evidenta_app"),
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env("POSTGRES_PORT", "5432"),
        # Every request runs inside a transaction. SET LOCAL, which carries the
        # tenant context, lives only for the transaction -- so this is not a
        # convenience, it is what makes R3 hold.
        "ATOMIC_REQUESTS": True,
        "TEST": {"NAME": TEST_DATABASE_NAME},
    },
    "migration": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "evidenta"),
        "USER": env("OWNER_DB_USER", "evidenta_owner"),
        "PASSWORD": env("OWNER_DB_PASSWORD", "evidenta_owner"),
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env("POSTGRES_PORT", "5432"),
        "ATOMIC_REQUESTS": False,
        "TEST": {"NAME": TEST_DATABASE_NAME},
    },
    # The reference-data loading role (ADR-049, OD-67). Writes the global
    # reference tables -- fiscal parameters, logic versions, BNM rates, the chart
    # of accounts, the counterparty registry -- and nothing else: no policy admits
    # it to any tenant table, and it holds no privilege on one. It is not a third
    # runtime connection either: nothing that serves a request may touch it. The
    # loaders reach it through `platform.audit.services.privileged`, which also
    # writes the `privileged_access_log` row the path owes (Spec A section 6.1).
    "refdata": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "evidenta"),
        "USER": env("REFDATA_DB_USER", "evidenta_refdata"),
        "PASSWORD": env("REFDATA_DB_PASSWORD", "evidenta_refdata"),
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env("POSTGRES_PORT", "5432"),
        "ATOMIC_REQUESTS": False,
        "TEST": {"NAME": TEST_DATABASE_NAME},
    },
}

if _ADMIN_USER:
    DATABASES["admin"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "evidenta"),
        "USER": _ADMIN_USER,
        "PASSWORD": env("DB_ADMIN_PASSWORD", ""),
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env("POSTGRES_PORT", "5432"),
        "ATOMIC_REQUESTS": False,
        "TEST": {"NAME": TEST_DATABASE_NAME},
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- locale ------------------------------------------------------------------
#
# Accounting is kept in Romanian by law (Law 287/2017, art. 7(1)) -- see ADR-016.
LANGUAGE_CODE = "ro"
TIME_ZONE = "Europe/Chisinau"
USE_I18N = True
USE_TZ = True

# --- attachments -------------------------------------------------------------
#
# Names a zero-argument factory returning the storage backend. Unset means
# RefusingStorage, which raises on every call -- OD-52 has not chosen a provider,
# and a filesystem fallback would pass every test and lose files in production
# behind a load balancer.
ATTACHMENT_STORAGE: str | None = None

# SCHELET. Upload limits have to exist before the first upload path does, because
# a missing limit is not a missing feature -- it is an unbounded write reachable
# from outside. The values are reversible defaults, not decisions; the real ones
# belong with OD-52, together with what a scanner does.
ATTACHMENT_MAX_BYTES = 25 * 1024 * 1024
ATTACHMENT_ALLOWED_CONTENT_TYPES: tuple[str, ...] = (
    "application/pdf",
    "application/xml",
    "text/xml",
    "image/jpeg",
    "image/png",
    "image/tiff",
    "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

# --- REST --------------------------------------------------------------------
REST_FRAMEWORK = {
    # Adopts the identity the session middleware established; it does not resolve
    # a session of its own. See platform/api/authentication.py for why there is
    # exactly one place that decides who the caller is.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "evidenta.platform.api.authentication.SessionIdentityAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "UNAUTHENTICATED_USER": None,
    # JSON only. The browsable API renders templates, needs `rest_framework` in
    # INSTALLED_APPS, and turns a content-negotiation mistake into a 200 with an
    # HTML body -- which a client parses as a failure it cannot name.
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    # Every error answers with a stable code (C10). Wired at the framework level
    # rather than per view: an endpoint that forgot to use it would answer with
    # DRF's own shape, and the difference is invisible until a client branches on
    # it.
    "EXCEPTION_HANDLER": "evidenta.platform.api.errors.exception_handler",
}

# --- Celery ------------------------------------------------------------------
#
# Every task takes tenant_id explicitly and sets the context before any query
# (R6). The decorator that enforces it arrives at F0.1.5; until then no task
# touches tenant data.
CELERY_BROKER_URL = env("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("REDIS_URL", "redis://localhost:6379/0")
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TIMEZONE = TIME_ZONE
