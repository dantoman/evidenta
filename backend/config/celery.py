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


@app.on_after_configure.connect
def _check_event_registry(sender: object, **_: object) -> None:
    """Same check as the web process, for the same reason -- ADR-038 section 5.

    A worker is where a posting most often happens, and where an unserviceable
    registry would be least visible: a task that fails quietly retries, and the
    queue grows while nothing says why.
    """
    from evidenta.accounting.events.registry import check_registry

    check_registry()
