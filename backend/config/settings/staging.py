"""Staging: same shape as production, different data.

No defaults. A missing variable stops the process at import time, which is the
only moment where the mistake is still cheap.
"""

from config.settings.base import *  # noqa: F403
from config.settings.base import env

DEBUG = False
SECRET_KEY = env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS").split(",")
