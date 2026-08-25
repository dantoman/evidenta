"""The request path, end to end -- spec-a 3.2 as a suite.

Every other isolation test builds a context by hand and proves what happens
inside it. This one proves the context is built at all, and built from the two
sources the specification names: the host, and the session. Nothing here
constructs a ``TenantContext``; if one exists during these requests, the
middleware chain made it.

The claims, in order of what they would cost to get wrong:

* a host with no tenant reaches nothing, and says so as 404
* a request with no session reaches nothing, and says so as 401
* a session issued for one tenant does not authenticate on another's host
* revoked and expired sessions stop authenticating immediately
* the cookie is host-only and unreadable by script

Runs under the application role like the rest of suite 1 (T1).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pyotp
import pytest
from django.contrib.auth.hashers import make_password
from django.test import Client

from evidenta.platform.identity.models import User, UserSession
from evidenta.platform.identity.services.authentication import (
    confirm_totp,
    enrol_totp,
    generate_secret_key,
)
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

PASSWORD = "o-parola-suficient-de-lunga"
HOST_A = "alpha.evidenta.localhost"
HOST_B = "beta.evidenta.localhost"
COOKIE = "evidenta_session"


@pytest.fixture(autouse=True)
def mfa_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MFA_SECRET_KEY", generate_secret_key())


@pytest.fixture
def credentials(world: dict[str, uuid.UUID]) -> Iterator[dict[str, Any]]:
    """A user of tenant A who can actually log in: password plus confirmed TOTP.

    Set up through a context on purpose -- enrolment is a post-authentication
    operation and has no business running on the privileged path.
    """
    context = TenantContext(
        tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="setup"
    )
    with tenant_context(context):
        User.objects.filter(pk=world["user_a"]).update(password_hash=make_password(PASSWORD))
        enrolment = enrol_totp(world["user_a"], label="phone")
        secret = str(pyotp.parse_uri(enrolment.provisioning_uri).secret)  # type: ignore[union-attr]
        confirm_totp(enrolment.method_id, pyotp.TOTP(secret).now())
    yield {"email": "a@example.md", "secret": secret, "context": context}


def log_in(client: Client, host: str, email: str, secret: str) -> Any:
    return client.post(
        "/api/v1/auth/login",
        data=json.dumps(
            {"email": email, "password": PASSWORD, "totp_code": pyotp.TOTP(secret).now()}
        ),
        content_type="application/json",
        headers={"host": host},
    )


def test_a_host_without_a_tenant_reaches_nothing(world: dict[str, uuid.UUID]) -> None:
    """What the browser at http://localhost:8000/ gets, and should keep getting.

    Not a misconfiguration: the tenant comes from the subdomain and nowhere else
    (C8), so a host without one has no tenant to serve. The refusal happens in
    the middleware, before URL resolution -- which is why the answer is the same
    for a path that exists and one that does not.
    """
    response = Client().get("/", headers={"host": "localhost:8000"})
    assert response.status_code == 404
    assert response.json()["code"] == "tenant.not_found"


def test_a_request_without_a_session_is_refused(world: dict[str, uuid.UUID]) -> None:
    response = Client().get("/api/v1/auth/whoami", headers={"host": HOST_A})
    assert response.status_code == 401
    assert response.json()["code"] == "auth.required"


def test_login_then_an_authenticated_request(
    credentials: dict[str, Any], world: dict[str, uuid.UUID]
) -> None:
    """The whole chain, and the only test that proves it end to end.

    Reaching ``whoami`` with the right identity means the cookie resolved, the
    host resolved, the two agreed and the context was set -- and none of those
    steps could have been faked by the view, which performs no query at all.
    """
    client = Client()
    assert log_in(client, HOST_A, credentials["email"], credentials["secret"]).status_code == 200

    response = client.get("/api/v1/auth/whoami", headers={"host": HOST_A})
    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == str(world["user_a"])
    assert body["tenant_id"] == str(world["tenant_a"])
    assert body["actor_firm_id"] is None


def test_the_cookie_is_host_only_and_hidden_from_script(credentials: dict[str, Any]) -> None:
    """Host-only is the tenant boundary restated in the browser.

    With a ``Domain`` attribute the cookie would be sent to every tenant's
    subdomain, and one tenant's session would arrive on another tenant's host --
    refused, but only because something remembered to compare. Without it the
    browser never sends it, and there is nothing to remember.
    """
    response = log_in(Client(), HOST_A, credentials["email"], credentials["secret"])
    morsel = response.cookies[COOKIE]
    assert morsel["domain"] == ""
    assert morsel["httponly"]
    assert morsel["samesite"] == "Lax"


def test_a_session_of_one_tenant_does_not_authenticate_on_another(
    credentials: dict[str, Any],
) -> None:
    """A browser would not send this cookie across hosts. A client that sets its
    own headers will, and the answer must not be an empty result set -- that is
    indistinguishable from a tenant with no data."""
    client = Client()
    log_in(client, HOST_A, credentials["email"], credentials["secret"])

    response = client.get("/api/v1/auth/whoami", headers={"host": HOST_B})
    assert response.status_code == 401
    assert response.json()["code"] == "auth.session_tenant_mismatch"


def test_a_revoked_session_stops_authenticating(credentials: dict[str, Any]) -> None:
    """IZ-20 on the request path: revocation ends the interface, not just the data."""
    client = Client()
    log_in(client, HOST_A, credentials["email"], credentials["secret"])

    with tenant_context(credentials["context"]):
        UserSession.objects.filter(revoked_at__isnull=True).update(
            revoked_at=datetime.now(UTC), revocation_reason="test"
        )

    response = client.get("/api/v1/auth/whoami", headers={"host": HOST_A})
    assert response.status_code == 401


def test_an_expired_session_stops_authenticating(credentials: dict[str, Any]) -> None:
    """Expiry is evaluated in the query, not by a job that marks rows."""
    client = Client()
    log_in(client, HOST_A, credentials["email"], credentials["secret"])

    with tenant_context(credentials["context"]):
        UserSession.objects.all().update(expires_at=datetime.now(UTC) - timedelta(minutes=1))

    response = client.get("/api/v1/auth/whoami", headers={"host": HOST_A})
    assert response.status_code == 401


def test_logout_ends_the_session(credentials: dict[str, Any]) -> None:
    client = Client()
    log_in(client, HOST_A, credentials["email"], credentials["secret"])

    assert client.post("/api/v1/auth/logout", headers={"host": HOST_A}).status_code == 204
    assert client.get("/api/v1/auth/whoami", headers={"host": HOST_A}).status_code == 401


def test_login_is_served_without_a_context_and_still_refuses_bad_credentials(
    credentials: dict[str, Any],
) -> None:
    """The one exempt path. It reaches the database only through the privileged
    authentication functions -- anything else would be refused by the query
    guard, since there is no context to run it in."""
    response = Client().post(
        "/api/v1/auth/login",
        data=json.dumps({"email": credentials["email"], "password": "gresit"}),
        content_type="application/json",
        headers={"host": HOST_A},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "auth.invalid_credentials"
    assert COOKIE not in response.cookies


def test_login_on_a_host_without_a_tenant_is_not_found(credentials: dict[str, Any]) -> None:
    """Exempt from the context, not from the host. A login endpoint that answered
    on any host would issue sessions for a tenant nobody named."""
    response = Client().post(
        "/api/v1/auth/login",
        data=json.dumps({"email": credentials["email"], "password": PASSWORD}),
        content_type="application/json",
        headers={"host": "localhost:8000"},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "tenant.not_found"


def test_login_refuses_a_user_with_no_access_to_the_tenant(
    world: dict[str, uuid.UUID], seed: Callable[..., None]
) -> None:
    """Correct password, correct second factor, wrong tenant.

    Without this check the session would be issued and every query would return
    nothing -- safe, and indistinguishable to the user from a broken product. The
    check asks the database the same question every later query asks, through the
    visibility of the tenant's own row.
    """
    context = TenantContext(
        tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="setup"
    )
    with tenant_context(context):
        User.objects.filter(pk=world["user_b"]).update(password_hash=make_password(PASSWORD))
        enrolment = enrol_totp(world["user_b"], label="phone")
        secret = str(pyotp.parse_uri(enrolment.provisioning_uri).secret)  # type: ignore[union-attr]
        confirm_totp(enrolment.method_id, pyotp.TOTP(secret).now())

    # User B belongs to tenant B. Asking for a session on tenant A's host.
    response = log_in(Client(), HOST_A, "b@example.md", secret)
    assert response.status_code == 401
    assert response.json()["code"] == "auth.no_access_to_tenant"
