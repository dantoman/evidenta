"""The chart of accounts over HTTP -- `/api/v1/accounting/coa/`.

Nothing here builds a ``TenantContext``. Every request goes through the real
chain: host to tenant, cookie to session, middleware to context. That is the
point of testing the API separately from the services -- the services were proved
inside a context somebody handed them, and this proves the context arrives.

What it checks, in order of what it would cost to get wrong:

* a request with no session reaches nothing
* an account of another tenant answers 404, never 403 (IZ-04)
* a parent in the body cannot move the write into another company
* the refusals of Spec B section 2.4 survive the trip through HTTP with their
  codes intact (C10)
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import pyotp
import pytest
from django.contrib.auth.hashers import make_password
from django.test import Client

from evidenta.accounting.coa.services.instantiation import instantiate_chart
from evidenta.platform.identity.models import User
from evidenta.platform.identity.services.authentication import (
    confirm_totp,
    enrol_totp,
    generate_secret_key,
)
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.isolation.test_coa import seed_account, seed_template

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

PASSWORD = "o-parola-suficient-de-lunga"
HOST_A = "alpha.evidenta.localhost"
BASE = "/api/v1/accounting/coa"


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


@pytest.fixture
def company(
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> uuid.UUID:
    company_id = company_of(world["tenant_a"], "1002600000201", "Alpha API")
    grant_company(world["tenant_a"], company_id, world["user_a"], world["user_a"])
    return company_id


@pytest.fixture
def template(seed: Callable[..., None]) -> uuid.UUID:
    template_id = seed_template(seed, code="API")
    seed_account(seed, template_id, account_code="T1")
    seed_account(
        seed,
        template_id,
        account_code="T11",
        parent_code="T1",
        name_ro="Subcont de fixture",
        allows_subaccounts=False,
    )
    return template_id


def get(client: Client, path: str) -> Any:
    return client.get(path, headers={"host": HOST_A})


def send(client: Client, method: str, path: str, body: dict[str, Any]) -> Any:
    return getattr(client, method)(
        path,
        data=json.dumps(body, default=str),
        content_type="application/json",
        headers={"host": HOST_A},
    )


# --- the chain itself -------------------------------------------------------


def test_a_request_with_no_session_reaches_nothing(company: uuid.UUID) -> None:
    response = Client().get(f"{BASE}/templates", headers={"host": HOST_A})
    assert response.status_code in (401, 403, 404)
    assert "code" in response.json()


def test_only_published_versions_are_offered(
    signed_in: Client, seed: Callable[..., None], template: uuid.UUID
) -> None:
    """A draft is a version being prepared. The service refuses to instantiate
    one, so listing it would put a choice on screen the server will not honour.
    """
    seed_template(seed, code="HIDDEN", status="draft")

    response = get(signed_in, f"{BASE}/templates")
    assert response.status_code == 200
    codes = {row["code"] for row in response.json()}
    assert "API" in codes
    assert "HIDDEN" not in codes


# --- the chart --------------------------------------------------------------


def test_instantiating_and_reading_back_the_chart(
    signed_in: Client, company: uuid.UUID, template: uuid.UUID
) -> None:
    created = send(
        signed_in, "post", f"{BASE}/companies/{company}/chart", {"template_id": template}
    )
    assert created.status_code == 201, created.content
    assert created.json()["template_id"] == str(template)

    accounts = get(signed_in, f"{BASE}/companies/{company}/accounts")
    assert accounts.status_code == 200
    rows = {row["account_code"]: row for row in accounts.json()}
    assert set(rows) == {"T1", "T11"}
    assert rows["T11"]["parent_id"] == rows["T1"]["id"]
    assert rows["T1"]["origin"] == "system"


def test_a_second_instantiation_is_refused_with_its_code(
    signed_in: Client, company: uuid.UUID, template: uuid.UUID
) -> None:
    send(signed_in, "post", f"{BASE}/companies/{company}/chart", {"template_id": template})
    again = send(signed_in, "post", f"{BASE}/companies/{company}/chart", {"template_id": template})
    assert again.status_code == 409
    assert again.json()["code"] == "coa.chart_already_instantiated"


@pytest.fixture
def chart(signed_in: Client, company: uuid.UUID, template: uuid.UUID) -> dict[str, dict[str, Any]]:
    send(signed_in, "post", f"{BASE}/companies/{company}/chart", {"template_id": template})
    rows = get(signed_in, f"{BASE}/companies/{company}/accounts").json()
    return {row["account_code"]: row for row in rows}


# --- reading the chart on a date --------------------------------------------


def test_postable_accounts_answer_for_the_date_the_caller_names(
    signed_in: Client, company: uuid.UUID, chart: dict[str, dict[str, Any]]
) -> None:
    """The server never substitutes today. R18: recalculating a closed period has
    to see the chart as it was.
    """
    send(signed_in, "patch", f"{BASE}/accounts/{chart['T11']['id']}", {"valid_to": "2026-01-01"})

    before = get(signed_in, f"{BASE}/companies/{company}/accounts?on=2025-12-31").json()
    after = get(signed_in, f"{BASE}/companies/{company}/accounts?on=2026-01-01").json()

    assert {row["account_code"] for row in before} == {"T1", "T11"}
    assert {row["account_code"] for row in after} == {"T1"}


def test_a_malformed_date_is_a_stable_code_not_a_field_error(
    signed_in: Client, company: uuid.UUID, chart: dict[str, dict[str, Any]]
) -> None:
    response = get(signed_in, f"{BASE}/companies/{company}/accounts?on=luna-trecuta")
    assert response.status_code == 400
    assert response.json()["code"] == "coa.invalid_date"


# --- writing ----------------------------------------------------------------


def test_a_subaccount_is_created_and_inherits_its_parent(
    signed_in: Client, company: uuid.UUID, chart: dict[str, dict[str, Any]]
) -> None:
    response = send(
        signed_in,
        "post",
        f"{BASE}/companies/{company}/accounts",
        {
            "parent_id": chart["T1"]["id"],
            "account_code": "T1-API",
            "name_ro": "Subcont prin API",
            "valid_from": "2026-01-01",
        },
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["origin"] == "company"
    assert body["account_class"] == chart["T1"]["account_class"]
    assert body["normal_balance"] == chart["T1"]["normal_balance"]


def test_a_parent_in_the_body_cannot_move_the_write_into_another_company(
    signed_in: Client,
    world: dict[str, uuid.UUID],
    company: uuid.UUID,
    template: uuid.UUID,
    chart: dict[str, dict[str, Any]],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
    seed: Callable[..., None],
) -> None:
    """Both companies are the caller's, so RLS permits both -- which is exactly
    why the URL has to be the one that decides. Without the check in the view,
    the body would silently win over the path.
    """
    second = company_of(world["tenant_a"], "1002600000202", "Alpha API doi")
    grant_company(world["tenant_a"], second, world["user_a"], world["user_a"])
    other = seed_template(seed, code="API2")
    seed_account(seed, other, account_code="X1")

    send(signed_in, "post", f"{BASE}/companies/{second}/chart", {"template_id": other})
    foreign = get(signed_in, f"{BASE}/companies/{second}/accounts").json()[0]

    response = send(
        signed_in,
        "post",
        f"{BASE}/companies/{company}/accounts",
        {
            "parent_id": foreign["id"],
            "account_code": "SMUGGLED",
            "name_ro": "Nu trebuie sa existe",
            "valid_from": "2026-01-01",
        },
    )
    assert response.status_code == 404
    assert response.json()["code"] == "api.not_found"

    remaining = get(signed_in, f"{BASE}/companies/{second}/accounts").json()
    assert "SMUGGLED" not in {row["account_code"] for row in remaining}


def test_renaming_a_system_account_is_refused_over_http_too(
    signed_in: Client, chart: dict[str, dict[str, Any]]
) -> None:
    response = send(
        signed_in, "patch", f"{BASE}/accounts/{chart['T1']['id']}", {"name_ro": "Alt nume"}
    )
    assert response.status_code == 400
    assert response.json()["code"] == "coa.system_account_immutable"


def test_blocking_an_account_over_http(signed_in: Client, chart: dict[str, dict[str, Any]]) -> None:
    response = send(
        signed_in, "patch", f"{BASE}/accounts/{chart['T1']['id']}", {"is_blocked": True}
    )
    assert response.status_code == 200
    assert response.json()["is_blocked"] is True


def test_an_empty_patch_is_refused(signed_in: Client, chart: dict[str, dict[str, Any]]) -> None:
    """A request that changes nothing is a client bug, and answering 200 to it
    hides the bug behind a success.
    """
    response = send(signed_in, "patch", f"{BASE}/accounts/{chart['T1']['id']}", {})
    assert response.status_code == 400
    assert response.json()["code"] == "api.invalid"


# --- IZ-04 ------------------------------------------------------------------


def test_an_account_of_another_tenant_is_absent_not_forbidden(
    signed_in: Client,
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
    seed: Callable[..., None],
) -> None:
    """403 would say "this exists and is not yours". Over a range of identifiers
    that is an enumeration oracle; 404 says nothing at all.
    """
    foreign_company = company_of(world["tenant_b"], "1002600000203", "Beta API")
    grant_company(world["tenant_b"], foreign_company, world["user_b"], world["user_b"])
    foreign_template = seed_template(seed, code="BETA")
    seed_account(seed, foreign_template, account_code="B1")

    context = TenantContext(
        tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="setup"
    )
    with tenant_context(context):
        instantiate_chart(foreign_company, foreign_template)

    with tenant_context(context):
        from evidenta.accounting.coa.models import CompanyAccount

        foreign_id = CompanyAccount.objects.get(company_id=foreign_company).id

    response = get(signed_in, f"{BASE}/accounts/{foreign_id}")
    assert response.status_code == 404
    assert response.json()["code"] == "api.not_found"
