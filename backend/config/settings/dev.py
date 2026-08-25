"""Local development.

The only module that carries defaults for values which differ between
environments. Convenient here, forbidden in staging and prod.
"""

from config.settings.base import *  # noqa: F403
from config.settings.base import env

DEBUG = True
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-only-not-a-secret")
ALLOWED_HOSTS = ["*"]


# ADR-025. Browsers resolve any `*.localhost` label to loopback with no hosts
# file entry, so a new development tenant costs nothing to reach.
TENANT_BASE_DOMAIN = env("TENANT_BASE_DOMAIN", "evidenta.localhost")

# There is no TLS in front of runserver. Requiring Secure here would mean the
# browser silently drops the session cookie and login appears to succeed while
# every following request is unauthenticated.
AUTH_COOKIE_SECURE = False
