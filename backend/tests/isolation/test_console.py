"""The platform's console, end to end -- ADR-076 as a suite.

ADR-076 §2 is one sentence: *the platform administrator administers the platform,
not the data*. §5 promises three automatic checks, and this file is (b) -- a
console session, under the application role, reaches no tenant row -- together
with the doors that make the console usable at all.

The claims, in order of what they would cost to get wrong:

* a console context reaches **no** tenant-scoped row -- an error, not an empty
  list, because the tenant setting is absent and `app.current_tenant_id()` is
  fail-closed (R4's second branch, measured)
* a console session does not authenticate on a tenant's host, and a tenant's
  session does not authenticate on the console
* the console serves the platform's routes and answers 404 to everything else
* a person who is not staff is refused **after** their credentials were accepted,
  with a code that says so
* `support` cannot write a fiscal parameter; `operator` can, and the write leaves
  a `P-4` row naming them
* a draft without a margin cannot be activated; one with a margin can, once

Runs under the application role like the rest of suite 1 (T1). The reference
writes go through the reference-data connection, as they do in production, and
are taken back by the next test's seed fixture.
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

from evidenta.fiscal.parameters.models import FiscalParameter
from evidenta.platform.audit.models import PrivilegedAccessLog
from evidenta.platform.audit.services.privileged import REFDATA_ALIAS
from evidenta.platform.identity.models import User
from evidenta.platform.identity.services.authentication import (
    confirm_totp,
    enrol_totp,
    generate_secret_key,
)
from evidenta.platform.rls.context import PlatformContext, TenantContext, tenant_context
from evidenta.platform.tenancy.models import Company, Tenant

pytestmark = pytest.mark.django_db(databases=["default", "migration", "refdata"])

PASSWORD = "o-parola-suficient-de-lunga"
CONSOLE = "admin.evidenta.localhost"
HOST_A = "alpha.evidenta.localhost"
PARAMETERS = "/api/v1/platform/fiscal-parameters/"
ME = "/api/v1/platform/staff/me"


@pytest.fixture(autouse=True)
def mfa_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MFA_SECRET_KEY", generate_secret_key())


@pytest.fixture
def staff(seed: Callable[..., None], world: dict[str, uuid.UUID]) -> dict[str, uuid.UUID]:
    """Two employees of the platform -- an operator and a support -- and no
    membership in any tenant for either. Seeded through the admin connection,
    the way the first staff grant happens in production (a DBA act)."""
    now = datetime.now(UTC)
    ids = {"operator": uuid.uuid4(), "support": uuid.uuid4()}
    for role, user_id in ids.items():
        seed(
            'INSERT INTO "user" (id, email, full_name, mfa_enabled, locale,'
            " is_active, created_at, updated_at)"
            " VALUES (%s, %s, %s, false, 'ro', true, %s, %s)",
            [user_id, f"{role}@platform.md", f"{role} al platformei", now, now],
        )
        seed(
            "INSERT INTO platform_staff (user_id, staff_role, granted_by_user_id, granted_at)"
            " VALUES (%s, %s, %s, %s)",
            [user_id, role, user_id, now],
        )
    return ids


def _sign_in(client: Client, user_id: uuid.UUID, email: str, host: str) -> None:
    """Password plus a confirmed second factor, then the real login endpoint.

    Enrolment runs under a platform context: the person belongs to no tenant,
    and the self-row policies on `user` and `mfa_method` need only the user.
    """
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
def operator(staff: dict[str, uuid.UUID]) -> Iterator[Client]:
    client = Client()
    _sign_in(client, staff["operator"], "operator@platform.md", CONSOLE)
    yield client


@pytest.fixture
def support(staff: dict[str, uuid.UUID]) -> Iterator[Client]:
    client = Client()
    _sign_in(client, staff["support"], "support@platform.md", CONSOLE)
    yield client


def body(response: Any) -> Any:
    return json.loads(response.content)


# --- the boundary ------------------------------------------------------------


def test_a_console_context_reaches_no_tenant_row(
    world: dict[str, uuid.UUID],
    staff: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
) -> None:
    """ADR-076 §5 (b), measured rather than asserted from the design.

    There is a tenant with a company in it. Under a console context, on the
    application connection, asking for either is **refused by the database**:
    every tenant policy opens with `... = app.current_tenant_id()`, and that
    function raises when the setting is absent. R4 names two outcomes -- zero
    rows or an error -- and this is the second; what matters is what does not
    happen: no row comes back.

    **What this test found on the way.** Its first run answered zero rows for
    `tenant` and no error at all from `app.current_tenant_id()`. The cause was
    not the policy: `SET LOCAL` outlives the savepoint that set it, and the
    member context opened a few lines above had left `app.tenant_id` in the
    transaction, which the console context then inherited -- `_apply` skipped
    absent keys instead of clearing them. It clears them now, and the member
    context above is kept here on purpose: the sequence is the regression.
    """
    company_of(world["tenant_a"], "1000000000001", "Alpha SRL")

    # The rows exist, for a member of the tenant. (`company` needs a
    # `company_access` row on top of membership -- ADR-004 -- so the positive
    # check is on `tenant`; the negative one is on both.)
    member = TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="t")
    with tenant_context(member):
        assert Tenant.objects.filter(pk=world["tenant_a"]).exists()

    with tenant_context(PlatformContext(user_id=staff["operator"], request_id="console")):
        # Each refused statement in its own savepoint, so the aborted statement
        # does not take the surrounding transaction down with it.
        with (
            pytest.raises(DatabaseError, match="lipseste contextul de tenant"),
            transaction.atomic(),
        ):
            Tenant.objects.exists()
        with (
            pytest.raises(DatabaseError, match="lipseste contextul de tenant"),
            transaction.atomic(),
        ):
            Company.objects.count()
        with (
            pytest.raises(DatabaseError, match="lipseste contextul de tenant"),
            transaction.atomic(),
            connection.cursor() as cursor,
        ):
            cursor.execute("SELECT app.current_tenant_id()")


def test_login_on_the_console_binds_the_session_to_no_tenant(operator: Client) -> None:
    who = body(operator.get("/api/v1/auth/whoami", headers={"host": CONSOLE}))
    assert who["tenant_id"] is None
    assert who["actor_firm_id"] is None

    me = body(operator.get(ME, headers={"host": CONSOLE}))
    assert me["staff_role"] == "operator"
    assert me["email"] == "operator@platform.md"


def test_a_person_who_is_not_staff_is_refused_after_their_credentials_pass(
    world: dict[str, uuid.UUID],
) -> None:
    """The owner of tenant A has a valid password and second factor. On the
    console that earns them `auth.no_access_to_console` -- not "wrong password",
    because the password was right, and retrying it will never help."""
    context = TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="s")
    with tenant_context(context):
        User.objects.filter(pk=world["user_a"]).update(password_hash=make_password(PASSWORD))
        enrolment = enrol_totp(world["user_a"], label="phone")
        secret = str(pyotp.parse_uri(enrolment.provisioning_uri).secret)  # type: ignore[union-attr]
        confirm_totp(enrolment.method_id, pyotp.TOTP(secret).now())

    response = Client().post(
        "/api/v1/auth/login",
        data=json.dumps(
            {"email": "a@example.md", "password": PASSWORD, "totp_code": pyotp.TOTP(secret).now()}
        ),
        content_type="application/json",
        headers={"host": CONSOLE},
    )
    assert response.status_code == 401
    assert body(response)["code"] == "auth.no_access_to_console"


def test_sessions_do_not_cross_between_the_console_and_a_tenant_host(
    operator: Client, world: dict[str, uuid.UUID]
) -> None:
    # The console session, presented on a tenant's host.
    response = operator.get("/api/v1/workspace", headers={"host": HOST_A})
    assert response.status_code == 401
    assert body(response)["code"] == "auth.session_tenant_mismatch"

    # A tenant session, presented on the console.
    tenant_client = Client()
    _sign_in(tenant_client, world["user_a"], "a@example.md", HOST_A)
    response = tenant_client.get(ME, headers={"host": CONSOLE})
    assert response.status_code == 401
    assert body(response)["code"] == "auth.session_tenant_mismatch"


def test_the_console_serves_only_the_platform_routes(operator: Client) -> None:
    """A tenant route asked for on `admin.` does not exist there -- 404, signed
    in or not, so a probe learns nothing from the difference."""
    for client in (operator, Client()):
        response = client.get("/api/v1/companies", headers={"host": CONSOLE})
        assert response.status_code == 404
        assert body(response)["code"] == "console.not_found"


def test_the_platform_routes_do_not_exist_on_a_tenant_host(world: dict[str, uuid.UUID]) -> None:
    """The other direction: `/api/v1/platform/` on `alpha.` is refused by the
    tenant resolver (no session, 401) and would run, at most, with a tenant
    principal the permission class does not accept. Here: the refusal."""
    response = Client().get(ME, headers={"host": HOST_A})
    assert response.status_code == 401


# --- the fiscal door ---------------------------------------------------------

ACT = {
    "act_type": "test",
    "act_number": "TEST-9/9999",
    "act_date": "2000-01-01",
    "title": "Act sintetic pentru suita consolei",
    "effective_from": "2000-01-01",
    "publication": {"gazette_year": 2000, "gazette_number": "TEST 0", "article": "art. 0"},
}


def draft(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "parameter_key": "test.console.alpha",
        "value_type": "integer",
        "value": 7,
        "act": ACT,
        "confidence": "provisional",
        "provisional_reason": "test: inferred, reason supplied so the check passes",
        "observed_in": "the value appears in the synthetic act; its margin was not read",
    }
    payload.update(overrides)
    return payload


def post(client: Client, path: str, payload: dict[str, Any] | None = None) -> Any:
    return client.post(
        path,
        data=json.dumps(payload or {}),
        content_type="application/json",
        headers={"host": CONSOLE},
    )


def log_rows() -> list[PrivilegedAccessLog]:
    """`privileged_access_log` is readable by nobody through the application
    (spec-a §6.3); the reference role reads its own rows, and the loader tests
    read it the same way."""
    return list(
        PrivilegedAccessLog.objects.using(REFDATA_ALIAS)
        .filter(path_code="P-4")
        .order_by("occurred_at")
    )


def test_support_cannot_write_a_parameter(support: Client) -> None:
    """`OD-113` said nothing in code refused a `support` the `P-4` call. Now
    something does, at the one door that exists."""
    response = post(support, PARAMETERS, draft())
    assert response.status_code == 403
    assert body(response)["code"] == "api.forbidden"

    listing = support.get(PARAMETERS, headers={"host": CONSOLE})
    assert listing.status_code == 200  # reading is metadata; any employee may


def test_an_operator_writes_a_draft_and_the_log_names_them(
    operator: Client, staff: dict[str, uuid.UUID]
) -> None:
    response = post(operator, PARAMETERS, draft())
    assert response.status_code == 201, response.content
    answer = body(response)
    assert answer["outcome"] == "created"
    row = answer["parameter"]
    assert row["status"] == "draft"
    assert row["valid_from"] is None
    assert row["act"]["act_number"] == "TEST-9/9999"
    assert row["approved_by_user_id"] is None

    # The same write again changes nothing and says so.
    again = post(operator, PARAMETERS, draft())
    assert again.status_code == 200
    assert body(again)["outcome"] == "unchanged"

    rows = log_rows()
    assert [r.path_code for r in rows] == ["P-4", "P-4"]
    assert all(r.actor_user_id == staff["operator"] for r in rows)
    assert rows[0].actor == "console:operator"
    assert rows[0].payload is not None and rows[0].payload["operation"] == "draft"
    assert rows[0].payload["outcome"] == "created"
    assert rows[1].payload is not None and rows[1].payload["outcome"] == "unchanged"

    # The row is where every tenant will read it from. (Through the reference
    # connection here, as the loader tests do: under the harness the reference
    # transaction has not committed, so the request's own connection cannot see
    # it yet -- in production it can, the moment the door closes.)
    stored = FiscalParameter.objects.using(REFDATA_ALIAS).get(parameter_key="test.console.alpha")
    assert stored.status == "draft"
    assert stored.source.act_number == "TEST-9/9999"


def test_a_draft_without_a_margin_cannot_be_activated(operator: Client) -> None:
    row = body(post(operator, PARAMETERS, draft()))["parameter"]
    response = post(operator, f"{PARAMETERS}{row['id']}/activate")
    assert response.status_code == 409
    assert body(response)["code"] == "fiscal.margin_missing"


def test_a_draft_with_a_margin_is_activated_once_by_the_named_approver(
    operator: Client, staff: dict[str, uuid.UUID]
) -> None:
    created = post(
        operator,
        PARAMETERS,
        draft(
            valid_from="2000-01-01",
            margin_basis="act",
            margin_reference="art. 1 — test",
            observed_in=None,
        ),
    )
    assert created.status_code == 201, created.content
    row = body(created)["parameter"]
    assert row["valid_from"] == "2000-01-01"
    assert row["margin_act"]["act_number"] == "TEST-9/9999"

    activated = post(operator, f"{PARAMETERS}{row['id']}/activate")
    assert activated.status_code == 200, activated.content
    answer = body(activated)
    assert answer["outcome"] == "activated"
    assert answer["parameter"]["status"] == "active"
    assert answer["parameter"]["approved_by_user_id"] == str(staff["operator"])
    assert answer["parameter"]["approved_at"] is not None

    # Idempotent by state: a second click is not a second approval.
    again = post(operator, f"{PARAMETERS}{row['id']}/activate")
    assert again.status_code == 200
    assert body(again)["outcome"] == "already_active"

    # And an active value is not edited: the same date with another value is refused.
    changed = post(
        operator,
        PARAMETERS,
        draft(
            value=8,
            valid_from="2000-01-01",
            margin_basis="act",
            margin_reference="art. 1 — test",
            observed_in=None,
        ),
    )
    assert changed.status_code == 409
    assert body(changed)["code"] == "fiscal.active_not_edited"

    # Three rows, not four: the refused write left none. `privileged_run` writes
    # the log row last, in the same transaction, so a run that fails leaves
    # neither its writes nor a row claiming it happened -- the refusal is the
    # 409 above, and the audit trail holds only what took effect.
    outcomes = [r.payload["operation"] for r in log_rows() if r.payload]
    assert outcomes == ["draft", "activate", "activate"]


def test_a_write_naming_an_unknown_field_is_refused(operator: Client) -> None:
    """`status: active` in the body must not be dropped silently -- the client
    would believe it activated something."""
    response = post(operator, PARAMETERS, draft(status="active"))
    assert response.status_code == 400
    assert body(response)["code"] == "api.invalid"


def test_a_margin_needs_what_establishes_it(operator: Client) -> None:
    response = post(operator, PARAMETERS, draft(valid_from="2000-01-01", observed_in=None))
    assert response.status_code == 400
    assert body(response)["code"] == "fiscal.parameter_invalid"
    assert "OD-92" in body(response)["message"]


def test_an_unknown_parameter_is_not_found(operator: Client) -> None:
    response = post(operator, f"{PARAMETERS}{uuid.uuid4()}/activate")
    assert response.status_code == 404
    assert body(response)["code"] == "fiscal.parameter_not_found"
