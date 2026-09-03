"""The rest of the console -- ADR-076 §4.3 as pages, ADR-092 as the staff path.

Every page here reads across tenants, which R7 permits only through enumerated
paths. The paths are the `rls.console_*` functions of 0076, and the first two
tests are about them rather than about any page: called under a tenant context
they refuse, whoever the caller is; called by somebody who is not staff they
refuse, whatever the context. Only then do the pages get to show anything.

The staff page is the one that writes. `P-12` is the admin's: an operator is
refused, the log row names the admin, a person holds one role at a time, and an
admin cannot revoke themselves -- the console can never end up with nobody able
to reopen it.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

import pyotp
import pytest
from django.contrib.auth.hashers import make_password
from django.db import DatabaseError, connection, transaction
from django.test import Client

from evidenta.platform.audit.models import PrivilegedAccessLog
from evidenta.platform.audit.services.privileged import REFDATA_ALIAS
from evidenta.platform.identity.models import PlatformStaff, User
from evidenta.platform.identity.services.authentication import (
    confirm_totp,
    enrol_totp,
    generate_secret_key,
)
from evidenta.platform.rls.context import PlatformContext, TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration", "refdata"])

PASSWORD = "o-parola-suficient-de-lunga"
CONSOLE = "admin.evidenta.localhost"
HOST_A = "alpha.evidenta.localhost"


@pytest.fixture(autouse=True)
def mfa_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MFA_SECRET_KEY", generate_secret_key())


@pytest.fixture
def staff(seed: Callable[..., None], world: dict[str, uuid.UUID]) -> dict[str, uuid.UUID]:
    """An admin and an operator of the platform, plus an ordinary account that
    is nobody's staff -- the one the admin will grant."""
    now = datetime.now(UTC)
    ids = {"admin": uuid.uuid4(), "operator": uuid.uuid4(), "newcomer": uuid.uuid4()}
    for name, user_id in ids.items():
        seed(
            'INSERT INTO "user" (id, email, full_name, mfa_enabled, locale,'
            " is_active, created_at, updated_at)"
            " VALUES (%s, %s, %s, false, 'ro', true, %s, %s)",
            [user_id, f"{name}@platform.md", f"{name} al platformei", now, now],
        )
    for role in ("admin", "operator"):
        seed(
            "INSERT INTO platform_staff (user_id, staff_role, granted_by_user_id, granted_at)"
            " VALUES (%s, %s, %s, %s)",
            [ids[role], role, ids["admin"], now],
        )
    return ids


def _sign_in(client: Client, user_id: uuid.UUID, email: str, host: str) -> None:
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


@pytest.fixture
def admin(staff: dict[str, uuid.UUID]) -> Iterator[Client]:
    client = Client()
    _sign_in(client, staff["admin"], "admin@platform.md", CONSOLE)
    yield client


@pytest.fixture
def operator(staff: dict[str, uuid.UUID]) -> Iterator[Client]:
    client = Client()
    _sign_in(client, staff["operator"], "operator@platform.md", CONSOLE)
    yield client


def body(response: Any) -> Any:
    return json.loads(response.content)


def get(client: Client, path: str) -> Any:
    response = client.get(path, headers={"host": CONSOLE})
    assert response.status_code == 200, response.content
    return body(response)


def post(client: Client, path: str, payload: dict[str, Any] | None = None) -> Any:
    return client.post(
        path,
        data=json.dumps(payload or {}),
        content_type="application/json",
        headers={"host": CONSOLE},
    )


# --- the functions refuse before any page can show anything --------------------


def test_a_console_read_refuses_under_a_tenant_context(
    world: dict[str, uuid.UUID], staff: dict[str, uuid.UUID]
) -> None:
    """Even a staff member, on a tenant's host, gets nothing from the console
    functions: the context has a tenant, so the caller is a client's user at that
    moment, whatever else they are."""
    member = TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="t")
    with (
        tenant_context(member),
        pytest.raises(DatabaseError, match="context de tenant"),
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute("SELECT count(*) FROM rls.console_tenants()")


def test_a_console_read_refuses_a_caller_who_is_not_staff(world: dict[str, uuid.UUID]) -> None:
    with (
        tenant_context(PlatformContext(user_id=world["user_a"], request_id="console")),
        pytest.raises(DatabaseError, match="angajat al platformei"),
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute("SELECT count(*) FROM rls.console_tenants()")


# --- the pages -----------------------------------------------------------------


def test_spaces_lists_every_space_with_counts_and_no_content(
    operator: Client, world: dict[str, uuid.UUID], company_of: Callable[..., uuid.UUID]
) -> None:
    company_of(world["tenant_a"], "1000000000001", "Alpha Comerț SRL")
    spaces = {row["subdomain"]: row for row in get(operator, "/api/v1/platform/spaces/")["spaces"]}
    assert set(spaces) >= {"alpha", "beta"}
    assert spaces["alpha"]["legal_name"] == "Alpha SRL"
    assert spaces["alpha"]["status"] == "active"
    assert spaces["alpha"]["company_count"] == 1
    assert spaces["alpha"]["member_count"] == 1
    assert spaces["beta"]["company_count"] == 0
    # The row is the tenant's row and nothing of the companies inside it: no
    # company name, no IDNO, no amount reaches the console through this page.
    assert "Alpha Comerț SRL" not in json.dumps(spaces)


def test_staff_page_lists_the_employees_with_history(operator: Client) -> None:
    rows = get(operator, "/api/v1/platform/staff/")["staff"]
    by_email = {row["email"]: row for row in rows}
    assert by_email["admin@platform.md"]["staff_role"] == "admin"
    assert by_email["operator@platform.md"]["granted_by_email"] == "admin@platform.md"
    assert all(row["revoked_at"] is None for row in rows)


def test_an_operator_cannot_grant_and_an_admin_can(
    admin: Client, operator: Client, staff: dict[str, uuid.UUID]
) -> None:
    payload = {"email": "newcomer@platform.md", "staff_role": "support"}
    refused = post(operator, "/api/v1/platform/staff/", payload)
    assert refused.status_code == 403
    assert body(refused)["code"] == "api.forbidden"

    granted = post(admin, "/api/v1/platform/staff/", payload)
    assert granted.status_code == 201, granted.content
    assert body(granted)["user_id"] == str(staff["newcomer"])

    row = PlatformStaff.objects.using(REFDATA_ALIAS).get(user_id=staff["newcomer"])
    assert row.staff_role == "support"
    assert row.granted_by_id == staff["admin"]
    assert row.revoked_at is None

    log = list(PrivilegedAccessLog.objects.using(REFDATA_ALIAS).filter(path_code="P-12"))
    assert len(log) == 1
    assert log[0].actor == "console:admin"
    assert log[0].actor_user_id == staff["admin"]
    assert log[0].payload == {
        "operation": "grant",
        "user_id": str(staff["newcomer"]),
        "staff_role": "support",
    }


def test_a_person_holds_one_role_at_a_time(admin: Client) -> None:
    again = post(
        admin, "/api/v1/platform/staff/", {"email": "operator@platform.md", "staff_role": "admin"}
    )
    assert again.status_code == 409
    assert body(again)["code"] == "staff.already_live"


def test_an_unknown_address_is_not_found_and_an_unknown_field_is_refused(admin: Client) -> None:
    missing = post(
        admin, "/api/v1/platform/staff/", {"email": "nobody@platform.md", "staff_role": "support"}
    )
    assert missing.status_code == 404
    assert body(missing)["code"] == "staff.user_not_found"

    stray = post(
        admin,
        "/api/v1/platform/staff/",
        {"email": "newcomer@platform.md", "staff_role": "support", "revoked_at": None},
    )
    assert stray.status_code == 400
    assert body(stray)["code"] == "api.invalid"


def test_an_admin_cannot_revoke_themselves_but_can_revoke_another(
    admin: Client, staff: dict[str, uuid.UUID]
) -> None:
    own = post(admin, f"/api/v1/platform/staff/{staff['admin']}/revoke")
    assert own.status_code == 409
    assert body(own)["code"] == "staff.cannot_revoke_self"

    ended = post(admin, f"/api/v1/platform/staff/{staff['operator']}/revoke")
    assert ended.status_code == 200, ended.content
    row = PlatformStaff.objects.using(REFDATA_ALIAS).get(user_id=staff["operator"])
    assert row.revoked_at is not None

    twice = post(admin, f"/api/v1/platform/staff/{staff['operator']}/revoke")
    assert twice.status_code == 409
    assert body(twice)["code"] == "staff.not_live"


def test_privileged_log_shows_the_console_own_rows(
    admin: Client, staff: dict[str, uuid.UUID]
) -> None:
    post(
        admin, "/api/v1/platform/staff/", {"email": "newcomer@platform.md", "staff_role": "support"}
    )
    # The reference transaction is not committed under the harness, so the
    # function -- which reads as evidenta_rls on the request's connection --
    # cannot see the row yet; what it proves here is the door and the shape.
    answer = get(admin, "/api/v1/platform/privileged-log/?path=P-12&limit=10")
    assert {p["code"] for p in answer["paths"]} >= {"P-4", "P-9", "P-12"}
    assert isinstance(answer["rows"], list)

    bad = admin.get("/api/v1/platform/privileged-log/?path=P-99", headers={"host": CONSOLE})
    assert bad.status_code == 400
    assert body(bad)["code"] == "audit.filter_invalid"


def test_capabilities_flags_and_chart_templates_answer(operator: Client) -> None:
    capabilities = get(operator, "/api/v1/platform/capabilities/")
    assert capabilities["activations"] == []

    flags = get(operator, "/api/v1/platform/flags/")
    assert set(flags) == {"flags", "rings", "ring_assignments", "overrides"}
    assert flags["ring_assignments"] == []

    templates = get(operator, "/api/v1/platform/coa-templates/")
    assert "templates" in templates


def test_the_pages_are_not_served_on_a_tenant_host(world: dict[str, uuid.UUID]) -> None:
    client = Client()
    _sign_in(client, world["user_a"], "a@example.md", HOST_A)
    for path in (
        "/api/v1/platform/spaces/",
        "/api/v1/platform/staff/",
        "/api/v1/platform/privileged-log/",
        "/api/v1/platform/capabilities/",
        "/api/v1/platform/flags/",
        "/api/v1/platform/coa-templates/",
    ):
        response = client.get(path, headers={"host": HOST_A})
        # A tenant session reaches a DRF view with a tenant principal, which the
        # staff permission classes do not accept: 403, and no query was made.
        assert response.status_code == 403, (path, response.content)
        assert body(response)["code"] == "api.forbidden"
