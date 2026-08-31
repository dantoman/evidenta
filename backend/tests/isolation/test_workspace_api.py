"""The workspace over HTTP -- `/api/v1/workspace`.

The endpoint exists to answer three questions the product answered nowhere: who
holds this account, what may I do here, and who else was given access. So the
test asks them the way a screen does -- through the real chain, host to tenant,
cookie to session, middleware to context -- and then asks the only question that
matters more: **can any of it be another tenant's?**

What it checks, in order of what it would cost to get wrong:

* the roles that come back are the workspace's own, never the neighbour's
* the account holder is the tenant of the host, not of the session's other
  memberships
* a company the caller was granted appears with *how* it was granted
* a permission held by the role is reported; one nobody granted is not
* no session reaches nothing
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
from django.test import Client

from evidenta.platform.identity.models import User
from evidenta.platform.identity.services.authentication import (
    confirm_totp,
    enrol_totp,
    generate_secret_key,
)
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.isolation.conftest import role_id

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

PASSWORD = "o-parola-suficient-de-lunga"
HOST_A = "alpha.evidenta.localhost"
PATH = "/api/v1/workspace"


@pytest.fixture(autouse=True)
def mfa_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MFA_SECRET_KEY", generate_secret_key())


@pytest.fixture
def signed_in(world: dict[str, uuid.UUID]) -> Iterator[Client]:
    """A client holding a real session cookie for tenant A."""
    context = TenantContext(
        tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="setup"
    )
    with tenant_context(context):
        User.objects.filter(pk=world["user_a"]).update(password_hash=make_password(PASSWORD))
        enrolment = enrol_totp(world["user_a"], label="phone")
        secret = str(pyotp.parse_uri(enrolment.provisioning_uri).secret)  # type: ignore[union-attr]
        confirm_totp(enrolment.method_id, pyotp.TOTP(secret).now())

    client = Client()
    response = client.post(
        "/api/v1/auth/login",
        data=json.dumps(
            {
                "email": "a@example.md",
                "password": PASSWORD,
                "totp_code": pyotp.TOTP(secret).now(),
            }
        ),
        content_type="application/json",
        headers={"host": HOST_A},
    )
    assert response.status_code == 200, response.content
    yield client


def read(client: Client) -> Any:
    response = client.get(PATH, headers={"host": HOST_A})
    assert response.status_code == 200, response.content
    return json.loads(response.content)


def test_workspace_names_the_account_holder(signed_in: Client) -> None:
    body = read(signed_in)

    # The holder of the contract, by name -- the thing the subdomain alone never
    # said. `legal_name`, because that is what a person recognises.
    assert body["tenant"]["subdomain"] == "alpha"
    assert body["tenant"]["legal_name"] == "Alpha SRL"
    assert body["tenant"]["status"] == "active"
    assert body["me"]["email"] == "a@example.md"
    assert body["me"]["membership_status"] == "active"
    assert body["me"]["role"]["key"] == "owner"


def test_roles_are_the_workspace_own_never_the_neighbour(
    signed_in: Client, world: dict[str, uuid.UUID], seed: Callable[..., None]
) -> None:
    """A role keyed distinctly in tenant B must not appear in tenant A's answer.

    The policy on `role` is the tenant template, so this passing is a statement
    about the policy rather than about the query -- which is the point of asking
    it here instead of in a service test.
    """
    now = datetime.now(UTC)
    seed(
        "INSERT INTO role (id, tenant_id, key, name, level, is_system,"
        " created_at, updated_at)"
        " VALUES (%s, %s, 'beta_only', 'Numai la beta', 'tenant', false, %s, %s)",
        [uuid.uuid4(), world["tenant_b"], now, now],
    )

    keys = {role["key"] for role in read(signed_in)["roles"]}
    assert "owner" in keys
    assert "beta_only" not in keys


def test_permissions_are_the_ones_the_role_holds(
    signed_in: Client, world: dict[str, uuid.UUID], seed: Callable[..., None]
) -> None:
    seed(
        "INSERT INTO role_permission (id, tenant_id, role_id, permission_key, scope)"
        " VALUES (%s, %s, %s, 'tenant.manage_roles', 'tenant')",
        [uuid.uuid4(), world["tenant_a"], role_id(world["tenant_a"], "owner")],
    )

    body = read(signed_in)
    assert body["me"]["role"]["permissions"] == ["tenant.manage_roles"]
    # And nothing invented: a key nobody granted is absent rather than implied by
    # the role being a system one.
    assert "engagement.revoke" not in body["me"]["role"]["permissions"]


def test_billing_identity_is_reported_and_no_company_is_singled_out(
    signed_in: Client,
    world: dict[str, uuid.UUID],
    seed: Callable[..., None],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> None:
    """The workspace's own identity is **billing**, and it points at nothing.

    ADR-085 undid the shape ADR-075 had given this: a workspace is held by a
    person, and in the case that turns out to be the common one -- an
    entrepreneur with four firms -- no company of the workspace is "the
    holder's". The endpoint therefore reports the identity and derives nothing
    from it.

    The fixture makes a company carry **exactly the workspace's IDNO**, which is
    what an implementation that still matched would seize on.
    """
    shared_idno = "1002600000401"
    seed(
        "UPDATE tenant SET idno = %s, legal_form = 'SRL' WHERE id = %s",
        [shared_idno, world["tenant_a"]],
    )
    company_id = company_of(world["tenant_a"], shared_idno, "Alpha SRL")
    grant_company(world["tenant_a"], company_id, world["user_a"], world["user_a"])

    body = read(signed_in)
    assert body["tenant"]["idno"] == shared_idno
    assert body["tenant"]["legal_form"] == "SRL"
    assert "own_company_id" not in body["tenant"]


def test_company_access_says_how_it_was_granted(
    signed_in: Client,
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> None:
    company_id = company_of(world["tenant_a"], "1002600000301", "Alpha Workspace")
    grant_company(world["tenant_a"], company_id, world["user_a"], world["user_a"])

    companies = read(signed_in)["me"]["companies"]
    assert [row["company_id"] for row in companies] == [str(company_id)]
    # Membership, not engagement: the difference is what a person needs to know
    # before writing in somebody's books.
    assert companies[0]["granted_via"] == "membership"


def test_no_session_reaches_nothing() -> None:
    response = Client().get(PATH, headers={"host": HOST_A})
    assert response.status_code in (401, 403), response.content


def test_a_person_corrects_their_own_name(signed_in: Client) -> None:
    """The name changes, and the workspace answers with it.

    Two assertions rather than one: the endpoint could return the new name
    without storing it, and the screen reads the stored one.
    """
    response = signed_in.patch(
        "/api/v1/auth/profile",
        data=json.dumps({"full_name": "  Ana Rusu  "}),
        content_type="application/json",
        headers={"host": HOST_A},
    )
    assert response.status_code == 200, response.content
    assert json.loads(response.content)["full_name"] == "Ana Rusu"
    assert read(signed_in)["me"]["full_name"] == "Ana Rusu"


def test_a_blank_name_is_refused(signed_in: Client) -> None:
    """An empty name would leave the e-mail address standing in for a person."""
    response = signed_in.patch(
        "/api/v1/auth/profile",
        data=json.dumps({"full_name": "   "}),
        content_type="application/json",
        headers={"host": HOST_A},
    )
    assert response.status_code == 422, response.content
    assert json.loads(response.content)["code"] == "identity.profile_malformed"


def test_the_profile_edits_the_signed_in_user_and_nobody_else(
    signed_in: Client, world: dict[str, uuid.UUID]
) -> None:
    """There is no identifier to send, and the policy is why.

    `user` is policed self-row, so even a request that named another id would
    update nothing. The endpoint does not accept one, so the two agree: the shape
    cannot express the question the database would refuse.
    """
    signed_in.patch(
        "/api/v1/auth/profile",
        data=json.dumps({"full_name": "Ana Rusu", "user_id": str(world["user_b"])}),
        content_type="application/json",
        headers={"host": HOST_A},
    )

    with tenant_context(
        TenantContext(tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="check")
    ):
        assert User.objects.get(pk=world["user_b"]).full_name == "b@example.md"
