"""The harness proving itself.

If these fail, nothing else in the suite means anything: every isolation test
below rests on the claim that it runs as the application role against a database
built the way production is built.
"""

from __future__ import annotations

import pytest
from django.db import connections

from evidenta.platform.rls.context import unguarded

pytestmark = pytest.mark.django_db(databases=["default", "migration"])


def test_runs_as_the_application_role() -> None:
    with unguarded("harness self-test"), connections["default"].cursor() as cursor:
        cursor.execute("SELECT current_user")
        assert cursor.fetchone()[0] == "evidenta_app"


def test_application_role_cannot_bypass_rls() -> None:
    with unguarded("harness self-test"), connections["default"].cursor() as cursor:
        cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        is_super, bypasses = cursor.fetchone()
    assert not is_super
    assert not bypasses


def test_migration_connection_is_the_owner() -> None:
    with connections["migration"].cursor() as cursor:
        cursor.execute("SELECT current_user")
        assert cursor.fetchone()[0] == "evidenta_owner"


def test_bootstrap_was_applied() -> None:
    """The context functions and the resolver role exist in the test database."""
    with unguarded("harness self-test"), connections["migration"].cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = 'app' AND p.proname = 'current_tenant_id'"
        )
        assert cursor.fetchone()[0] == 1
        cursor.execute("SELECT rolbypassrls FROM pg_roles WHERE rolname = 'evidenta_rls'")
        assert cursor.fetchone()[0] is True


def test_database_collation_matches_production() -> None:
    """ADR-015: a suite that sorted differently from production would hide bugs."""
    with unguarded("harness self-test"), connections["migration"].cursor() as cursor:
        cursor.execute(
            "SELECT datlocprovider, datlocale FROM pg_database WHERE datname = current_database()"
        )
        provider, locale = cursor.fetchone()
    assert provider == "i"
    assert locale == "ro"
