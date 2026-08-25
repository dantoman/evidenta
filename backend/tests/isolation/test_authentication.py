"""Authentication and MFA -- ADR-021.

The claim under test is narrow and absolute: there is no path from a password to
a session. Everything else here supports it or covers the recovery route that
makes a mandatory second factor survivable.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta

import pyotp
import pytest
from django.contrib.auth.hashers import make_password

from evidenta.platform.identity.models import (
    MfaBackupCode,
    MfaMethod,
    User,
    UserSession,
)
from evidenta.platform.identity.services.authentication import (
    AuthenticationError,
    MfaRequiredError,
    SecretKeyMissingError,
    authenticate,
    confirm_totp,
    enrol_totp,
    generate_secret_key,
    regenerate_backup_codes,
)
from evidenta.platform.identity.services.sessions import (
    invalidate_sessions_for_engagement,
    is_live,
)
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

PASSWORD = "o-parola-suficient-de-lunga"


@pytest.fixture(autouse=True)
def mfa_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MFA_SECRET_KEY", generate_secret_key())


@pytest.fixture
def account(world: dict[str, uuid.UUID]) -> Iterator[TenantContext]:
    """A user with a password, inside their own context."""
    context = TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="auth")
    with tenant_context(context):
        User.objects.filter(pk=world["user_a"]).update(password_hash=make_password(PASSWORD))
        yield context


def enrolled(context: TenantContext) -> str:
    """Enrol and confirm TOTP; return the shared secret for generating codes."""
    enrolment = enrol_totp(context.user_id, label="phone")
    secret = pyotp.parse_uri(enrolment.provisioning_uri).secret  # type: ignore[union-attr]
    confirm_totp(enrolment.method_id, pyotp.TOTP(secret).now())
    return str(secret)


def test_a_password_alone_never_produces_a_session(
    account: TenantContext, world: dict[str, uuid.UUID]
) -> None:
    """The whole point of ADR-021, stated as a test.

    Before enrolment there is no second factor to present, and the correct
    password still does not authenticate -- it routes to enrolment instead.
    """
    with tenant_context(account), pytest.raises(MfaRequiredError):
        authenticate("a@example.md", PASSWORD)
    assert UserSession.objects.count() == 0


def test_password_and_totp_produce_a_session(account: TenantContext) -> None:
    with tenant_context(account):
        secret = enrolled(account)
        session = authenticate("a@example.md", PASSWORD, totp_code=pyotp.TOTP(secret).now())
        assert is_live(session)


def test_an_enrolled_user_still_needs_a_code(account: TenantContext) -> None:
    with tenant_context(account):
        enrolled(account)
        with pytest.raises(AuthenticationError) as caught:
            authenticate("a@example.md", PASSWORD)
    assert caught.value.code == "auth.mfa_code_required"


def test_a_wrong_code_is_refused(account: TenantContext) -> None:
    with tenant_context(account):
        enrolled(account)
        with pytest.raises(AuthenticationError) as caught:
            authenticate("a@example.md", PASSWORD, totp_code="000000")
    assert caught.value.code == "auth.invalid_mfa_code"


def test_unknown_user_and_wrong_password_fail_identically(
    account: TenantContext,
) -> None:
    """Distinguishing them turns the login form into a list of who has an account."""
    with tenant_context(account):
        codes = []
        for email, password in (
            ("a@example.md", "gresit"),
            ("nimeni@example.md", PASSWORD),
        ):
            with pytest.raises(AuthenticationError) as caught:
                authenticate(email, password)
            codes.append(caught.value.code)
    assert codes[0] == codes[1] == "auth.invalid_credentials"


def test_an_unconfirmed_enrolment_does_not_authenticate(
    account: TenantContext,
) -> None:
    """A QR code scanned into nothing must not lock the user out or let them in."""
    with tenant_context(account):
        enrolment = enrol_totp(account.user_id, label="phone")
        secret = pyotp.parse_uri(enrolment.provisioning_uri).secret  # type: ignore[union-attr]
        with pytest.raises(MfaRequiredError):
            authenticate("a@example.md", PASSWORD, totp_code=pyotp.TOTP(secret).now())


def test_a_backup_code_works_once(account: TenantContext) -> None:
    """Recovery is what makes a mandatory second factor survivable.

    Without it, a lost phone becomes a manual reset in production -- which is the
    vector the second factor was meant to close.
    """
    with tenant_context(account):
        enrolment = enrol_totp(account.user_id, label="phone")
        secret = pyotp.parse_uri(enrolment.provisioning_uri).secret  # type: ignore[union-attr]
        confirm_totp(enrolment.method_id, pyotp.TOTP(secret).now())

        code = enrolment.backup_codes[0]
        session = authenticate("a@example.md", PASSWORD, backup_code=code)
        assert is_live(session)

        with pytest.raises(AuthenticationError) as caught:
            authenticate("a@example.md", PASSWORD, backup_code=code)
    assert caught.value.code == "auth.invalid_backup_code"


def test_backup_codes_are_stored_hashed(account: TenantContext) -> None:
    """A database dump must not be a list of ways past the second factor."""
    with tenant_context(account):
        enrolment = enrol_totp(account.user_id, label="phone")
        stored = list(MfaBackupCode.objects.values_list("code_hash", flat=True))
    assert all(code not in stored for code in enrolment.backup_codes)
    assert all(h.startswith("pbkdf2_") for h in stored)


def test_regenerating_codes_invalidates_the_old_ones(account: TenantContext) -> None:
    with tenant_context(account):
        first = enrol_totp(account.user_id, label="phone")
        confirm_totp(
            first.method_id,
            pyotp.TOTP(pyotp.parse_uri(first.provisioning_uri).secret).now(),  # type: ignore[union-attr]
        )
        regenerate_backup_codes(account.user_id)

        with pytest.raises(AuthenticationError):
            authenticate("a@example.md", PASSWORD, backup_code=first.backup_codes[0])


def test_enrolment_refuses_without_a_key(
    account: TenantContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refusing to start beats encrypting with something guessable.

    A secret stored next to the data it protects only looks protected.
    """
    monkeypatch.delenv("MFA_SECRET_KEY", raising=False)
    with tenant_context(account), pytest.raises(SecretKeyMissingError):
        enrol_totp(account.user_id, label="phone")


def test_the_secret_is_not_stored_in_clear(account: TenantContext) -> None:
    with tenant_context(account):
        enrolment = enrol_totp(account.user_id, label="phone")
        secret = pyotp.parse_uri(enrolment.provisioning_uri).secret  # type: ignore[union-attr]
        stored = bytes(MfaMethod.objects.get(pk=enrolment.method_id).secret_encrypted)
    assert str(secret).encode() not in stored


def test_sessions_are_private_to_their_user(
    account: TenantContext, world: dict[str, uuid.UUID]
) -> None:
    with tenant_context(account):
        secret = enrolled(account)
        authenticate("a@example.md", PASSWORD, totp_code=pyotp.TOTP(secret).now())

    other = TenantContext(tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="auth")
    with tenant_context(other):
        assert UserSession.objects.count() == 0


def test_revoking_an_engagement_ends_the_firms_sessions(
    firm_world: dict[str, uuid.UUID],
    engage: Callable[..., uuid.UUID],
    seed: Callable[..., None],
) -> None:
    """IZ-20, the half of revocation that RLS does not cover.

    RLS already refuses the firm's queries. This is what stops their interface
    from failing one request at a time instead of ending cleanly.
    """
    engage(firm_world["firm"], firm_world["tenant_b"], firm_world["user_f"])
    now = datetime.now(UTC)
    seed(
        "INSERT INTO user_session (id, user_id, tenant_id, actor_firm_id,"
        " created_at, expires_at) VALUES (%s, %s, %s, %s, %s, %s)",
        [
            uuid.uuid4(),
            firm_world["user_f"],
            firm_world["tenant_b"],
            firm_world["firm"],
            now,
            now + timedelta(hours=12),
        ],
    )

    acting = TenantContext(
        tenant_id=firm_world["tenant_b"],
        user_id=firm_world["user_f"],
        request_id="auth",
        actor_firm_id=firm_world["firm"],
    )
    with tenant_context(acting):
        ended = invalidate_sessions_for_engagement(
            firm_world["tenant_b"], firm_world["firm"], reason="test"
        )
        assert ended == 1
        assert UserSession.objects.filter(revoked_at__isnull=True).count() == 0
