"""Who is an employee of the platform, and with what role -- ADR-076 §4.1, ADR-092.

Three kinds of caller, and they run in different worlds on purpose.

The **per-request readers** run inside a context, through the ordinary
``platform_staff_self`` policy: the console's doors ask "is the caller staff, and
which role", and the login on the ``admin.`` host asks the same before issuing a
session. Both see exactly one row -- the caller's -- which is all either needs.

The **console's list** is a cross-tenant read of platform metadata and goes
through ``rls.console_staff()`` -- a narrow, staff-gated function (0076) that
refuses under a tenant context and refuses a caller with no live row, before it
reads anything. Same for finding the account behind an e-mail address.

The **writers** are two. The operator command grants the first `admin` under the
installation role, before any console exists -- the same act as `create_tenant`.
Every later grant and revocation is the console's, by an `admin`, on the
reference-data connection inside `privileged_run` (`P-12`, ADR-092), which is
what leaves the row in `privileged_access_log`.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from django.db import DEFAULT_DB_ALIAS, connection

from evidenta.platform.identity.models import PlatformStaff, StaffRole, User


@dataclass(frozen=True, slots=True)
class StaffMembership:
    """What a door needs to know about the caller, and nothing more."""

    user_id: uuid.UUID
    staff_role: str
    granted_at: datetime


def staff_role_in_context(user_id: uuid.UUID) -> StaffMembership | None:
    """The caller's live staff row, or None.

    ``user_id`` is passed rather than read from the context so the login can ask
    about the person it has just verified -- but the policy narrows the answer to
    the context's own user regardless, so a caller that asked about somebody else
    would get None, not their row.
    """
    row = PlatformStaff.objects.filter(user_id=user_id, revoked_at__isnull=True).first()
    if row is None:
        return None
    return StaffMembership(
        user_id=uuid.UUID(str(row.user_id)),
        staff_role=str(row.staff_role),
        granted_at=row.granted_at,
    )


@dataclass(frozen=True, slots=True)
class StaffRow:
    """One line of the console's staff page -- history included."""

    user_id: uuid.UUID
    email: str
    full_name: str
    staff_role: str
    granted_by_email: str
    granted_at: datetime
    revoked_at: datetime | None


@contextmanager
def _console_cursor() -> Iterator[Any]:
    # On the request's own connection, inside its context: the function itself
    # checks that the context is the console's and the caller is staff.
    with connection.cursor() as cursor:
        yield cursor


def list_staff() -> list[StaffRow]:
    """Every grant ever made, live ones first -- through `rls.console_staff()`."""
    with _console_cursor() as cursor:
        cursor.execute(
            "SELECT user_id, email, full_name, staff_role, granted_by_email, granted_at, "
            "revoked_at FROM rls.console_staff()"
        )
        rows = cursor.fetchall()
    return [
        StaffRow(
            user_id=row[0],
            email=row[1],
            full_name=row[2],
            staff_role=row[3],
            granted_by_email=row[4],
            granted_at=row[5],
            revoked_at=row[6],
        )
        for row in rows
    ]


def user_id_by_email(email: str) -> uuid.UUID | None:
    """The active account behind an address, for granting -- or None."""
    with _console_cursor() as cursor:
        cursor.execute("SELECT user_id FROM rls.console_user_by_email(%s)", [email.strip()])
        row = cursor.fetchone()
    return None if row is None else uuid.UUID(str(row[0]))


class StaffGrantError(RuntimeError):
    """The grant or revocation cannot be made as asked. ``code`` is stable (C10)."""

    code = "staff.invalid"
    status = 400


class StaffRoleInvalidError(StaffGrantError):
    code = "staff.role_invalid"


class StaffAlreadyLiveError(StaffGrantError):
    code = "staff.already_live"
    status = 409


class StaffNotLiveError(StaffGrantError):
    code = "staff.not_live"
    status = 409


class StaffSelfRevocationError(StaffGrantError):
    """The last admin locking everyone out is the failure this prevents."""

    code = "staff.cannot_revoke_self"
    status = 409


def grant_staff_by_id(
    *,
    user_id: uuid.UUID,
    staff_role: str,
    granted_by_user_id: uuid.UUID,
    using: str = DEFAULT_DB_ALIAS,
) -> PlatformStaff:
    """Make ``user_id`` an employee of the platform with ``staff_role``.

    The connection decides whether the write is permitted: the installation role
    for the operator command, the reference-data role for the console (0075). A
    person who already holds a live row is refused rather than re-roled: changing
    a role is a revocation and a new grant, so that both dates exist. A revoked
    row is re-opened -- the primary key is the person -- with a fresh grant date.
    """
    if staff_role not in StaffRole.values:
        raise StaffRoleInvalidError(f"{staff_role!r} is not one of {StaffRole.values}")
    rows = PlatformStaff.objects.using(using)
    if rows.filter(user_id=user_id, revoked_at__isnull=True).exists():
        raise StaffAlreadyLiveError(
            "this person already holds a live staff role; revoke it first -- a change of "
            "role is a revocation and a new grant, so that both dates exist"
        )
    now = datetime.now(tz=UTC)
    existing = rows.filter(user_id=user_id).first()
    if existing is not None:
        existing.staff_role = staff_role
        existing.granted_by_id = granted_by_user_id
        existing.granted_at = now
        existing.revoked_at = None
        existing.save(
            using=using, update_fields=["staff_role", "granted_by", "granted_at", "revoked_at"]
        )
        return existing
    return rows.create(
        user_id=user_id,
        staff_role=staff_role,
        granted_by_id=granted_by_user_id,
        granted_at=now,
    )


def revoke_staff_by_id(
    *, user_id: uuid.UUID, revoked_by_user_id: uuid.UUID, using: str = DEFAULT_DB_ALIAS
) -> None:
    """End a live staff role. Refuses the caller's own, and a row that is not live."""
    if user_id == revoked_by_user_id:
        raise StaffSelfRevocationError(
            "an employee does not revoke their own role: the last admin would lock "
            "the console for everyone, with nobody left to reopen it"
        )
    ended = (
        PlatformStaff.objects.using(using)
        .filter(user_id=user_id, revoked_at__isnull=True)
        .update(revoked_at=datetime.now(tz=UTC))
    )
    if not ended:
        raise StaffNotLiveError("this person holds no live staff role")


def grant_staff(*, user: User, staff_role: str, granted_by: User) -> PlatformStaff:
    """The operator command's entry: the same rule, keyed by rows it already holds."""
    return grant_staff_by_id(
        user_id=uuid.UUID(str(user.pk)),
        staff_role=staff_role,
        granted_by_user_id=uuid.UUID(str(granted_by.pk)),
    )


def revoke_staff(*, user: User) -> bool:
    """The operator command's revocation. False when there was none to end.

    No self-check here: the shell is where a locked-out console is repaired, so
    the shell must be able to end any row, including the operator's own.
    """
    return (
        PlatformStaff.objects.filter(user=user, revoked_at__isnull=True).update(
            revoked_at=datetime.now(tz=UTC)
        )
        > 0
    )
