"""Authentication -- ADR-021: MFA is mandatory for everyone.

Two properties this module is built around.

**Authentication cannot complete without a second factor.** Not "should not":
there is no code path that returns a session from a password alone. A policy
enforced by a flag someone can flip is a policy that gets flipped on a Friday.

**A mandatory second factor without recovery is worse than an optional one.** It
produces lost accounts, lost accounts produce manual resets in production, and a
support desk that can reset MFA is an optional MFA with extra steps. So backup
codes are issued at enrolment, and recovery goes through a second administrator
of the tenant -- never through us.
"""

from __future__ import annotations

import base64
import os
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pyotp
from cryptography.fernet import Fernet, InvalidToken
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction

from evidenta.platform.identity.models import (
    MfaBackupCode,
    MfaMethod,
    MfaMethodType,
    User,
    UserSession,
)

#: How long an issued session lives before it must be renewed.
SESSION_LIFETIME = timedelta(hours=12)

#: How many recovery codes are issued, and how long each is.
BACKUP_CODE_COUNT = 10
BACKUP_CODE_BYTES = 10


class AuthenticationError(RuntimeError):
    """Authentication failed. The reason is deliberately not in the message."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class MfaRequiredError(AuthenticationError):
    """The password was correct and the user has not enrolled a second factor."""


class SecretKeyMissingError(RuntimeError):
    """No key is configured to encrypt MFA secrets with."""


def _cipher() -> Fernet:
    """The key comes from the environment and never from the database.

    A TOTP secret stored next to the data it protects means a database dump is a
    list of working second factors. Refusing to start without a key is the
    fail-closed position: the alternative is encrypting with something derived,
    guessable, and indistinguishable from real encryption at a glance.
    """
    key = os.environ.get("MFA_SECRET_KEY")
    if not key:
        raise SecretKeyMissingError(
            "MFA_SECRET_KEY is not set. MFA secrets are encrypted with a key held "
            "outside the database; without it, enrolment would store secrets that "
            "look protected and are not."
        )
    return Fernet(key.encode())


def generate_secret_key() -> str:
    """A key suitable for MFA_SECRET_KEY. For provisioning, not for runtime."""
    return Fernet.generate_key().decode()


@dataclass(frozen=True)
class Enrolment:
    """What the user needs to finish enrolling. Shown once."""

    method_id: uuid.UUID
    provisioning_uri: str
    backup_codes: tuple[str, ...]


def enrol_totp(user_id: uuid.UUID, label: str, issuer: str = "Evidenta") -> Enrolment:
    """Start TOTP enrolment and issue recovery codes.

    The codes are returned in clear exactly once, here. They are stored hashed,
    so nobody -- including us -- can read them back.
    """
    cipher = _cipher()
    secret = pyotp.random_base32()
    user = User.objects.get(pk=user_id)

    with transaction.atomic():
        method = MfaMethod.objects.create(
            user_id=user_id,
            method_type=MfaMethodType.TOTP,
            secret_encrypted=cipher.encrypt(secret.encode()),
            label=label,
        )
        codes = _issue_backup_codes(user_id)

    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=issuer)
    return Enrolment(method_id=method.id, provisioning_uri=uri, backup_codes=codes)


def confirm_totp(method_id: uuid.UUID, code: str) -> None:
    """Finish enrolment by proving the device works.

    Unconfirmed methods do not authenticate. Without this step a user could be
    locked out by an enrolment they never completed -- the QR code scanned into
    nothing.
    """
    method = MfaMethod.objects.get(pk=method_id)
    if not _totp_matches(method, code):
        raise AuthenticationError("mfa.invalid_code")

    now = datetime.now(UTC)
    method.confirmed_at = now
    method.last_used_at = now
    method.save(update_fields=["confirmed_at", "last_used_at"])

    User.objects.filter(pk=method.user_id).update(mfa_enabled=True, updated_at=now)


def authenticate(
    email: str,
    password: str,
    *,
    totp_code: str | None = None,
    backup_code: str | None = None,
    tenant_id: uuid.UUID | None = None,
    actor_firm_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> UserSession:
    """Verify password and second factor, then issue a session.

    There is no argument that skips the second factor, and no branch that returns
    a session without one.
    """
    user = User.objects.filter(email=email, is_active=True).first()

    # The same failure for "no such user" and "wrong password". Distinguishing
    # them turns the login form into a list of who has an account.
    if user is None or not user.password_hash:
        raise AuthenticationError("auth.invalid_credentials")
    if not check_password(password, user.password_hash):
        raise AuthenticationError("auth.invalid_credentials")

    methods = list(MfaMethod.objects.filter(user_id=user.id, confirmed_at__isnull=False))
    if not methods:
        # Not a failure of the credentials: the user must enrol before they can
        # reach any data. Raised as its own type so the caller can route to
        # enrolment rather than showing "wrong password".
        raise MfaRequiredError("auth.mfa_enrolment_required")

    if totp_code:
        if not any(_totp_matches(method, totp_code) for method in methods):
            raise AuthenticationError("auth.invalid_mfa_code")
    elif backup_code:
        _consume_backup_code(user.id, backup_code)
    else:
        raise AuthenticationError("auth.mfa_code_required")

    now = datetime.now(UTC)
    User.objects.filter(pk=user.id).update(last_login_at=now, updated_at=now)
    return UserSession.objects.create(
        user_id=user.id,
        tenant_id=tenant_id,
        actor_firm_id=actor_firm_id,
        expires_at=now + SESSION_LIFETIME,
        last_seen_at=now,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def _totp_matches(method: MfaMethod, code: str) -> bool:
    if method.method_type != MfaMethodType.TOTP:
        return False
    try:
        secret = _cipher().decrypt(bytes(method.secret_encrypted)).decode()
    except InvalidToken:
        # The stored secret cannot be read with the current key. Treating this as
        # "code does not match" would silently lock every user out after a key
        # rotation, with no signal that the key is the problem.
        raise AuthenticationError("mfa.secret_unreadable") from None
    # One step of tolerance: clocks drift, and refusing a code that was valid two
    # seconds ago produces support tickets, not security.
    return bool(pyotp.TOTP(secret).verify(code, valid_window=1))


def _issue_backup_codes(user_id: uuid.UUID) -> tuple[str, ...]:
    MfaBackupCode.objects.filter(user_id=user_id, used_at__isnull=True).delete()
    codes = tuple(
        base64.b32encode(secrets.token_bytes(BACKUP_CODE_BYTES)).decode().rstrip("=")
        for _ in range(BACKUP_CODE_COUNT)
    )
    MfaBackupCode.objects.bulk_create(
        [MfaBackupCode(user_id=user_id, code_hash=make_password(code)) for code in codes]
    )
    return codes


def _consume_backup_code(user_id: uuid.UUID, code: str) -> None:
    """Spend one recovery code, or refuse.

    Codes are checked one by one because they are hashed with a salt each -- there
    is no lookup by value, which is the same property that makes a dump useless.
    """
    now = datetime.now(UTC)
    with transaction.atomic():
        for candidate in MfaBackupCode.objects.select_for_update().filter(
            user_id=user_id, used_at__isnull=True
        ):
            if check_password(code, candidate.code_hash):
                candidate.used_at = now
                candidate.save(update_fields=["used_at"])
                return
    raise AuthenticationError("auth.invalid_backup_code")


def regenerate_backup_codes(user_id: uuid.UUID) -> tuple[str, ...]:
    """Issue a fresh set, invalidating the unused ones. Shown once."""
    with transaction.atomic():
        return _issue_backup_codes(user_id)
