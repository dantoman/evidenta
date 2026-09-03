"""The support grant, end to end -- ADR-077 as a suite, under the application role (T1).

ADR-077 §7 names three tests and this file starts with them, each a statement
about the predicates rather than about a screen:

1. an unapproved grant with `app.support_grant_id` set reaches **zero rows**;
2. an approved grant whose `expires_at` has passed reaches zero rows, with no job
   having run;
3. a grant approved on tenant A, a session on tenant B: zero rows.

Then the rest of the mechanism: the request is `P-7` and only `support` on the
console may make it; the approval is the client's, through the ordinary policy,
with the permission ADR-020 requires; a support session signs in on the client's
host, sees, and cannot write -- refused by the middleware and, underneath, by a
read-only transaction (ADR-094); revocation ends the session at its next request.
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
from django.db import DatabaseError, connection, transaction
from django.test import Client

from evidenta.platform.identity.models import User
from evidenta.platform.identity.services import roles as role_service
from evidenta.platform.identity.services.authentication import (
    confirm_totp,
    enrol_totp,
    generate_secret_key,
)
from evidenta.platform.rls.context import PlatformContext, TenantContext, tenant_context
from evidenta.platform.support.models import SupportGrant
from evidenta.platform.tenancy.models import Tenant

pytestmark = pytest.mark.django_db(databases=["default", "migration", "refdata"])

PASSWORD = "o-parola-suficient-de-lunga"
CONSOLE = "admin.evidenta.localhost"
HOST_A = "alpha.evidenta.localhost"
HOST_B = "beta.evidenta.localhost"


@pytest.fixture(autouse=True)
def mfa_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MFA_SECRET_KEY", generate_secret_key())


@pytest.fixture
def support(seed: Callable[..., None], world: dict[str, uuid.UUID]) -> uuid.UUID:
    """A `support` employee of the platform, member of no space."""
    now = datetime.now(UTC)
    user_id = uuid.uuid4()
    seed(
        'INSERT INTO "user" (id, email, full_name, mfa_enabled, locale,'
        " is_active, created_at, updated_at)"
        " VALUES (%s, %s, %s, false, 'ro', true, %s, %s)",
        [user_id, "support@platform.md", "Suport", now, now],
    )
    seed(
        "INSERT INTO platform_staff (user_id, staff_role, granted_by_user_id, granted_at)"
        " VALUES (%s, 'support', %s, %s)",
        [user_id, user_id, now],
    )
    return user_id


def seed_grant(
    seed: Callable[..., None],
    *,
    tenant_id: uuid.UUID,
    requested_by: uuid.UUID,
    approved_by: uuid.UUID | None = None,
    expires_in: timedelta | None = None,
    company_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """A grant row through the admin connection -- the shape the function writes,
    with the approval the client would give."""
    now = datetime.now(UTC)
    grant_id = uuid.uuid4()
    approved_at = now if approved_by else None
    expires_at = (now + expires_in) if approved_by and expires_in is not None else None
    seed(
        "INSERT INTO support_grant (id, tenant_id, company_id, requested_by_user_id,"
        " request_ref, justification, requested_at, approved_by_user_id, approved_at, expires_at)"
        " VALUES (%s, %s, %s, %s, 'T-1', 'test', %s, %s, %s, %s)",
        [grant_id, tenant_id, company_id, requested_by, now, approved_by, approved_at, expires_at],
    )
    return grant_id


def on_grant(tenant_id: uuid.UUID, user_id: uuid.UUID, grant_id: uuid.UUID) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id, user_id=user_id, request_id="support", support_grant_id=grant_id
    )


# --- ADR-077 §7: the three predicate tests --------------------------------------------------


def test_an_unapproved_grant_reaches_nothing(
    seed: Callable[..., None], world: dict[str, uuid.UUID], support: uuid.UUID
) -> None:
    grant = seed_grant(seed, tenant_id=world["tenant_a"], requested_by=support)
    with tenant_context(on_grant(world["tenant_a"], support, grant)):
        assert not Tenant.objects.exists()


def test_an_expired_grant_reaches_nothing_without_any_job(
    seed: Callable[..., None], world: dict[str, uuid.UUID], support: uuid.UUID
) -> None:
    """Approved an hour ago for a window that ended a minute ago. Nothing ran to
    change its state; the predicate compares `expires_at` with `now()`."""
    now = datetime.now(UTC)
    grant_id = uuid.uuid4()
    seed(
        "INSERT INTO support_grant (id, tenant_id, requested_by_user_id, request_ref,"
        " justification, requested_at, approved_by_user_id, approved_at, expires_at)"
        " VALUES (%s, %s, %s, 'T-1', 'test', %s, %s, %s, %s)",
        [
            grant_id,
            world["tenant_a"],
            support,
            now - timedelta(hours=2),
            world["user_a"],
            now - timedelta(hours=1),
            now - timedelta(minutes=1),
        ],
    )
    with tenant_context(on_grant(world["tenant_a"], support, grant_id)):
        assert not Tenant.objects.exists()


def test_a_grant_on_one_tenant_opens_nothing_on_another(
    seed: Callable[..., None], world: dict[str, uuid.UUID], support: uuid.UUID
) -> None:
    grant = seed_grant(
        seed,
        tenant_id=world["tenant_a"],
        requested_by=support,
        approved_by=world["user_a"],
        expires_in=timedelta(hours=1),
    )
    with tenant_context(on_grant(world["tenant_b"], support, grant)):
        assert not Tenant.objects.exists()
    # And the same grant, on its own tenant, opens exactly that tenant.
    with tenant_context(on_grant(world["tenant_a"], support, grant)):
        assert [t.subdomain for t in Tenant.objects.all()] == ["alpha"]


def test_a_company_scoped_grant_opens_one_company(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    support: uuid.UUID,
    company_of: Callable[..., uuid.UUID],
) -> None:
    from evidenta.platform.tenancy.models import Company

    first = company_of(world["tenant_a"], "1000000000001", "Alpha Unu SRL")
    company_of(world["tenant_a"], "1000000000002", "Alpha Doi SRL")
    grant = seed_grant(
        seed,
        tenant_id=world["tenant_a"],
        requested_by=support,
        approved_by=world["user_a"],
        expires_in=timedelta(hours=1),
        company_id=first,
    )
    with tenant_context(on_grant(world["tenant_a"], support, grant)):
        assert [c.id for c in Company.objects.all()] == [first]


def test_the_session_variable_alone_grants_nothing(
    world: dict[str, uuid.UUID], support: uuid.UUID
) -> None:
    """ADR-077 §4 (2): a value nobody wrote a row for is a value that opens nothing."""
    with tenant_context(on_grant(world["tenant_a"], support, uuid.uuid4())):
        assert not Tenant.objects.exists()


# --- the request: P-7 from the console -------------------------------------------------------


def _sign_in(client: Client, user_id: uuid.UUID, email: str, host: str) -> str:
    with tenant_context(PlatformContext(user_id=user_id, request_id="setup")):
        User.objects.filter(pk=user_id).update(password_hash=make_password(PASSWORD))
        enrolment = enrol_totp(user_id, label="phone")
        secret = str(pyotp.parse_uri(enrolment.provisioning_uri).secret)  # type: ignore[union-attr]
        confirm_totp(enrolment.method_id, pyotp.TOTP(secret).now())
    response = client.post(
        "/api/v1/auth/login",
        data=json.dumps(
            {"email": email, "password": PASSWORD, "totp_code": pyotp.TOTP(secret).now()}
        ),
        content_type="application/json",
        headers={"host": host},
    )
    assert response.status_code == 200, response.content
    return secret


def _login(client: Client, email: str, secret: str, host: str) -> Any:
    return client.post(
        "/api/v1/auth/login",
        data=json.dumps(
            {"email": email, "password": PASSWORD, "totp_code": pyotp.TOTP(secret).now()}
        ),
        content_type="application/json",
        headers={"host": host},
    )


def body(response: Any) -> Any:
    return json.loads(response.content)


@pytest.fixture
def console(support: uuid.UUID) -> Iterator[Client]:
    client = Client()
    _sign_in(client, support, "support@platform.md", CONSOLE)
    yield client


def request_grant(client: Client, space: str = "alpha", **overrides: Any) -> Any:
    payload = {"space": space, "request_ref": "T-4711", "justification": "balanța nu se închide"}
    payload.update(overrides)
    return client.post(
        "/api/v1/platform/support-grants/",
        data=json.dumps(payload),
        content_type="application/json",
        headers={"host": CONSOLE},
    )


def test_support_requests_a_grant_and_the_log_names_the_ticket(
    console: Client, world: dict[str, uuid.UUID], support: uuid.UUID
) -> None:
    response = request_grant(console)
    assert response.status_code == 201, response.content
    grant_id = uuid.UUID(body(response)["grant_id"])

    # Unapproved, in the client's space, by the support employee.
    with tenant_context(
        TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="t")
    ):
        grant = SupportGrant.objects.get(pk=grant_id)
        assert grant.approved_at is None
        assert grant.requested_by_id == support
        assert grant.request_ref == "T-4711"

    # The console lists it; the log has its P-7 row with the justification.
    listing = body(console.get("/api/v1/platform/support-grants/", headers={"host": CONSOLE}))
    assert [g["status"] for g in listing["grants"]] == ["pending"]
    assert listing["grants"][0]["subdomain"] == "alpha"

    # Written by the function on the request's own connection, so it is read the
    # way the console reads it -- through `rls.console_privileged_log` -- not via
    # the reference connection, which cannot see this transaction.
    log = body(console.get("/api/v1/platform/privileged-log/?path=P-7", headers={"host": CONSOLE}))[
        "rows"
    ]
    assert len(log) == 1
    assert log[0]["actor_user_id"] == str(support)
    assert log[0]["subject_subdomain"] == "alpha"
    assert log[0]["justification"] == "balanța nu se închide"
    assert log[0]["payload"]["request_ref"] == "T-4711"

    # A second request for the same space while one is pending is refused.
    again = request_grant(console)
    assert again.status_code == 409
    assert body(again)["code"] == "support.request_exists"


def test_a_request_needs_a_ticket_and_a_space(
    console: Client, world: dict[str, uuid.UUID], support: uuid.UUID
) -> None:
    # A blank ticket is stopped at the door by the serializer ...
    empty = request_grant(console, request_ref="  ")
    assert empty.status_code == 400
    assert body(empty)["code"] == "api.invalid"

    nowhere = request_grant(console, space="gamma")
    assert nowhere.status_code == 404
    assert body(nowhere)["code"] == "support.space_not_found"

    # ... and, should a caller reach the function some other way, by the function.
    with (
        tenant_context(PlatformContext(user_id=support, request_id="console")),
        pytest.raises(DatabaseError, match="numarul solicitarii si justificarea"),
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute(
            "SELECT rls.request_support_access(%s, NULL, 'T-1', '   ')", [world["tenant_a"]]
        )


def test_only_support_requests_a_grant(
    seed: Callable[..., None], world: dict[str, uuid.UUID]
) -> None:
    """An `operator` is staff and may read the page, and is refused the request:
    ADR-076 §4.1 gives `P-7` to `support` alone."""
    now = datetime.now(UTC)
    operator = uuid.uuid4()
    seed(
        'INSERT INTO "user" (id, email, full_name, mfa_enabled, locale, is_active,'
        " created_at, updated_at) VALUES (%s, 'operator@platform.md', 'Operator', false, 'ro',"
        " true, %s, %s)",
        [operator, now, now],
    )
    seed(
        "INSERT INTO platform_staff (user_id, staff_role, granted_by_user_id, granted_at)"
        " VALUES (%s, 'operator', %s, %s)",
        [operator, operator, now],
    )
    client = Client()
    _sign_in(client, operator, "operator@platform.md", CONSOLE)
    refused = request_grant(client)
    assert refused.status_code == 403
    assert body(refused)["code"] == "api.forbidden"
    listing = client.get("/api/v1/platform/support-grants/", headers={"host": CONSOLE})
    assert listing.status_code == 200


def test_the_function_refuses_a_caller_under_a_tenant_context(
    world: dict[str, uuid.UUID], support: uuid.UUID
) -> None:
    """Even the support employee: on a client's host the request is not theirs to make."""
    with (
        tenant_context(TenantContext(tenant_id=world["tenant_a"], user_id=support, request_id="t")),
        pytest.raises(DatabaseError, match="doar de pe consola"),
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute(
            "SELECT rls.request_support_access(%s, NULL, 'T-1', 'x')", [world["tenant_a"]]
        )


# --- the approval: the client's, through the ordinary policy -----------------------------------


@pytest.fixture
def owner(world: dict[str, uuid.UUID]) -> Iterator[tuple[Client, str]]:
    """The owner of tenant A, signed in on its host, with the administration role
    composed from the catalogue -- which now includes `tenant.approve_support_access`."""
    context = TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="s")
    with tenant_context(context):
        role_service.create_system_roles(world["tenant_a"])
    client = Client()
    secret = _sign_in(client, world["user_a"], "a@example.md", HOST_A)
    yield client, secret


def test_the_client_approves_and_the_window_is_bounded(
    console: Client, owner: tuple[Client, str], world: dict[str, uuid.UUID]
) -> None:
    client, _ = owner
    grant_id = body(request_grant(console))["grant_id"]

    listing = body(client.get("/api/v1/support/grants", headers={"host": HOST_A}))
    assert [g["status"] for g in listing["grants"]] == ["pending"]
    assert listing["grants"][0]["request_ref"] == "T-4711"

    too_long = client.post(
        f"/api/v1/support/grants/{grant_id}/approve",
        data=json.dumps({"hours": 73}),
        content_type="application/json",
        headers={"host": HOST_A},
    )
    assert too_long.status_code == 400  # the serializer's ceiling, before the service's

    approved = client.post(
        f"/api/v1/support/grants/{grant_id}/approve",
        data=json.dumps({}),
        content_type="application/json",
        headers={"host": HOST_A},
    )
    assert approved.status_code == 200, approved.content
    grant = body(approved)["grant"]
    assert grant["status"] == "active"
    assert grant["expires_at"] is not None
    expires = datetime.fromisoformat(grant["expires_at"])
    approved_at = datetime.fromisoformat(grant["approved_at"])
    assert expires - approved_at == timedelta(hours=24)

    twice = client.post(
        f"/api/v1/support/grants/{grant_id}/approve",
        data=json.dumps({}),
        content_type="application/json",
        headers={"host": HOST_A},
    )
    assert twice.status_code == 409
    assert body(twice)["code"] == "support.not_pending"


def test_a_member_without_the_key_cannot_approve(
    console: Client, world: dict[str, uuid.UUID]
) -> None:
    """The owner of tenant A as the `world` fixture seeds them: a system role with
    no permissions in it. Membership alone is not consent."""
    grant_id = body(request_grant(console))["grant_id"]
    client = Client()
    _sign_in(client, world["user_a"], "a@example.md", HOST_A)
    refused = client.post(
        f"/api/v1/support/grants/{grant_id}/approve",
        data=json.dumps({}),
        content_type="application/json",
        headers={"host": HOST_A},
    )
    assert refused.status_code == 403
    assert body(refused)["code"] == "api.forbidden"


# --- the support session: sees, cannot write, ends with the grant ------------------------------


def test_a_support_session_reads_and_cannot_write_and_ends_on_revocation(
    console: Client,
    owner: tuple[Client, str],
    world: dict[str, uuid.UUID],
    support: uuid.UUID,
    company_of: Callable[..., uuid.UUID],
) -> None:
    client, _ = owner
    company_of(world["tenant_a"], "1000000000001", "Alpha SRL")
    grant_id = body(request_grant(console))["grant_id"]
    client.post(
        f"/api/v1/support/grants/{grant_id}/approve",
        data=json.dumps({"hours": 2}),
        content_type="application/json",
        headers={"host": HOST_A},
    )

    # The support employee signs in on the CLIENT's host, as ADR-077 §6 says --
    # the same form, the same password and second factor.
    supporter = Client()
    secret = _sign_in(supporter, support, "support@platform.md", HOST_A)
    who = body(supporter.get("/api/v1/auth/whoami", headers={"host": HOST_A}))
    assert who["tenant_id"] == str(world["tenant_a"])
    assert who["support_grant_id"] == grant_id

    # Reads work: the session's own grant, and the client's companies.
    session = body(supporter.get("/api/v1/support/session", headers={"host": HOST_A}))
    assert session["grant"]["request_ref"] == "T-4711"
    companies = supporter.get("/api/v1/companies", headers={"host": HOST_A})
    assert companies.status_code == 200
    assert [c["legal_name"] for c in body(companies)] == ["Alpha SRL"]

    # Writes do not, before any view runs.
    write = supporter.post(
        "/api/v1/masterdata/partners/",
        data=json.dumps({"legal_name": "Furnizor SRL"}),
        content_type="application/json",
        headers={"host": HOST_A},
    )
    assert write.status_code == 403
    assert body(write)["code"] == "support.read_only"

    # And not on tenant B, where there is no grant.
    elsewhere = _login(supporter, "support@platform.md", secret, HOST_B)
    assert elsewhere.status_code == 401
    assert body(elsewhere)["code"] == "auth.no_access_to_tenant"

    # The client revokes; the support session is over at its next request.
    revoked = client.post(
        f"/api/v1/support/grants/{grant_id}/revoke",
        data=json.dumps({}),
        content_type="application/json",
        headers={"host": HOST_A},
    )
    assert revoked.status_code == 200, revoked.content
    assert body(revoked)["grant"]["status"] == "revoked"
    after = supporter.get("/api/v1/auth/whoami", headers={"host": HOST_A})
    assert after.status_code == 401

    # And a new sign-in on the revoked grant is refused.
    again = _login(supporter, "support@platform.md", secret, HOST_A)
    assert again.status_code == 401


def test_the_read_only_transaction_holds_under_the_grant(
    seed: Callable[..., None], world: dict[str, uuid.UUID], support: uuid.UUID
) -> None:
    """ADR-094, measured: under a support context the database itself refuses a
    write -- whatever policy or service might have let it through."""
    grant = seed_grant(
        seed,
        tenant_id=world["tenant_a"],
        requested_by=support,
        approved_by=world["user_a"],
        expires_in=timedelta(hours=1),
    )
    with (
        tenant_context(on_grant(world["tenant_a"], support, grant)),
        pytest.raises(DatabaseError, match="read-only transaction"),
        transaction.atomic(),
    ):
        Tenant.objects.filter(pk=world["tenant_a"]).update(legal_name="Alpha Modificată SRL")
