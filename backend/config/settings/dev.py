"""Local development.

The only module that carries defaults for values which differ between
environments. Convenient here, forbidden in staging and prod.
"""

from config.settings.base import *  # noqa: F403
from config.settings.base import env

DEBUG = True
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-only-not-a-secret")
ALLOWED_HOSTS = ["*"]
