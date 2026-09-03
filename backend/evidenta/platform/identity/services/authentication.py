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

from evidenta.platform.identity import privileged
from evidenta.platform.identity.models import (
    MfaBackupCode,
    MfaMethod,
    MfaMethodType,
    User,
    UserSession,
)
from evidenta.platform.identity.services import sessions
from evidenta.platform.identity.services.staff import staff_role_in_context
from evidenta.platform.rls.context import Context, PlatformContext, TenantContext, tenant_context
from evidenta.platform.tenancy.services.access import tenant_visible_in_context

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
    if not _totp_matches(method.method_type, bytes(method.secret_encrypted), code):
        raise AuthenticationError("mfa.invalid_code")

    now = datetime.now(UTC)
    method.confirmed_at = now
    method.last_used_at = now
    method.save(update_fields=["confirmed_at", "last_used_at"])

    User.objects.filter(pk=method.user_id).update(mfa_enabled=True, updated_at=now)


@dataclass(frozen=True)
class IssuedSession:
    """The result of a successful authentication.

    ``token`` is the only time the session secret exists outside the browser --
    it is stored as a fingerprint, so it cannot be read back from anywhere.
    """

    session_id: uuid.UUID
    token: str
    expires_at: datetime


def authenticate(
    email: str,
    password: str,
    tenant_id: uuid.UUID | None,
    *,
    request_id: str,
    totp_code: str | None = None,
    backup_code: str | None = None,
    actor_firm_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> IssuedSession:
    """Verify password and second factor, then issue a session.

    There is no argument that skips the second factor, and no branch that returns
    a session without one.

    ``tenant_id`` comes from the subdomain the request arrived on (C8) and is
    never chosen by the caller. **``None`` means the console** (ADR-076 §4.2):
    the request arrived on the ``admin.`` host, where there is no tenant to
    bind, and the session issued is bound to *no* tenant -- which is exactly why
    a tenant host refuses it. It is not a shortcut around the check below: a
    console session is issued only to a live member of ``platform_staff``, the
    way a tenant session is issued only to somebody the tenant's policies admit.

    Everything up to the second factor runs on the privileged path, because it
    precedes the identity a policy would need. Everything after it runs inside a
    context, through ordinary policies -- including the write of the session row.
    """
    material = privileged.lookup_user(email)

    # The same failure for "no such user", "deactivated" and "wrong password".
    # Distinguishing them turns the login form into a list of who has an account.
    if material is None or not material.password_hash:
        raise AuthenticationError("auth.invalid_credentials")
    if not check_password(password, material.password_hash):
        raise AuthenticationError("auth.invalid_credentials")

    factors = privileged.mfa_methods(material.user_id)
    if not factors:
        # Not a failure of the credentials: the user must enrol before they can
        # reach any data. Raised as its own type so the caller can route to
        # enrolment rather than showing "wrong password".
        raise MfaRequiredError("auth.mfa_enrolment_required")

    if totp_code:
        if not any(
            _totp_matches(factor.method_type, factor.secret_encrypted, totp_code)
            for factor in factors
        ):
            raise AuthenticationError("auth.invalid_mfa_code")
    elif backup_code:
        _consume_backup_code(material.user_id, backup_code)
    else:
        raise AuthenticationError("auth.mfa_code_required")

    return _open_session(
        user_id=material.user_id,
        tenant_id=tenant_id,
        request_id=request_id,
        actor_firm_id=actor_firm_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def _open_session(
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID | None,
    request_id: str,
    actor_firm_id: uuid.UUID | None,
    ip_address: str | None,
    user_agent: str | None,
) -> IssuedSession:
    """Both factors are verified; from here the ordinary policies apply.

    The access check is the interesting line. It goes through `tenancy`'s public
    service rather than its models -- `D6` -- and that service asks the database
    rather than recomputing the rule, so the question here is the same one every
    later query will ask.

    Without it, a correct password and a correct second factor would produce a
    session for a tenant the user has nothing to do with. Every query would
    return nothing, which is safe and reads to the user as the product being
    broken.

    **The console is the same shape with a different question.** Under a
    `PlatformContext` the access check asks `platform_staff`, through its own
    self-row policy, whether this person is a live employee of the platform. A
    correct password and second factor from anybody else issue nothing -- and the
    refusal code says "no access to the console", not "wrong password", because
    the credentials were right and retrying them will never help.
    """
    now = datetime.now(UTC)
    token = sessions.new_token()
    expires_at = now + SESSION_LIFETIME
    context: Context
    if tenant_id is None:
        if actor_firm_id is not None:
            # A firm acts for a client's tenant; the console has no client.
            raise AuthenticationError("auth.no_access_to_console")
        context = PlatformContext(user_id=user_id, request_id=request_id)
    else:
        context = TenantContext(
            tenant_id=tenant_id,
            user_id=user_id,
            request_id=request_id,
            actor_firm_id=actor_firm_id,
        )

    support_grant_id: uuid.UUID | None = None
    with tenant_context(context):
        if tenant_id is None:
            if staff_role_in_context(user_id) is None:
                raise AuthenticationError("auth.no_access_to_console")
        elif not tenant_visible_in_context(tenant_id):
            # Not a member and not acting for a firm. The one remaining door is
            # a support grant the client approved (ADR-077 §6): the tenant is
            # visible only under the grant, so the check is repeated inside a
            # context that carries it -- opened read-write on purpose, because
            # the session row about to be written is the exception ADR-094 names.
            support_grant_id = privileged.support_grant_for(user_id, tenant_id)
            if support_grant_id is None:
                raise AuthenticationError("auth.no_access_to_tenant")
            on_grant = TenantContext(
                tenant_id=tenant_id,
                user_id=user_id,
                request_id=request_id,
                support_grant_id=support_grant_id,
            )
            with tenant_context(on_grant, read_only=False):
                if not tenant_visible_in_context(tenant_id):
                    raise AuthenticationError("auth.no_access_to_tenant")

        User.objects.filter(pk=user_id).update(last_login_at=now, updated_at=now)
        session = UserSession.objects.create(
            user_id=user_id,
            token_hash=sessions.fingerprint(token),
            tenant_id=tenant_id,
            actor_firm_id=actor_firm_id,
            support_grant_id=support_grant_id,
            expires_at=expires_at,
            last_seen_at=now,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    return IssuedSession(session_id=session.id, token=token, expires_at=expires_at)


def _totp_matches(method_type: str, secret_encrypted: bytes, code: str) -> bool:
    """Takes the two fields rather than a model instance.

    During authentication the factor arrives from the privileged path as a plain
    row; afterwards, at enrolment, it is an ORM object. One function either way --
    two would be two places for the tolerance window to be set differently.
    """
    if method_type != MfaMethodType.TOTP:
        return False
    try:
        secret = _cipher().decrypt(secret_encrypted).decode()
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

    The spend itself is one statement in the database (``used_at IS NULL`` in the
    same UPDATE that sets it), so two requests presenting the same code have one
    winner. Doing it here, read-then-write, would have had two.
    """
    for candidate in privileged.backup_codes(user_id):
        if check_password(code, candidate.code_hash) and privileged.spend_backup_code(
            candidate.code_id
        ):
            return
    raise AuthenticationError("auth.invalid_backup_code")


def regenerate_backup_codes(user_id: uuid.UUID) -> tuple[str, ...]:
    """Issue a fresh set, invalidating the unused ones. Shown once."""
    with transaction.atomic():
        return _issue_backup_codes(user_id)
