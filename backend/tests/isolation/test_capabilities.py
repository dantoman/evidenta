"""Capabilities and feature flags -- R23, R24, R25, and Spec A 1.8 / 10.5.

Three claims, each of which fails silently if it is only a convention: an
activation is an entity, compliance cannot be switched off, and a flag override
cannot become a per-tenant version of the product.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import pytest
from django.db import connection, transaction
from django.db.utils import IntegrityError

from evidenta.platform.capabilities.models import (
    ActivationSource,
    CapabilityActivation,
    InitialisationState,
)
from evidenta.platform.flags.models import FeatureFlagOverride
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="cap")


def activate(
    world: dict[str, uuid.UUID],
    key: str,
    *,
    company_id: uuid.UUID | None = None,
    start: date = date(2026, 1, 1),
    end: date | None = None,
) -> CapabilityActivation:
    return CapabilityActivation.objects.create(
        tenant_id=world["tenant_a"],
        company_id=company_id,
        capability_key=key,
        effective_from=start,
        effective_to=end,
        initialisation_state=InitialisationState.NOT_REQUIRED,
        activated_by_id=world["user_a"],
        activated_at=datetime.now(UTC),
        source=ActivationSource.MANUAL,
    )


def test_an_activation_carries_a_date_and_a_state(
    context: TenantContext, world: dict[str, uuid.UUID]
) -> None:
    """R25. A boolean cannot express "active from March, opening balances pending"."""
    with tenant_context(context):
        activation = activate(world, "inventory")
        activation.initialisation_state = InitialisationState.REQUIRED
        activation.save(update_fields=["initialisation_state"])
        assert activation.effective_from == date(2026, 1, 1)


def test_overlapping_activations_are_refused(
    context: TenantContext, world: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        activate(world, "inventory", start=date(2026, 1, 1))
        with (
            pytest.raises(IntegrityError, match="capability_activation_no_overlap"),
            transaction.atomic(),
        ):
            activate(world, "inventory", start=date(2026, 6, 1))


def test_tenant_level_activations_do_not_escape_the_constraint(
    context: TenantContext, world: dict[str, uuid.UUID]
) -> None:
    """The case the obvious constraint gets wrong.

    With ``EXCLUDE`` on a nullable ``company_id``, two tenant-level rows never
    conflict -- NULL is not equal to NULL -- so duplicates pass in silence. The
    key is COALESCE(company_id, tenant_id) precisely so this test can fail.
    """
    with tenant_context(context):
        activate(world, "multi_company", company_id=None, start=date(2026, 1, 1))
        with (
            pytest.raises(IntegrityError, match="capability_activation_no_overlap"),
            transaction.atomic(),
        ):
            activate(world, "multi_company", company_id=None, start=date(2026, 3, 1))


def test_adjacent_periods_are_allowed(context: TenantContext, world: dict[str, uuid.UUID]) -> None:
    """Half-open ranges: one ends where the next begins, with no gap and no clash."""
    with tenant_context(context):
        activate(world, "payroll", start=date(2026, 1, 1), end=date(2026, 7, 1))
        activate(world, "payroll", start=date(2026, 7, 1))


@pytest.mark.parametrize("key", ["vat", "efactura", "statutory_reporting"])
def test_compliance_capabilities_cannot_be_switched_off(
    context: TenantContext, world: dict[str, uuid.UUID], key: str
) -> None:
    """R24, in the database.

    If a client issues invoices in Evidenta, e-Factura works whatever they pay.
    Otherwise the product takes on responsibility for clients who fail their
    obligations while using it.
    """
    with (
        tenant_context(context),
        pytest.raises(IntegrityError, match="compliance_never_ends"),
        transaction.atomic(),
    ):
        activate(world, key, end=date(2026, 12, 31))


def test_a_non_compliance_capability_may_end(
    context: TenantContext, world: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        assert activate(world, "inventory", end=date(2026, 12, 31)).effective_to


def test_capabilities_are_scoped_to_the_tenant(
    context: TenantContext, world: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        activate(world, "inventory")

    other = TenantContext(tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="cap")
    with tenant_context(other):
        assert CapabilityActivation.objects.count() == 0


def test_an_override_needs_a_reason_and_an_expiry(
    context: TenantContext, world: dict[str, uuid.UUID], seed: Callable[..., None]
) -> None:
    """An override with no expiry is a per-tenant version of the product.

    One with no reason is one nobody can safely remove, because nobody remembers
    why it is there. Both columns are NOT NULL, which is the whole design.

    Asserted in SQL rather than through the ORM: the claim is about the database,
    and expressing it through a model would mean passing None to a field typed
    as non-null -- a lie to the type checker to test something it is not about.
    """
    seed(
        "INSERT INTO feature_flag (key, description, default_state, is_compliance,"
        " created_at) VALUES ('new_grid', 'test', false, false, now())"
    )
    for column in ("reason", "expires_at"):
        values = {"reason": "'test'", "expires_at": "now() + interval '30 days'"}
        values[column] = "NULL"
        with (
            tenant_context(context),
            pytest.raises(IntegrityError, match="null value"),
            transaction.atomic(),
            connection.cursor() as cursor,
        ):
            cursor.execute(
                "INSERT INTO feature_flag_override (id, tenant_id, flag_key, state,"
                " reason, expires_at, created_at, created_by_user_id)"
                f" VALUES (%s, %s, 'new_grid', true, {values['reason']},"
                f" {values['expires_at']}, now(), %s)",
                [uuid.uuid4(), world["tenant_a"], world["user_a"]],
            )


def test_a_compliance_flag_cannot_be_overridden(
    context: TenantContext, world: dict[str, uuid.UUID], seed: Callable[..., None]
) -> None:
    """R24 again, from the other side.

    An override on a compliance flag would deliver a change in the law to some
    tenants and not others. Enforced by a trigger, because the condition lives in
    another table and a CHECK cannot see it -- and a service-level check would be
    bypassed by the first direct write.
    """
    seed(
        "INSERT INTO feature_flag (key, description, default_state, is_compliance,"
        " created_at) VALUES ('vat_2027_rates', 'test', false, true, now())"
    )
    with (
        tenant_context(context),
        # The trigger raises with ERRCODE 23514, which Django maps to
        # IntegrityError -- the same class as a CHECK, which is what it is.
        pytest.raises(IntegrityError, match="flag de conformitate"),
        transaction.atomic(),
    ):
        FeatureFlagOverride.objects.create(
            tenant_id=world["tenant_a"],
            flag_id="vat_2027_rates",
            state=False,
            reason="clientul nu vrea",
            expires_at=datetime.now(UTC) + timedelta(days=30),
            created_by_id=world["user_a"],
        )


def test_a_normal_flag_can_be_overridden(
    context: TenantContext, world: dict[str, uuid.UUID], seed: Callable[..., None]
) -> None:
    seed(
        "INSERT INTO feature_flag (key, description, default_state, is_compliance,"
        " created_at) VALUES ('new_grid', 'test', false, false, now())"
    )
    with tenant_context(context):
        override = FeatureFlagOverride.objects.create(
            tenant_id=world["tenant_a"],
            flag_id="new_grid",
            state=True,
            reason="pilot cu clientul",
            expires_at=datetime.now(UTC) + timedelta(days=30),
            created_by_id=world["user_a"],
        )
        assert override.state is True
