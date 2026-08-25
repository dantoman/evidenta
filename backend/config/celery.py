"""Celery application.

Task-level tenant context is not configured here. It arrives at F0.1.5 as a
decorator that refuses to start a task without an explicit tenant_id -- refusing
loudly, because a task that quietly runs with no context returns zero rows and
reports success (R6).
"""

from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("evidenta")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
