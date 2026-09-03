"""The queries that precede the tenant context -- Spec A section 3.2, step 2.

The request sequence in Spec A numbers two steps before the transaction opens:
resolve the subdomain, then authenticate the user. Step 1 already has its narrow
privileged path (``rls.resolve_tenant_by_subdomain``). This module is step 2.

Why it cannot be an ordinary queryset: ``app.current_user_id()`` is fail-closed.
With no context it raises rather than returning NULL, so every ``self_row``
policy -- ``user``, ``mfa_method``, ``mfa_backup_code``, ``user_session`` --
refuses before it can answer. And it is right to: "my own row" is precisely what
is not yet known during authentication.

**What is deliberately absent.** Issuing a session, recording the login and
revoking a session are not here. Once the password *and* the second factor have
been verified the identity is known, a context can be opened, and the ordinary
policies write those rows through the ORM. A privileged function for them would
be a hole opened where none was needed.

Each wrapper is a thin call. The judgement lives in the SQL -- liveness, the
``confirmed_at`` filter, the single-statement spend of a backup code -- so that a
caller cannot forget a condition the security of the thing depends on. See
infra/migrations/0028_auth_request_path.up.sql.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from django.db import connection

from evidenta.platform.rls.context import unguarded

#: Stated once. Every suspension of the query guard in this module is the same
#: suspension, for the same reason, and a second wording would read as a second
#: reason.
_REASON = "authentication: precedes any tenant context (spec-a 3.2, step 2)"


@dataclass(frozen=True, slots=True)
class AuthMaterial:
    """What is needed to check a password, and nothing else."""

    user_id: uuid.UUID
    password_hash: str | None
    mfa_enabled: bool


@dataclass(frozen=True, slots=True)
class EnrolledFactor:
    method_id: uuid.UUID
    method_type: str
    secret_encrypted: bytes


@dataclass(frozen=True, slots=True)
class StoredBackupCode:
    code_id: uuid.UUID
    code_hash: str


@dataclass(frozen=True, slots=True)
class ResolvedSession:
    """A live session. Expired and revoked ones do not reach here -- the SQL
    filters them, so there is no representation of a dead session to mishandle."""

    session_id: uuid.UUID
    user_id: uuid.UUID
    tenant_id: uuid.UUID | None
    actor_firm_id: uuid.UUID | None
    support_grant_id: uuid.UUID | None = None


@contextmanager
def _privileged_cursor() -> Iterator[Any]:
    with unguarded(_REASON), connection.cursor() as cursor:
        yield cursor


def lookup_user(email: str) -> AuthMaterial | None:
    """The account behind an e-mail, if it is active.

    Inactive accounts return None, the same as absent ones: the difference is
    real and must not reach the caller, or the login form becomes a directory of
    who has an account.
    """
    with _privileged_cursor() as cursor:
        cursor.execute(
            "SELECT user_id, password_hash, mfa_enabled FROM rls.auth_lookup_user(%s)",
            [email],
        )
        row = cursor.fetchone()
    if row is None:
        return None
    return AuthMaterial(user_id=row[0], password_hash=row[1], mfa_enabled=row[2])


def mfa_methods(user_id: uuid.UUID) -> tuple[EnrolledFactor, ...]:
    """Confirmed second factors only. An abandoned enrolment authenticates nothing."""
    with _privileged_cursor() as cursor:
        cursor.execute(
            "SELECT method_id, method_type, secret_encrypted FROM rls.auth_mfa_methods(%s)",
            [user_id],
        )
        rows = cursor.fetchall()
    return tuple(
        EnrolledFactor(method_id=row[0], method_type=row[1], secret_encrypted=bytes(row[2]))
        for row in rows
    )


def backup_codes(user_id: uuid.UUID) -> tuple[StoredBackupCode, ...]:
    """The unused recovery codes, as hashes. There is no lookup by value."""
    with _privileged_cursor() as cursor:
        cursor.execute("SELECT code_id, code_hash FROM rls.auth_backup_codes(%s)", [user_id])
        rows = cursor.fetchall()
    return tuple(StoredBackupCode(code_id=row[0], code_hash=row[1]) for row in rows)


def spend_backup_code(code_id: uuid.UUID) -> bool:
    """Consume one code. False means it was already spent -- by another request,
    or by this user a moment ago; the condition and the write are one statement,
    so the race has one winner."""
    with _privileged_cursor() as cursor:
        cursor.execute("SELECT rls.auth_spend_backup_code(%s)", [code_id])
        row = cursor.fetchone()
    return bool(row and row[0])


def resolve_session(token_hash: str) -> ResolvedSession | None:
    """The live session behind a token, or None.

    None covers three cases -- unknown token, expired session, revoked session --
    and keeps covering them as one: whichever it is, the caller has no session
    and there is nothing else it could usefully do with the distinction.
    """
    with _privileged_cursor() as cursor:
        cursor.execute(
            "SELECT session_id, user_id, tenant_id, actor_firm_id, support_grant_id "
            "FROM rls.resolve_session(%s)",
            [token_hash],
        )
        row = cursor.fetchone()
    if row is None:
        return None
    return ResolvedSession(
        session_id=row[0],
        user_id=row[1],
        tenant_id=row[2],
        actor_firm_id=row[3],
        support_grant_id=row[4],
    )


def support_grant_for(user_id: uuid.UUID, tenant_id: uuid.UUID) -> uuid.UUID | None:
    """The approved, live support grant of this person on this tenant -- or None.

    Asked at login, after both factors and after the ordinary access check has
    failed (ADR-077 §6): a member signs in as a member; only somebody the
    tenant's policies do not admit is tried as support. The function also wants
    a live `support` row in `platform_staff`, so an employee who has left does
    not get in on a grant that outlived them.
    """
    with _privileged_cursor() as cursor:
        cursor.execute("SELECT rls.auth_support_grant(%s, %s)", [user_id, tenant_id])
        row = cursor.fetchone()
    return None if row is None or row[0] is None else uuid.UUID(str(row[0]))
