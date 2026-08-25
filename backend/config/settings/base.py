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
]

MIDDLEWARE: list[str] = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "evidenta.platform.rls.middleware.TenantContextMiddleware",
]

# Resolves the tenant for a request. Unset means the default resolver, which
# refuses -- see middleware.refuse_all. The subdomain resolver (F0.3.5) lives in
# platform.tenancy but is not wired here: it takes a base domain in its
# constructor, so it needs a factory and a setting, and it refuses until
# authentication supplies a user (F0.3.7).
RLS_CONTEXT_RESOLVER: str | None = None

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
    },
    "migration": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "evidenta"),
        "USER": env("OWNER_DB_USER", "evidenta_owner"),
        "PASSWORD": env("OWNER_DB_PASSWORD", "evidenta_owner"),
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env("POSTGRES_PORT", "5432"),
        "ATOMIC_REQUESTS": False,
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- locale ------------------------------------------------------------------
#
# Accounting is kept in Romanian by law (Law 287/2017, art. 7(1)) -- see ADR-016.
LANGUAGE_CODE = "ro"
TIME_ZONE = "Europe/Chisinau"
USE_I18N = True
USE_TZ = True

# --- REST --------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "UNAUTHENTICATED_USER": None,
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
