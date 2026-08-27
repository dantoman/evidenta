"""Fixtures for the integration suite, borrowed rather than duplicated.

`seed` and `world` live in the isolation suite because that is where they were
first needed. Importing them keeps one definition of "a tenant, a user, a
membership": a second copy would drift, and the copy that drifts is the one that
stops proving what its name says.
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

from evidenta.platform.identity.models import User
from evidenta.platform.identity.services.authentication import (
    confirm_totp,
    enrol_totp,
    generate_secret_key,
)
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.isolation import conftest as isolation

# Re-exported by assignment rather than by `from ... import world`, and the
# difference is not style: an imported name is shadowed by the fixture parameter
# of the same name one function below, which reads as a redefinition -- ruff says
# `F811`, and it is right that the two cannot be told apart at a glance. Bound
# through the module, the parameter shadows nothing.
seed = isolation.seed
world = isolation.world

PASSWORD = "o-parola-suficient-de-lunga"
HOST_A = "alpha.evidenta.localhost"


@pytest.fixture(autouse=True)
def mfa_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MFA_SECRET_KEY", generate_secret_key())


@pytest.fixture
def signed_in(world: dict[str, uuid.UUID]) -> Iterator[dict[str, Any]]:
    """A logged-in HTTP client for tenant A, with the cookie the browser gets.

    Through the real login, second factor included: a client whose session was
    inserted by hand would prove the endpoints work for a session shape the
    product does not issue.
    """
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

    yield {"client": client, "world": world, "context": context}


@pytest.fixture
def post(signed_in: dict[str, Any]) -> Callable[..., Any]:
    """POST as the signed-in user, with the host header every request needs."""

    def call(path: str, body: dict[str, Any], **headers: str) -> Any:
        return signed_in["client"].post(
            path,
            data=json.dumps(body),
            content_type="application/json",
            headers={"host": HOST_A, **headers},
        )

    return call


@pytest.fixture
def get(signed_in: dict[str, Any]) -> Callable[..., Any]:
    def call(path: str) -> Any:
        return signed_in["client"].get(path, headers={"host": HOST_A})

    return call
