"""Liveness and readiness, for the container orchestrator.

Deliberately in `config` and not in an app. A health endpoint is not a module of
the product -- it has no tenant, no business rule and no place in the dependency
graph (C1 exists to stop the `common` app that accumulates exactly this kind of
thing). It is also not an API resource, so it does not settle anything about the
API conventions, which are F0.10.1 and open.

**Neither view touches business data, and that is what makes exempting them from
the tenant context safe.** They are exempt because they have to be: a probe
arrives on the container's own host, which has no tenant subdomain, so a
context-bound path would answer 404 to a healthy service. The query guard is
still the backstop -- a context-less query on the application connection is
refused whatever this module does.
"""

from __future__ import annotations

from django.db import connections
from django.http import HttpRequest, JsonResponse

from evidenta.platform.rls.context import unguarded


def live(request: HttpRequest) -> JsonResponse:
    """The process is up and serving. No database, on purpose.

    A liveness probe that queries the database restarts a healthy application
    when the database blips -- turning a recoverable outage into a restart loop
    at exactly the moment the database is least able to take the reconnection
    storm.
    """
    return JsonResponse({"status": "live"})


def ready(request: HttpRequest) -> JsonResponse:
    """The process can reach its dependencies and should receive traffic.

    `SELECT 1` and nothing else. It is named through `unguarded` because the
    query guard refuses context-less queries by default and this is a real
    exception, not an oversight -- the whole point of that mechanism is that
    every exception says why in one word visible at the call site.

    Not merged with `live` even though the code would be shorter: they answer
    different questions and the orchestrator does different things with the
    answers. Ready failing removes the container from the load balancer; live
    failing kills it.
    """
    try:
        with unguarded("health: readiness probe"), connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as failure:
        return JsonResponse({"status": "not-ready", "reason": type(failure).__name__}, status=503)
    return JsonResponse({"status": "ready"})
