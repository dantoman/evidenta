"""Fixtures for the penetration suite.

Seeding is the interesting part. With ``FORCE ROW LEVEL SECURITY`` even
``evidenta_owner`` is subject to the policies, so test data cannot be inserted by
the migration connection either.

``SET LOCAL ROLE evidenta_rls`` looks like the answer and is not: that role has
BYPASSRLS but no table privileges at all, by design -- 0001_roles.sql grants it
SELECT pointwise, only on the tables the predicates read. It is a resolver, not a
seeder, and trying to seed with it fails with "permission denied", which is the
correct outcome.

So the fixture seeds through the **test admin** connection, the same superuser the
harness uses to create the database. That is not a workaround: creating the first
tenant, its first user and their first membership is inherently privileged -- there
is no context under which a tenant that does not exist yet can be inserted. In
production this is a platform path, not a user action.

Rows are removed at teardown: the seed connection commits, so the test
transaction's rollback does not undo them.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator, Sequence
from datetime import UTC, datetime
from typing import Any

import psycopg
import pytest
from django.conf import settings

from tests.conftest import admin_dsn

# Order matters: children before parents.
SEEDED_TABLES = (
    "fiscal_logic_version",
    "fiscal_parameter",
    "fiscal_parameter_source",
    "company_partner",
    "partner",
    "item",
    "item_category",
    "unit_conversion",
    "unit_of_measure",
    "counterparty_registry",
    "document_event",
    "document",
    "numbering_counter",
    "numbering_template",
    "feature_flag_override",
    "tenant_release_ring",
    "feature_flag",
    "capability_activation",
    "user_session",
    "mfa_backup_code",
    "mfa_method",
    "role_permission",
    "company_access",
    "engagement_module_scope",
    "engagement_company_scope",
    "engagement",
    "firm",
    "membership",
    # After membership and company_access: both point at it now (ADR-020).
    # `permission` is absent on purpose -- it is the catalogue, fed by the
    # migration, and a fixture that deleted it would break every later test.
    "role",
    "company_vat_registration",
    "company",
    "tenant",
    '"user"',
)


#: Roles are per tenant (ADR-020), so a fixture that seeds a membership needs one
#: first. Deriving the id from the tenant keeps it stable across fixtures without
#: reading it back: the seeding connection executes, it does not query.
ROLE_NAMESPACE = uuid.UUID("6f5f1d02-9a1e-5f3a-9c1e-3f0d2b7a4c11")

SYSTEM_ROLE_LEVELS = {"owner": "tenant", "company_admin": "company"}


def role_id(tenant_id: uuid.UUID, key: str) -> uuid.UUID:
    return uuid.uuid5(ROLE_NAMESPACE, f"{tenant_id}:{key}")


def seed_system_roles(seed: Callable[..., None], tenant_id: uuid.UUID) -> None:
    """The two system roles of one tenant. Idempotent, like the service."""
    now = datetime.now(UTC)
    for key, level in SYSTEM_ROLE_LEVELS.items():
        seed(
            "INSERT INTO role (id, tenant_id, key, name, level, is_system,"
            " created_at, updated_at)"
            " VALUES (%s, %s, %s, %s, %s, true, %s, %s)"
            " ON CONFLICT (tenant_id, key) DO NOTHING",
            [role_id(tenant_id, key), tenant_id, key, key, level, now, now],
        )


#: The protections the cleanup has to get past, and put back. Written once so
#: the disable and the re-enable cannot drift apart.
_TRIGGER_STATE = (
    "ALTER TABLE role {action} TRIGGER role_protect_system",
    "ALTER TABLE role_permission {action} TRIGGER role_permission_protect_system",
)


@pytest.fixture
def seed(django_db_setup: None) -> Iterator[Callable[..., None]]:
    """Insert rows through the privileged path, and clean up after.

    Depends on ``django_db_setup`` explicitly. Without it pytest is free to build
    this fixture first, and it would read the database name before the harness has
    pointed settings at the test database -- connecting somewhere real, finding no
    tables, and reporting a confusing "relation does not exist".
    """
    # The harness has already pointed settings at the test database; deriving the
    # name again would compute test_test_evidenta.
    dbname = str(settings.DATABASES["default"]["NAME"])
    with psycopg.connect(admin_dsn(dbname), autocommit=True) as admin:

        def run(sql: str, params: Sequence[Any] | None = None) -> None:
            admin.execute(sql, params or [])

        # Cleaning *before* seeding rather than after. Cleaning afterwards blocks:
        # the test's own transaction still holds row locks when fixture teardown
        # runs, so the DELETE waits on it and the suite hangs with no output. The
        # lock timeout is a second line -- if a previous run left something
        # locked, this fails loudly instead of stalling.
        admin.execute("SET lock_timeout = '5s'")
        # System roles refuse deletion -- that is production behaviour (ADR-020),
        # and the suite proves it in test_roles.py. Cleaning up after a fixture is
        # the one place that has to get past it, so it says so out loud rather
        # than seeding roles as non-system and testing a shape we do not ship.
        # Re-enable before disabling, which looks redundant and is not: a run
        # killed between the two ALTERs below leaves the protection off on a
        # shared test database, and a suite that keeps passing with the trigger
        # disabled proves less every run without saying so. Repairing at the
        # start makes that self-healing; `finally` alone cannot, because nothing
        # runs after SIGKILL. One transaction around the whole block is not an
        # option either -- PostgreSQL refuses ALTER TABLE while the DELETEs have
        # trigger events pending.
        for statement in _TRIGGER_STATE:
            admin.execute(statement.format(action="ENABLE"))
        for statement in _TRIGGER_STATE:
            admin.execute(statement.format(action="DISABLE"))
        try:
            for table in SEEDED_TABLES:
                admin.execute(f"DELETE FROM {table}")
        finally:
            for statement in _TRIGGER_STATE:
                admin.execute(statement.format(action="ENABLE"))
        yield run


@pytest.fixture
def world(seed: Callable[..., None]) -> dict[str, uuid.UUID]:
    """Two tenants, two users, a membership each -- the minimum for IZ-01..IZ-08.

    Deliberately symmetric: whatever tenant A's member can do, tenant B's member
    can do to their own data, and neither can reach the other's. An asymmetric
    fixture hides the direction the bug is actually in.
    """
    now = datetime.now(UTC)
    ids = {
        "tenant_a": uuid.uuid4(),
        "tenant_b": uuid.uuid4(),
        "user_a": uuid.uuid4(),
        "user_b": uuid.uuid4(),
    }

    for key, subdomain, name in (
        ("tenant_a", "alpha", "Alpha SRL"),
        ("tenant_b", "beta", "Beta SRL"),
    ):
        seed(
            "INSERT INTO tenant (id, subdomain, legal_name, status, default_locale,"
            " created_at, updated_at) VALUES (%s, %s, %s, 'active', 'ro', %s, %s)",
            [ids[key], subdomain, name, now, now],
        )

    for key, email in (("user_a", "a@example.md"), ("user_b", "b@example.md")):
        seed(
            'INSERT INTO "user" (id, email, full_name, mfa_enabled, locale,'
            " is_active, created_at, updated_at)"
            " VALUES (%s, %s, %s, false, 'ro', true, %s, %s)",
            [ids[key], email, email, now, now],
        )

    for tenant_key, user_key in (("tenant_a", "user_a"), ("tenant_b", "user_b")):
        seed_system_roles(seed, ids[tenant_key])
        seed(
            "INSERT INTO membership (id, tenant_id, user_id, role_id, status,"
            " invited_at, accepted_at, created_at, updated_at)"
            " VALUES (%s, %s, %s, %s, 'active', %s, %s, %s, %s)",
            [
                uuid.uuid4(),
                ids[tenant_key],
                ids[user_key],
                role_id(ids[tenant_key], "owner"),
                now,
                now,
                now,
                now,
            ],
        )
        ids[f"role_owner_{tenant_key[-1]}"] = role_id(ids[tenant_key], "owner")

    return ids


@pytest.fixture
def firm_world(seed: Callable[..., None], world: dict[str, uuid.UUID]) -> dict[str, uuid.UUID]:
    """Adds an accounting firm holding an engagement over tenant B.

    The firm is itself a tenant -- that is the whole point of the model, and a
    fixture that faked it with a bare row would test a system we did not build.
    """
    now = datetime.now(UTC)
    ids = dict(world)
    ids["firm_tenant"] = uuid.uuid4()
    ids["firm"] = uuid.uuid4()
    ids["user_f"] = uuid.uuid4()

    seed(
        "INSERT INTO tenant (id, subdomain, legal_name, status, default_locale,"
        " created_at, updated_at)"
        " VALUES (%s, 'contaexpert', 'Conta Expert SRL', 'active', 'ro', %s, %s)",
        [ids["firm_tenant"], now, now],
    )
    seed(
        'INSERT INTO "user" (id, email, full_name, mfa_enabled, locale, is_active,'
        " created_at, updated_at)"
        " VALUES (%s, 'f@example.md', 'F', false, 'ro', true, %s, %s)",
        [ids["user_f"], now, now],
    )
    seed_system_roles(seed, ids["firm_tenant"])
    seed(
        "INSERT INTO membership (id, tenant_id, user_id, role_id, status, invited_at,"
        " accepted_at, created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, 'active', %s, %s, %s, %s)",
        [
            uuid.uuid4(),
            ids["firm_tenant"],
            ids["user_f"],
            role_id(ids["firm_tenant"], "owner"),
            now,
            now,
            now,
            now,
        ],
    )
    seed(
        "INSERT INTO firm (id, tenant_id, name, status, created_at, updated_at)"
        " VALUES (%s, %s, 'Conta Expert', 'active', %s, %s)",
        [ids["firm"], ids["firm_tenant"], now, now],
    )
    return ids


@pytest.fixture
def engage(seed: Callable[..., None]) -> Callable[..., uuid.UUID]:
    """Create an engagement with a given status and validity window."""

    def make(
        firm_id: uuid.UUID,
        client_tenant_id: uuid.UUID,
        invited_by: uuid.UUID,
        *,
        status: str = "active",
        valid_from: str = "2020-01-01",
        valid_to: str | None = None,
    ) -> uuid.UUID:
        now = datetime.now(UTC)
        engagement_id = uuid.uuid4()
        accepted = now if status in ("active", "suspended", "revoked") else None
        revoked = now if status == "revoked" else None
        seed(
            "INSERT INTO engagement (id, firm_id, client_tenant_id, status,"
            " covers_all_companies, valid_from, valid_to, initiated_by,"
            " invited_by_user_id, invited_at, accepted_at, revoked_at,"
            " created_at, updated_at)"
            " VALUES (%s, %s, %s, %s, true, %s, %s, 'firm', %s, %s, %s, %s, %s, %s)",
            [
                engagement_id,
                firm_id,
                client_tenant_id,
                status,
                valid_from,
                valid_to,
                invited_by,
                now,
                accepted,
                revoked,
                now,
                now,
            ],
        )
        return engagement_id

    return make


@pytest.fixture
def grant_company(seed: Callable[..., None]) -> Callable[..., uuid.UUID]:
    """Grant one user access to one company."""

    def make(
        tenant_id: uuid.UUID,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        granted_by: uuid.UUID,
        *,
        via: str = "membership",
        engagement_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        now = datetime.now(UTC)
        access_id = uuid.uuid4()
        seed_system_roles(seed, tenant_id)
        seed(
            "INSERT INTO company_access (id, tenant_id, company_id, user_id, role_id,"
            " granted_via, engagement_id, valid_from, granted_by_user_id,"
            " created_at, updated_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, '2020-01-01', %s, %s, %s)",
            [
                access_id,
                tenant_id,
                company_id,
                user_id,
                role_id(tenant_id, "company_admin"),
                via,
                engagement_id,
                granted_by,
                now,
                now,
            ],
        )
        return access_id

    return make


@pytest.fixture
def company_of(seed: Callable[..., None]) -> Callable[..., uuid.UUID]:
    """Create a company under a tenant."""

    def make(tenant_id: uuid.UUID, idno: str, name: str) -> uuid.UUID:
        now = datetime.now(UTC)
        company_id = uuid.uuid4()
        seed(
            "INSERT INTO company (id, tenant_id, idno, legal_name,"
            " functional_currency, fiscal_year_start_month, accounting_start_date,"
            " status, created_at, updated_at)"
            " VALUES (%s, %s, %s, %s, 'MDL', 1, '2026-01-01', 'active', %s, %s)",
            [company_id, tenant_id, idno, name, now, now],
        )
        return company_id

    return make
