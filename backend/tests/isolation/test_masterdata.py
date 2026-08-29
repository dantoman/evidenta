"""Master data -- the three-level partner model, units and items.

The level split is what these tests are about. Amendment C.1 puts a public
register under a tenant master record under a per-company configuration, and each
boundary exists to stop a specific failure.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from django.db import transaction
from django.db.utils import IntegrityError

from evidenta.masterdata.counterparties.models import (
    CounterpartyRegistry,
    CounterpartyStatus,
)
from evidenta.masterdata.items.models import Item, ItemKind
from evidenta.masterdata.partners.models import CompanyPartner, Partner
from evidenta.masterdata.uom.models import UnitConversion, UnitOfMeasure
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="md")


@pytest.fixture
def company(
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> uuid.UUID:
    company_id = company_of(world["tenant_a"], "1002600000001", "Alpha Trading")
    grant_company(world["tenant_a"], company_id, world["user_a"], world["user_a"])
    return company_id


def make_partner(world: dict[str, uuid.UUID], **kwargs: object) -> Partner:
    defaults: dict[str, object] = {
        "tenant_id": world["tenant_a"],
        "idno": "1003600000001",
        "legal_name": "METRO Moldova SRL",
        "is_supplier": True,
    }
    defaults.update(kwargs)
    return Partner.objects.create(**defaults)


def test_the_registry_is_readable_by_every_tenant(
    context: TenantContext, world: dict[str, uuid.UUID], seed: Callable[..., None]
) -> None:
    """Global reference data: what the state says, not what a tenant entered."""
    seed(
        "INSERT INTO counterparty_registry (id, idno, legal_name, vat_registered,"
        " status, source, fetched_at, created_at, updated_at)"
        " VALUES (%s, '1003600000001', 'METRO Moldova SRL', true, 'active',"
        " 'test', now(), now(), now())",
        [uuid.uuid4()],
    )
    for tenant_key, user_key in (("tenant_a", "user_a"), ("tenant_b", "user_b")):
        ctx = TenantContext(tenant_id=world[tenant_key], user_id=world[user_key], request_id="md")
        with tenant_context(ctx):
            assert CounterpartyRegistry.objects.count() == 1


def test_a_tenant_cannot_write_to_the_registry(
    context: TenantContext, world: dict[str, uuid.UUID]
) -> None:
    """A tenant that could write here would change what the state says about a
    counterparty, for everyone else. Writing goes through the privileged path.

    Refused at both layers, and the distinction cost a bug to find: the policy
    alone was doing the work, because 0001_roles.sql grants write privileges by
    default on every table the owner creates. An absent INSERT policy is an
    omission that behaves like a prohibition until someone adds a policy for an
    unrelated reason. The privilege is now withdrawn explicitly.
    """
    with (
        tenant_context(context),
        pytest.raises(Exception, match="permission denied"),
        transaction.atomic(),
    ):
        CounterpartyRegistry.objects.create(
            idno="9999999999999",
            legal_name="Inventat SRL",
            status=CounterpartyStatus.ACTIVE,
            source="forged",
            fetched_at=datetime.now(UTC),
        )


def test_a_partner_is_entered_once_per_tenant(
    context: TenantContext, world: dict[str, uuid.UUID]
) -> None:
    """In a holding, METRO Moldova is entered once, not once per company.

    Without the constraint the same supplier appears twice and the balances split
    between them -- which surfaces as a reconciliation that will not close.
    """
    with tenant_context(context):
        make_partner(world)
        with pytest.raises(IntegrityError, match="partner_idno_unique"), transaction.atomic():
            make_partner(world, legal_name="METRO Moldova (duplicat)")


def test_a_partner_needs_a_role(context: TenantContext, world: dict[str, uuid.UUID]) -> None:
    """Neither customer nor supplier is a record nothing can be posted against."""
    with (
        tenant_context(context),
        pytest.raises(IntegrityError, match="partner_has_a_role"),
        transaction.atomic(),
    ):
        make_partner(world, is_customer=False, is_supplier=False)


def test_partners_are_shared_between_companies_of_a_tenant(
    context: TenantContext, world: dict[str, uuid.UUID], company: uuid.UUID
) -> None:
    """The point of the tenant level: one master record, many companies."""
    with tenant_context(context):
        partner = make_partner(world)
        CompanyPartner.objects.create(
            tenant_id=world["tenant_a"],
            company_id=company,
            partner=partner,
            receivable_account_code="221",
            payment_terms_days=30,
        )
        assert Partner.objects.count() == 1


def test_a_partner_is_configured_once_per_company(
    context: TenantContext, world: dict[str, uuid.UUID], company: uuid.UUID
) -> None:
    with tenant_context(context):
        partner = make_partner(world)
        CompanyPartner.objects.create(
            tenant_id=world["tenant_a"], company_id=company, partner=partner
        )
        with (
            pytest.raises(IntegrityError, match="company_partner_unique"),
            transaction.atomic(),
        ):
            CompanyPartner.objects.create(
                tenant_id=world["tenant_a"], company_id=company, partner=partner
            )


def test_a_block_carries_its_reason(
    context: TenantContext, world: dict[str, uuid.UUID], company: uuid.UUID
) -> None:
    """A block nobody can explain is a block nobody can safely lift."""
    with tenant_context(context):
        partner = make_partner(world)
        with (
            pytest.raises(IntegrityError, match="company_partner_block_has_reason"),
            transaction.atomic(),
        ):
            CompanyPartner.objects.create(
                tenant_id=world["tenant_a"],
                company_id=company,
                partner=partner,
                is_blocked=True,
            )


def test_partners_do_not_cross_tenants(context: TenantContext, world: dict[str, uuid.UUID]) -> None:
    with tenant_context(context):
        make_partner(world)

    other = TenantContext(tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="md")
    with tenant_context(other):
        assert Partner.objects.count() == 0


def test_a_unit_cannot_convert_to_itself(
    context: TenantContext, world: dict[str, uuid.UUID]
) -> None:
    """Either a no-op or a mistake, and the mistake is the conversion loop."""
    with tenant_context(context):
        piece = UnitOfMeasure.objects.create(
            tenant_id=world["tenant_a"], code="BUC", name="Bucată", decimal_places=0
        )
        with (
            pytest.raises(IntegrityError, match="unit_conversion_not_self"),
            transaction.atomic(),
        ):
            UnitConversion.objects.create(
                tenant_id=world["tenant_a"],
                from_unit=piece,
                to_unit=piece,
                numerator=Decimal(1),
                denominator=Decimal(1),
            )


def test_a_conversion_is_a_ratio_not_a_factor(
    context: TenantContext, world: dict[str, uuid.UUID]
) -> None:
    """A box of 12 is exact; a kilogram in litres is not.

    Rounding the second into a single decimal factor at definition time loses
    precision that every later quantity inherits.
    """
    with tenant_context(context):
        piece = UnitOfMeasure.objects.create(
            tenant_id=world["tenant_a"], code="BUC", name="Bucată", decimal_places=0
        )
        box = UnitOfMeasure.objects.create(
            tenant_id=world["tenant_a"], code="CUT", name="Cutie", decimal_places=0
        )
        conversion = UnitConversion.objects.create(
            tenant_id=world["tenant_a"],
            from_unit=box,
            to_unit=piece,
            numerator=Decimal(12),
            denominator=Decimal(1),
        )
        assert conversion.numerator / conversion.denominator == Decimal(12)


def test_a_service_tracks_neither_lots_nor_serials(
    context: TenantContext, world: dict[str, uuid.UUID]
) -> None:
    """A service has no stock, so the setting could never be honoured."""
    with tenant_context(context):
        unit = UnitOfMeasure.objects.create(
            tenant_id=world["tenant_a"], code="ORA", name="Oră", decimal_places=2
        )
        with (
            pytest.raises(IntegrityError, match="item_service_tracks_nothing"),
            transaction.atomic(),
        ):
            Item.objects.create(
                tenant_id=world["tenant_a"],
                sku="CONS-01",
                name="Consultanță",
                kind=ItemKind.SERVICE,
                base_unit=unit,
                tracks_lots=True,
            )


def test_lot_and_serial_flags_exist_before_the_module_does(
    context: TenantContext, world: dict[str, uuid.UUID]
) -> None:
    """Modelled at F0, handled at F4.

    Changing these on an item that already has movements is not a settings
    change, it is a restatement of stock -- which is why they are here from the
    start rather than added when lots arrive.
    """
    with tenant_context(context):
        unit = UnitOfMeasure.objects.create(
            tenant_id=world["tenant_a"], code="BUC", name="Bucată", decimal_places=0
        )
        item = Item.objects.create(
            tenant_id=world["tenant_a"],
            sku="MARF-01",
            name="Marfă",
            kind=ItemKind.GOODS,
            base_unit=unit,
            tracks_lots=True,
            tracks_serials=True,
        )
        assert item.tracks_lots and item.tracks_serials
