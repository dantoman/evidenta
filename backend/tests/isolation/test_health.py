"""The orchestrator's probes -- F0.0.3.

These are the only two paths besides login that answer without a tenant context,
so they get the same scrutiny the login exemption got: what makes an exempt path
safe is not that it is trusted, it is that the query guard refuses every
context-less query on the application connection, so an exempt view cannot reach
business data even by mistake.

The container image's HEALTHCHECK calls `/healthz`. If it started answering 404 --
which is what a context-bound path does on a host with no tenant subdomain -- the
orchestrator would restart a healthy service in a loop, and the suite would still
be green. Hence these tests.
"""

from __future__ import annotations

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db(databases=["default", "migration"])


def test_liveness_answers_without_a_tenant_and_without_the_database() -> None:
    """A host with no subdomain, which is exactly what a probe arrives on.

    The response must not depend on the database: a liveness probe that queries
    it restarts a healthy application when the database blips, turning a
    recoverable outage into a restart loop at the moment the database can least
    afford the reconnection storm.
    """
    response = Client().get("/healthz", headers={"host": "localhost"})
    assert response.status_code == 200
    assert response.json() == {"status": "live"}


def test_readiness_answers_on_a_host_with_no_tenant() -> None:
    """Readiness does reach the database -- and still needs no tenant.

    `SELECT 1` touches no business table, which is why it can run under
    `unguarded`: the exception is named at the call site rather than being a hole
    in the guard.
    """
    response = Client().get("/readyz", headers={"host": "localhost"})
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_the_probes_are_exact_paths_not_prefixes() -> None:
    """The same discipline as the login exemption.

    A prefix exemption on `/healthz` would exempt `/healthz/../api/v1/...`-shaped
    routes anyone later hangs beneath it. There is nothing under these paths
    today, and the assertion is here so that adding something would fail loudly
    rather than inherit the exemption.
    """
    from django.conf import settings

    assert "/healthz" in settings.TENANT_CONTEXT_EXEMPT_PATHS
    response = Client().get("/healthz/something", headers={"host": "localhost"})
    assert response.status_code == 404


def test_an_ordinary_path_still_refuses_on_a_host_with_no_tenant() -> None:
    """The control. Without it the two tests above prove only that Django
    serves URLs, not that the exemption is what makes them answer.
    """
    response = Client().get("/api/v1/accounting/", headers={"host": "localhost"})
    assert response.status_code == 404
