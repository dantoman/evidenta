"""What the platform can honestly say about its own running state -- ADR-076 §4.3, "Incidente".

No job persists its state yet, so there is no job history to show. What exists
and can be measured, right now, from the process serving the request: whether
the database answers, whether the broker answers and how deep its queue is,
whether any worker is alive, and when each privileged path last ran (from the
log, which is the one durable trace of platform work). Everything here is a
probe with a short timeout; a probe that hangs would turn the incidents page
into an incident.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.conf import settings
from django.db import connection

from evidenta.platform.audit.models import PrivilegedPath
from evidenta.platform.audit.services.console import privileged_log

#: How long a probe may take before it is reported as down. Short on purpose.
PROBE_TIMEOUT_SECONDS = 1.0

#: The queue Celery consumes by default. Read by name, since no task declares
#: another yet.
QUEUES = ("celery",)


@dataclass(frozen=True, slots=True)
class Probe:
    name: str
    ok: bool
    detail: str | None = None
    latency_ms: int | None = None


@dataclass(frozen=True, slots=True)
class QueueDepth:
    name: str
    depth: int | None
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class PathLastRun:
    code: str
    label: str
    last_run_at: datetime | None
    last_actor: str | None


def database() -> Probe:
    started = time.monotonic()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as failure:
        return Probe("database", False, type(failure).__name__)
    return Probe("database", True, None, int((time.monotonic() - started) * 1000))


def _redis_client() -> Any:
    import redis

    return redis.Redis.from_url(
        str(settings.CELERY_BROKER_URL),
        socket_connect_timeout=PROBE_TIMEOUT_SECONDS,
        socket_timeout=PROBE_TIMEOUT_SECONDS,
    )


def broker() -> Probe:
    started = time.monotonic()
    try:
        _redis_client().ping()
    except Exception as failure:
        return Probe("broker", False, type(failure).__name__)
    return Probe("broker", True, None, int((time.monotonic() - started) * 1000))


def queues() -> list[QueueDepth]:
    try:
        client = _redis_client()
        return [QueueDepth(name, int(client.llen(name))) for name in QUEUES]
    except Exception as failure:
        return [QueueDepth(name, None, type(failure).__name__) for name in QUEUES]


def workers() -> Probe:
    """Who answers a ping on the broker. None is an answer, not an error."""
    try:
        from config.celery import app as celery_app

        replies = celery_app.control.inspect(timeout=PROBE_TIMEOUT_SECONDS).ping() or {}
    except Exception as failure:
        return Probe("workers", False, type(failure).__name__)
    names = sorted(replies)
    return Probe("workers", bool(names), ", ".join(names) if names else None)


def last_runs() -> list[PathLastRun]:
    """For every path the log knows, its most recent run -- or none, ever."""
    latest: dict[str, tuple[datetime, str]] = {}
    for row in privileged_log(limit=500):
        if row.path_code not in latest:
            latest[row.path_code] = (row.occurred_at, row.actor_email or row.actor)
    return [
        PathLastRun(
            code=str(code),
            label=str(label),
            last_run_at=latest[code][0] if code in latest else None,
            last_actor=latest[code][1] if code in latest else None,
        )
        for code, label in PrivilegedPath.choices
    ]
