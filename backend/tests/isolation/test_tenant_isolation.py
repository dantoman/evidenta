"""Tenant A cannot reach tenant B. The first cases against real tables.

Until now the suite proved the *mechanism* -- context is required, tasks refuse
without it. These prove the *outcome*: with everything working normally, the data
of another tenant is unreachable.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import pytest
from django.db import connection

from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])


def as_user(tenant_id: uuid.UUID, user_id: uuid.UUID) -> TenantContext:
    return TenantContext(tenant_id=tenant_id, user_id=user_id, request_id="test")


def query(sql: str, params: Sequence[Any] | None = None) -> list[tuple[object, ...]]:
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        return cursor.fetchall()


def test_member_sees_own_tenant(world: dict[str, uuid.UUID]) -> None:
    """IZ-01, on the membership access path."""
    with tenant_context(as_user(world["tenant_a"], world["user_a"])):
        rows = query("SELECT subdomain FROM tenant")
    assert rows == [("alpha",)]


def test_member_cannot_reach_another_tenant(world: dict[str, uuid.UUID]) -> None:
    """IZ-03. The context claims tenant B; the predicate says no."""
    with tenant_context(as_user(world["tenant_b"], world["user_a"])):
        rows = query("SELECT subdomain FROM tenant")
    assert rows == []


def test_membership_shows_only_own_rows(world: dict[str, uuid.UUID]) -> None:
    """IZ-08. Both memberships exist; each user sees one."""
    with tenant_context(as_user(world["tenant_a"], world["user_a"])):
        assert len(query("SELECT id FROM membership")) == 1
    with tenant_context(as_user(world["tenant_b"], world["user_b"])):
        assert len(query("SELECT id FROM membership")) == 1


def test_user_table_shows_only_the_caller(world: dict[str, uuid.UUID]) -> None:
    """The global table is reachable without tenant context -- so it shows one row.

    This is what makes it safe for User to carry no business fields, and unsafe
    for it to carry any.
    """
    with tenant_context(as_user(world["tenant_a"], world["user_a"])):
        rows = query('SELECT email FROM "user"')
    assert rows == [("a@example.md",)]


def test_suspended_membership_grants_nothing(world: dict[str, uuid.UUID], seed: object) -> None:
    """A membership that is not active is not access.

    The predicate checks ``status = 'active'``; a row existing is not enough.
    """
    now = datetime.now(UTC)
    user_c = uuid.uuid4()
    seed(  # type: ignore[operator]
        'INSERT INTO "user" (id, email, full_name, mfa_enabled, locale, is_active,'
        " created_at, updated_at) VALUES (%s, 'c@example.md', 'C', false, 'ro', true,"
        " %s, %s)",
        [user_c, now, now],
    )
    seed(  # type: ignore[operator]
        "INSERT INTO membership (id, tenant_id, user_id, role_id, status, invited_at,"
        " created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, 'suspended', %s, %s, %s)",
        [uuid.uuid4(), world["tenant_a"], user_c, world["role_owner_a"], now, now, now],
    )
    with tenant_context(as_user(world["tenant_a"], user_c)):
        assert query("SELECT subdomain FROM tenant") == []
