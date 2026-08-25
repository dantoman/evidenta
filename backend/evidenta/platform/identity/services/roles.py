"""Composing roles, and the guards that keep the composition safe -- ADR-020.

The decision this file implements: roles are data the tenant edits, permissions
are a fixed catalogue in code. What makes that safe is not trust but shape --
a role can only hold keys the product enforces somewhere, and the database is
what refuses everything else.

Three protections live here rather than in an interface, because an interface is
one of several callers:

1. A system role cannot be deleted, and cannot lose ``tenant.manage_roles``.
   Also enforced by trigger (``0019_roles.up.sql``); the check here exists to
   fail with a stable code instead of a database error.
2. The last active holder of ``tenant.manage_roles`` cannot be demoted. Without
   it, the first tenant that edits its roles badly is locked out of itself and
   recovery becomes a manual intervention in production.
3. A role holds permissions of its own level only. The composite foreign key
   enforces it; the message here says which level was expected.
"""

from __future__ import annotations

import uuid

from django.db import transaction

from evidenta.platform.audit.services.recording import record
from evidenta.platform.identity.models import (
    Membership,
    MembershipStatus,
    Permission,
    Role,
    RoleLevel,
    RolePermission,
)
from evidenta.platform.identity.permissions import MANAGE_ROLES, permissions_for_scope
from evidenta.platform.rls.context import current_context

#: The roles the platform creates with every tenant. Keys are codes; what they
#: are called in the interface lives in the frontend resource files (C32).
SYSTEM_ROLES: tuple[tuple[str, str], ...] = (
    ("owner", RoleLevel.TENANT),
    ("company_admin", RoleLevel.COMPANY),
)


class RoleError(RuntimeError):
    """A role operation the product refuses, with a stable code (C10)."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def create_system_roles(tenant_id: uuid.UUID) -> dict[str, Role]:
    """Create the tenant's system roles, holding every permission of their level.

    Called when the tenant is created -- a privileged path, since a tenant that
    does not exist yet has no context under which anything could be inserted.

    Idempotent: re-running repairs a tenant whose creation was interrupted, which
    is the state that otherwise needs a human with database access.
    """
    created: dict[str, Role] = {}
    with transaction.atomic():
        for key, level in SYSTEM_ROLES:
            role, _ = Role.objects.get_or_create(
                tenant_id=tenant_id,
                key=key,
                defaults={"name": key, "level": level, "is_system": True},
            )
            created[key] = role
            for permission_key in permissions_for_scope(level):
                RolePermission.objects.get_or_create(
                    tenant_id=tenant_id,
                    role=role,
                    permission_id=permission_key,
                    defaults={"scope": level},
                )
    return created


def has_permission(user_id: uuid.UUID, tenant_id: uuid.UUID, permission_key: str) -> bool:
    """Does the **current** user hold this permission in this tenant, right now?

    Reads through the active membership only. A suspended or removed membership
    keeps its row -- history is not rewritten -- but grants nothing.

    Answers about the caller and nobody else, and says so instead of guessing:
    ``membership`` is policed as ``user_id = app.current_user_id()``, so a query
    about another user sees no rows and would return a confident, wrong ``False``.
    Asking about someone else is a question this shape cannot answer, and the
    difference between "no" and "cannot tell" is exactly what an authorisation
    check must not blur. Answering it needs `OD-37`.
    """
    context = current_context()
    if context is not None and context.user_id != user_id:
        raise RoleError(
            "PERMISSION_CHECK_NOT_SELF",
            "permissions can only be checked for the current user until OD-37 is decided",
        )
    return RolePermission.objects.filter(
        tenant_id=tenant_id,
        permission_id=permission_key,
        role__membership__user_id=user_id,
        role__membership__status=MembershipStatus.ACTIVE,
    ).exists()


def require_permission(user_id: uuid.UUID, tenant_id: uuid.UUID, permission_key: str) -> None:
    """Refuse, loudly and with a stable code, unless the permission is held."""
    if not has_permission(user_id, tenant_id, permission_key):
        raise RoleError("PERMISSION_DENIED", f"{permission_key} is required")


def grant_permission(role: Role, permission_key: str, granted_by_user_id: uuid.UUID) -> None:
    """Add one permission to a role.

    Granting ``tenant.manage_roles`` is audited without exception: it is the
    permission from which every other one can be derived, so the interesting
    question after an incident is who handed it out, not who used it.
    """
    permission = Permission.objects.get(pk=permission_key)
    if permission.scope != role.level:
        raise RoleError(
            "ROLE_LEVEL_MISMATCH",
            f"{permission_key} is a {permission.scope} permission, role {role.key} is {role.level}",
        )

    with transaction.atomic():
        _, created = RolePermission.objects.get_or_create(
            tenant_id=role.tenant_id,
            role=role,
            permission=permission,
            defaults={"scope": role.level},
        )
        if created and permission_key == MANAGE_ROLES:
            record(
                action="role.grant_manage_roles",
                entity_type="role",
                entity_id=role.id,
                new_value={"role_key": role.key, "granted_by": str(granted_by_user_id)},
            )


def revoke_permission(role: Role, permission_key: str) -> None:
    """Remove one permission from a role, unless that would disarm the tenant."""
    if role.is_system and permission_key == MANAGE_ROLES:
        raise RoleError(
            "SYSTEM_ROLE_PROTECTED",
            f"system role {role.key} cannot lose {MANAGE_ROLES}",
        )
    RolePermission.objects.filter(role=role, permission_id=permission_key).delete()


def delete_role(role: Role) -> None:
    """Delete a role the tenant composed. System roles are not deletable."""
    if role.is_system:
        raise RoleError("SYSTEM_ROLE_PROTECTED", f"system role {role.key} cannot be deleted")
    role.delete()


def assign_role(membership: Membership, role: Role) -> Membership:
    """Move a membership to another role, refusing every move it cannot verify.

    **What works today, and why the rest does not.** ``membership`` is policed as
    ``user_id = app.current_user_id()`` (ADR-003), so a session sees exactly one
    membership row per tenant: its own. That has two consequences this function
    states rather than trips over:

    * An administrator cannot move **someone else's** membership -- the row is
      invisible, and the ORM would report it as "does not exist", which reads as
      "no such member" and is a different fact entirely.
    * The anti-lockout rule of ADR-020 -- the last user who can administer roles
      may not be demoted -- cannot be *verified*, because proving another
      administrator exists means reading other people's memberships. So a move
      that would give up ``tenant.manage_roles`` is refused outright: fail-closed
      where the alternative is a tenant locked out of itself.

    Both need `OD-37` -- how members of a tenant are listed at all -- and neither
    is worked around here. Widening the policy from the service side would be the
    same move the policy's own migration forbids without an ADR.
    """
    if role.level != RoleLevel.TENANT:
        raise RoleError(
            "ROLE_LEVEL_MISMATCH", f"membership needs a tenant role, {role.key} is {role.level}"
        )
    if role.tenant_id != membership.tenant_id:
        raise RoleError("ROLE_OTHER_TENANT", "the role belongs to another tenant")

    context = current_context()
    if context is not None and context.user_id != membership.user_id:
        raise RoleError(
            "MEMBER_ADMINISTRATION_BLOCKED",
            "another member's role cannot be changed until OD-37 is decided",
        )

    with transaction.atomic():
        locked = Membership.objects.select_for_update().get(pk=membership.pk)
        _assert_administration_survives(locked, role)
        locked.role = role
        locked.save(update_fields=["role", "updated_at"])
        return locked


def _assert_administration_survives(membership: Membership, new_role: Role) -> None:
    """Refuse a move that gives up role administration and cannot prove it is safe.

    The check the rule really wants is "is there another active administrator?".
    It is not written here, and not because it was forgotten: the query would run
    against ``membership``, which shows the caller their own row only. Written
    anyway, it would find nobody, always -- and a guard that always fires is
    indistinguishable from one that works, right up to the day it matters.
    """
    if not _role_grants(membership.role_id, MANAGE_ROLES):
        return  # They could not administer roles anyway; nothing is being lost.
    if _role_grants(new_role.id, MANAGE_ROLES):
        return  # The new role still can.

    raise RoleError(
        "ADMINISTRATION_UNPROVABLE",
        "giving up tenant.manage_roles cannot be verified as safe until OD-37 is decided",
    )


def _role_grants(role_id: uuid.UUID, permission_key: str) -> bool:
    return RolePermission.objects.filter(role_id=role_id, permission_id=permission_key).exists()
