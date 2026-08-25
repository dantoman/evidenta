"""No path to the database without tenant context.

These assert the *absence* of a path, not the presence of one. A test that sets
the context, queries, and checks the result shows that things work *with*
context; it says nothing about what happens without. Every test here expects a
refusal -- if this file ever contains no failing expectation, it has stopped
testing isolation.

Migrated from tests/isolation/manual_context_probe.py, which is deleted in the
same change.
"""

from __future__ import annotations

import io
import uuid

import pytest
from django.core.management import call_command
from django.db import connection, connections, transaction

from evidenta.platform.rls.context import (
    MissingTenantContextError,
    TenantContext,
    tenant_context,
    unguarded,
)
from evidenta.platform.rls.middleware import TenantResolutionError, refuse_all

pytestmark = pytest.mark.django_db(databases=["default", "migration"])


@pytest.fixture
def context() -> TenantContext:
    return TenantContext(tenant_id=uuid.uuid4(), user_id=uuid.uuid4(), request_id="test")


def test_query_without_context_is_refused() -> None:
    with pytest.raises(MissingTenantContextError), connection.cursor() as cursor:
        cursor.execute("SELECT 1")


def test_a_transaction_alone_is_not_enough() -> None:
    """Opening a transaction without setting context proves nothing."""
    with (
        pytest.raises(MissingTenantContextError),
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute("SELECT 1")


def test_inside_context_the_database_sees_the_same_tenant(context: TenantContext) -> None:
    with tenant_context(context), connection.cursor() as cursor:
        cursor.execute("SELECT app.current_tenant_id()")
        assert cursor.fetchone()[0] == context.tenant_id


def test_context_does_not_outlive_its_block(context: TenantContext) -> None:
    with tenant_context(context), connection.cursor() as cursor:
        cursor.execute("SELECT 1")

    with pytest.raises(MissingTenantContextError), connection.cursor() as cursor:
        cursor.execute("SELECT 1")


def test_unguarded_requires_a_reason() -> None:
    with pytest.raises(ValueError), unguarded(""):
        pass


def test_unguarded_allows_the_query() -> None:
    with unguarded("test: deliberate escape hatch"), connection.cursor() as cursor:
        cursor.execute("SELECT 1")


def test_migration_connection_is_not_guarded() -> None:
    """Guarding it would only break `migrate`; it never serves a request."""
    with connections["migration"].cursor() as cursor:
        cursor.execute("SELECT current_user")
        assert cursor.fetchone()[0] == "evidenta_owner"


def test_management_command_path_is_guarded() -> None:
    """A management command is an entry point the middleware does not cover.

    The guard is installed from AppConfig.ready(), so it covers every entry
    point -- request, task, command, shell -- rather than each of them
    remembering to.
    """
    with pytest.raises(MissingTenantContextError):
        call_command("inspectdb", stdout=io.StringIO())


def test_default_resolver_refuses() -> None:
    """Fail-closed until subdomain resolution exists (F0.3.5)."""
    with pytest.raises(TenantResolutionError):
        refuse_all(None)  # type: ignore[arg-type]
