"""Roles are data the tenant edits; the database is what keeps that safe.

ADR-020 puts authorisation into a table the client writes to. The risk it names
is obvious -- a client granting itself a right the product never anticipated --
and the answer is not trust. These tests are that answer: every protection is
tried from the side that would exploit it, and expected to fail there.

Split by who refuses:

* the **policy**, for what one tenant may see of another's roles;
* the **grants**, for the catalogue, which the application may read and never write;
* the **composite foreign keys**, for rows that would point across a tenant border
  or mix permission levels;
* the **triggers**, for the two deletions that would lock a tenant out of itself;
* the **service**, for the rules that need to count rows before deciding.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any

import pytest
from django.db import connection, transaction
from django.db.utils import InternalError, NotSupportedError, ProgrammingError

from evidenta.platform.identity.models import Membership, MembershipStatus, Role, RoleLevel
from evidenta.platform.identity.permissions import MANAGE_ROLES
from evidenta.platform.identity.services import roles as role_service
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.isolation.conftest import role_id

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

WRITE_REFUSED = (ProgrammingError, InternalError, NotSupportedError)


def as_user(tenant_id: uuid.UUID, user_id: uuid.UUID) -> TenantContext:
    return TenantContext(tenant_id=tenant_id, user_id=user_id, request_id="test")


def query(sql: str, params: Sequence[Any] | None = None) -> list[tuple[object, ...]]:
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        return cursor.fetchall()


# --- what the policy refuses -------------------------------------------------


def test_roles_of_another_tenant_are_invisible(world: dict[str, uuid.UUID]) -> None:
    """Both tenants have the same system roles. Each sees only its own."""
    with tenant_context(as_user(world["tenant_a"], world["user_a"])):
        rows = query("SELECT tenant_id FROM role")
    assert rows
    assert {row[0] for row in rows} == {world["tenant_a"]}


def test_a_role_cannot_be_written_into_another_tenant(world: dict[str, uuid.UUID]) -> None:
    """WITH CHECK, not only USING: the write path is the one that matters here."""
    with (
        tenant_context(as_user(world["tenant_a"], world["user_a"])),
        pytest.raises(WRITE_REFUSED),
        transaction.atomic(),
    ):
        query(
            "INSERT INTO role (id, tenant_id, key, name, level, is_system,"
            " created_at, updated_at)"
            " VALUES (%s, %s, 'stolen', 'stolen', 'tenant', false, now(), now())",
            [uuid.uuid4(), world["tenant_b"]],
        )


# --- what the grants refuse --------------------------------------------------


def test_the_catalogue_is_readable(world: dict[str, uuid.UUID]) -> None:
    with tenant_context(as_user(world["tenant_a"], world["user_a"])):
        keys = {row[0] for row in query("SELECT key FROM permission")}
    assert MANAGE_ROLES in keys


def test_the_catalogue_cannot_be_extended_by_the_application(
    world: dict[str, uuid.UUID],
) -> None:
    """The heart of ADR-020: the client composes roles, never permissions.

    A tenant that could insert here would grant itself a key the product does not
    check anywhere -- which is not a privilege escalation today, but becomes one
    the moment a later release starts checking that key.
    """
    with (
        tenant_context(as_user(world["tenant_a"], world["user_a"])),
        pytest.raises(WRITE_REFUSED),
        transaction.atomic(),
    ):
        query("INSERT INTO permission (key, scope) VALUES ('invented.right', 'tenant')")


# --- what the composite foreign keys refuse ----------------------------------


def test_a_membership_cannot_carry_another_tenants_role(
    world: dict[str, uuid.UUID], seed: Callable[..., None]
) -> None:
    """Django cannot express this constraint; the accompanying SQL can.

    Seeded through the privileged connection on purpose: if the *superuser* is
    refused, no application path can get past it either.
    """
    now = datetime.now(UTC)
    # A user with no membership yet: otherwise `membership_live_unique` fires
    # first and the test proves the wrong constraint.
    newcomer = uuid.uuid4()
    seed(
        'INSERT INTO "user" (id, email, full_name, mfa_enabled, locale, is_active,'
        " created_at, updated_at)"
        " VALUES (%s, 'newcomer@example.md', 'N', false, 'ro', true, %s, %s)",
        [newcomer, now, now],
    )
    with pytest.raises(Exception, match="membership_role_same_tenant"):
        seed(
            "INSERT INTO membership (id, tenant_id, user_id, role_id, status,"
            " invited_at, accepted_at, created_at, updated_at)"
            " VALUES (%s, %s, %s, %s, 'active', %s, %s, %s, %s)",
            [
                uuid.uuid4(),
                world["tenant_a"],
                newcomer,
                role_id(world["tenant_b"], "owner"),
                now,
                now,
                now,
                now,
            ],
        )


def test_a_tenant_role_cannot_hold_a_company_permission(
    world: dict[str, uuid.UUID], seed: Callable[..., None]
) -> None:
    """One key, two invariants: same tenant, and matching level."""
    with pytest.raises(Exception, match="role_permission_role_same_tenant_and_level"):
        seed(
            "INSERT INTO role_permission (id, tenant_id, role_id, permission_key, scope)"
            " VALUES (%s, %s, %s, 'company.revoke_access', 'company')",
            [uuid.uuid4(), world["tenant_a"], role_id(world["tenant_a"], "owner")],
        )


# --- what the triggers refuse ------------------------------------------------


def test_a_system_role_cannot_be_deleted(world: dict[str, uuid.UUID]) -> None:
    with (
        tenant_context(as_user(world["tenant_a"], world["user_a"])),
        pytest.raises(Exception, match="cannot be deleted"),
        transaction.atomic(),
    ):
        query("DELETE FROM role WHERE id = %s", [world["role_owner_a"]])


def test_a_system_role_cannot_lose_the_administration_permission(
    world: dict[str, uuid.UUID], seed: Callable[..., None]
) -> None:
    """The lock-out this prevents is not hypothetical: it is one DELETE away."""
    seed(
        "INSERT INTO role_permission (id, tenant_id, role_id, permission_key, scope)"
        " VALUES (%s, %s, %s, %s, 'tenant')",
        [uuid.uuid4(), world["tenant_a"], world["role_owner_a"], MANAGE_ROLES],
    )
    with (
        tenant_context(as_user(world["tenant_a"], world["user_a"])),
        pytest.raises(Exception, match="cannot lose"),
        transaction.atomic(),
    ):
        query(
            "DELETE FROM role_permission WHERE role_id = %s AND permission_key = %s",
            [world["role_owner_a"], MANAGE_ROLES],
        )


# --- what the service refuses ------------------------------------------------


def test_create_system_roles_is_idempotent(world: dict[str, uuid.UUID]) -> None:
    """Re-running repairs an interrupted tenant creation instead of failing."""
    with tenant_context(as_user(world["tenant_a"], world["user_a"])):
        first = role_service.create_system_roles(world["tenant_a"])
        second = role_service.create_system_roles(world["tenant_a"])
    assert {r.id for r in first.values()} == {r.id for r in second.values()}


def test_permission_follows_the_active_membership(world: dict[str, uuid.UUID]) -> None:
    """A suspended membership keeps its row and grants nothing."""
    with tenant_context(as_user(world["tenant_a"], world["user_a"])):
        role_service.create_system_roles(world["tenant_a"])
        owner = Role.objects.get(tenant_id=world["tenant_a"], key="owner")
        Membership.objects.filter(tenant_id=world["tenant_a"]).update(role=owner)

        assert role_service.has_permission(world["user_a"], world["tenant_a"], MANAGE_ROLES)

        Membership.objects.filter(user_id=world["user_a"]).update(status=MembershipStatus.SUSPENDED)
        assert not role_service.has_permission(world["user_a"], world["tenant_a"], MANAGE_ROLES)


def test_giving_up_administration_is_refused_because_it_cannot_be_verified(
    world: dict[str, uuid.UUID],
) -> None:
    """Fail-closed, and honest about which fact is missing.

    The rule ADR-020 wants is "the *last* administrator cannot be demoted". It
    cannot be checked: proving another administrator exists means reading other
    people's memberships, and the policy on that table shows the caller their own
    row only (OD-37). So the move is refused whether or not a second
    administrator exists -- and the code says which of the two it is refusing on,
    instead of reporting the stronger claim it cannot support.
    """
    with tenant_context(as_user(world["tenant_a"], world["user_a"])):
        role_service.create_system_roles(world["tenant_a"])
        owner = Role.objects.get(tenant_id=world["tenant_a"], key="owner")
        membership = Membership.objects.get(user_id=world["user_a"])
        membership.role = owner
        membership.save(update_fields=["role"])

        viewer = Role.objects.create(
            tenant_id=world["tenant_a"],
            key="viewer",
            name="viewer",
            level=RoleLevel.TENANT,
            is_system=False,
        )
        with pytest.raises(role_service.RoleError) as refused:
            role_service.assign_role(membership, viewer)
    assert refused.value.code == "ADMINISTRATION_UNPROVABLE"


def test_a_membership_refuses_a_company_role(world: dict[str, uuid.UUID]) -> None:
    """Membership is the tenant-level relationship; CompanyAccess is the other one."""
    with tenant_context(as_user(world["tenant_a"], world["user_a"])):
        role_service.create_system_roles(world["tenant_a"])
        company_role = Role.objects.get(tenant_id=world["tenant_a"], key="company_admin")
        membership = Membership.objects.get(user_id=world["user_a"])
        with pytest.raises(role_service.RoleError) as refused:
            role_service.assign_role(membership, company_role)
    assert refused.value.code == "ROLE_LEVEL_MISMATCH"


def test_a_second_administrator_does_not_change_the_answer(
    world: dict[str, uuid.UUID], seed: Callable[..., None]
) -> None:
    """The proof that the refusal above is a limit, not the rule ADR-020 asked for.

    A second active administrator exists here. The service still refuses, because
    it cannot see them. Without this test the previous one passes for the wrong
    reason, and the day OD-37 is decided nobody knows which of the two behaviours
    was ever verified.
    """
    now = datetime.now(UTC)
    colleague = uuid.uuid4()
    seed(
        'INSERT INTO "user" (id, email, full_name, mfa_enabled, locale, is_active,'
        " created_at, updated_at)"
        " VALUES (%s, 'colleague@example.md', 'C', false, 'ro', true, %s, %s)",
        [colleague, now, now],
    )
    seed(
        "INSERT INTO membership (id, tenant_id, user_id, role_id, status,"
        " invited_at, accepted_at, created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, 'active', %s, %s, %s, %s)",
        [uuid.uuid4(), world["tenant_a"], colleague, world["role_owner_a"], now, now, now, now],
    )

    with tenant_context(as_user(world["tenant_a"], world["user_a"])):
        role_service.create_system_roles(world["tenant_a"])
        owner = Role.objects.get(tenant_id=world["tenant_a"], key="owner")
        membership = Membership.objects.get(user_id=world["user_a"])
        membership.role = owner
        membership.save(update_fields=["role"])

        viewer = Role.objects.create(
            tenant_id=world["tenant_a"],
            key="viewer2",
            name="viewer2",
            level=RoleLevel.TENANT,
            is_system=False,
        )
        with pytest.raises(role_service.RoleError) as refused:
            role_service.assign_role(membership, viewer)
    assert refused.value.code == "ADMINISTRATION_UNPROVABLE"


def test_another_members_role_cannot_be_changed(world: dict[str, uuid.UUID]) -> None:
    """The invisible row must not read as "no such member"."""
    with tenant_context(as_user(world["tenant_a"], world["user_a"])):
        role_service.create_system_roles(world["tenant_a"])
        owner = Role.objects.get(tenant_id=world["tenant_a"], key="owner")
        someone_else = Membership(
            id=uuid.uuid4(),
            tenant_id=world["tenant_a"],
            user_id=world["user_b"],
            role=owner,
            status=MembershipStatus.ACTIVE,
            invited_at=datetime.now(UTC),
        )
        with pytest.raises(role_service.RoleError) as refused:
            role_service.assign_role(someone_else, owner)
    assert refused.value.code == "MEMBER_ADMINISTRATION_BLOCKED"


def test_permissions_of_another_user_cannot_be_checked(world: dict[str, uuid.UUID]) -> None:
    """A quiet "denied" for a question the shape cannot answer is the wrong answer."""
    with (
        tenant_context(as_user(world["tenant_a"], world["user_a"])),
        pytest.raises(role_service.RoleError) as refused,
    ):
        role_service.has_permission(world["user_b"], world["tenant_a"], MANAGE_ROLES)
    assert refused.value.code == "PERMISSION_CHECK_NOT_SELF"


def test_a_system_role_cannot_be_stripped_of_its_flag(world: dict[str, uuid.UUID]) -> None:
    """The bypass the DELETE-only trigger left open, closed and proven closed.

    `UPDATE role SET is_system = false` followed by `DELETE` defeated the original
    protection completely: the trigger read OLD.is_system, already false by then.
    The application holds UPDATE on this table, so this was two ordinary
    statements, not an exotic attack.
    """
    with (
        tenant_context(as_user(world["tenant_a"], world["user_a"])),
        pytest.raises(Exception, match="is_system cannot be changed"),
        transaction.atomic(),
    ):
        query("UPDATE role SET is_system = false WHERE id = %s", [world["role_owner_a"]])


def test_a_permission_row_cannot_be_rewritten_into_another(
    world: dict[str, uuid.UUID], seed: Callable[..., None]
) -> None:
    """The second bypass: no row is deleted, so a BEFORE DELETE trigger never runs.

    Rewriting `permission_key` stripped `tenant.manage_roles` from a system role
    while leaving the row count unchanged -- invisible to every check that watched
    deletions.
    """
    seed(
        "INSERT INTO role_permission (id, tenant_id, role_id, permission_key, scope)"
        " VALUES (%s, %s, %s, %s, 'tenant')",
        [uuid.uuid4(), world["tenant_a"], world["role_owner_a"], MANAGE_ROLES],
    )
    with (
        tenant_context(as_user(world["tenant_a"], world["user_a"])),
        pytest.raises(Exception, match="granted or revoked, never rewritten"),
        transaction.atomic(),
    ):
        query(
            "UPDATE role_permission SET permission_key = 'engagement.invite'"
            " WHERE role_id = %s AND permission_key = %s",
            [world["role_owner_a"], MANAGE_ROLES],
        )
