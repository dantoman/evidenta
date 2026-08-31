"""What the signed-in user may do in the workspace they are looking at.

Read-only, and **only about themselves** -- which is not a simplification but the
shape of the policies. ``membership`` and ``company_access`` are policed as
``user_id = app.current_user_id()`` (0011, 0014): a query about somebody else
returns no rows, so a service that listed "the people of this workspace" would
answer a confident, empty, wrong list. Answering that needs `OD-37`; until it is
decided, this module answers about the caller and says so.

``role`` and ``role_permission`` are ordinary tenant-scoped tables, so *what
rights exist here* is answerable in full, even though *who holds them* is not.
That asymmetry is the honest state of the product and the screen shows it as such.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from evidenta.platform.identity.models import (
    CompanyAccess,
    Membership,
    MembershipStatus,
    Role,
    RolePermission,
    User,
)


@dataclass(frozen=True)
class RoleView:
    key: str
    name: str
    level: str
    is_system: bool
    permissions: tuple[str, ...]


@dataclass(frozen=True)
class CompanyAccessView:
    company_id: uuid.UUID
    role_key: str
    #: ``membership`` or ``engagement`` -- how this right arrived. The difference
    #: is what a person needs to know before writing in somebody's books.
    granted_via: str


@dataclass(frozen=True)
class MyAccess:
    #: Who the caller is, answered here rather than by the view reading `User`.
    #: `D6` is why: modules talk through public services, and a view that reached
    #: into another module's models would be the shape the rule exists to refuse.
    email: str
    full_name: str
    membership_status: str | None
    role: RoleView | None
    companies: tuple[CompanyAccessView, ...]


def _permissions_of(role_id: uuid.UUID) -> tuple[str, ...]:
    return tuple(
        RolePermission.objects.filter(role_id=role_id)
        .order_by("permission_id")
        .values_list("permission_id", flat=True)
    )


def _as_view(role: Role) -> RoleView:
    return RoleView(
        key=role.key,
        name=role.name,
        level=role.level,
        is_system=role.is_system,
        permissions=_permissions_of(role.id),
    )


def describe_my_access(user_id: uuid.UUID, tenant_id: uuid.UUID) -> MyAccess:
    """The caller's standing in this workspace: membership, role, companies.

    ``tenant_id`` is filtered explicitly, and that is **not** the manager C3
    forbids. C3 is about hiding a missing context behind a filter that looks like
    safety; here the policy genuinely does not scope the row -- ``membership`` is
    self-row precisely because ``rls.has_tenant_access`` reads it and a
    predicate-based policy would recurse -- so a user's memberships in *other*
    workspaces are visible to them and have to be excluded by the question, not
    by the guard.
    """
    membership = (
        Membership.objects.filter(tenant_id=tenant_id, user_id=user_id)
        .exclude(status=MembershipStatus.REMOVED)
        .select_related("role")
        .first()
    )

    access = (
        CompanyAccess.objects.filter(tenant_id=tenant_id, user_id=user_id, revoked_at__isnull=True)
        .select_related("role")
        .order_by("granted_via", "company_id")
    )

    # The self-row policy on `user` is what makes this one row and not a lookup
    # over people: a query about anybody else comes back empty.
    user = User.objects.get(pk=user_id)

    return MyAccess(
        email=user.email,
        full_name=user.full_name,
        membership_status=membership.status if membership else None,
        role=_as_view(membership.role) if membership else None,
        companies=tuple(
            CompanyAccessView(
                company_id=row.company_id,
                role_key=row.role.key,
                granted_via=row.granted_via,
            )
            for row in access
        ),
    )


def roles_in_context() -> tuple[RoleView, ...]:
    """Every role of the workspace in context, with what each one may do.

    No filter: ``role`` carries the tenant template policy, so the rows that come
    back are the workspace's own (C3).
    """
    return tuple(_as_view(role) for role in Role.objects.all().order_by("level", "key"))
