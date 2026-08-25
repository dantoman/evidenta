"""Production.

No defaults, and no DEBUG under any circumstance: with DEBUG on, Django renders
tracebacks that include settings and query parameters -- in this system that
means tenant identifiers and accounting data, to whoever triggered the error.
"""

from config.settings.base import *  # noqa: F403
from config.settings.base import env

DEBUG = False
SECRET_KEY = env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS").split(",")

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
