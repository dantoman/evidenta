"""Who is an employee of the platform, and with what role -- ADR-076 §4.1.

Two readers and one writer, and they run in different worlds on purpose.

The **readers** run inside a context, through the ordinary ``platform_staff_self``
policy: the console's doors ask "is the caller staff, and which role", and the
login on the ``admin.`` host asks the same before issuing a session. Both see
exactly one row -- the caller's -- which is all either needs. Nothing here lists
the staff: that list is not the application role's to read (0075), and the
screen that will show it to an `admin` gets its own privileged path (OD-133).

The **writer** is the operator command, under the installation role and before
any console exists: somebody has to be the first `admin`, and that somebody is
granted the way the first tenant is created (`create_tenant`) -- a DBA act,
spelled that way, with the operating-system login as the actor. Every later grant
belongs to the console and to the path OD-133 decides.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

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


class StaffGrantError(RuntimeError):
    """The grant cannot be made as asked."""


def grant_staff(*, user: User, staff_role: str, granted_by: User) -> PlatformStaff:
    """Make ``user`` an employee of the platform with ``staff_role``.

    For the operator command only -- the connection it runs on decides whether the
    write is permitted, and under the application role it never is (0075). A
    user who already holds a live row is refused rather than re-roled: changing
    a role is a revocation and a new grant, so that both dates exist.
    """
    if staff_role not in StaffRole.values:
        raise StaffGrantError(f"{staff_role!r} is not one of {StaffRole.values}")
    if PlatformStaff.objects.filter(user=user, revoked_at__isnull=True).exists():
        raise StaffGrantError(
            f"{user.email} already holds a live staff role; revoke it first -- a change of "
            f"role is a revocation and a new grant, so that both dates exist"
        )
    if PlatformStaff.objects.filter(user=user).exists():
        # The primary key is the user, so a revoked row occupies the slot. A
        # re-grant re-opens it with the new role and a fresh grant date; the
        # revocation date is cleared because the row is live again.
        row = PlatformStaff.objects.get(user=user)
        row.staff_role = staff_role
        row.granted_by = granted_by
        row.granted_at = datetime.now(tz=UTC)
        row.revoked_at = None
        row.save(update_fields=["staff_role", "granted_by", "granted_at", "revoked_at"])
        return row
    return PlatformStaff.objects.create(
        user=user,
        staff_role=staff_role,
        granted_by=granted_by,
        granted_at=datetime.now(tz=UTC),
    )


def revoke_staff(*, user: User) -> bool:
    """End a live staff role. False when there was none to end."""
    return (
        PlatformStaff.objects.filter(user=user, revoked_at__isnull=True).update(
            revoked_at=datetime.now(tz=UTC)
        )
        > 0
    )
