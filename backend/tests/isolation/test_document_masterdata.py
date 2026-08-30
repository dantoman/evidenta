"""The nomenclatures the document layer needs, and the two facts they carry.

**VAT registration is state with an effective date, not a flag.** A counterparty
registers and can be struck off during the year, and a document dated before the
strike-off was correct when it was issued. Recalculating that period has to use
the status valid then (`R18`).

**The legal name is what prints; the internal name is what the user types.**
ADR-034 and `C39`. A test that only checked the column exists would miss the
whole point, so the one below checks what reaches a document line.

Everything runs under the application role (`T1`).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest
from django.db import transaction
from django.db.utils import IntegrityError

from evidenta.masterdata.items.models import Item, ItemBarcode, ItemKind, ItemUnit
from evidenta.masterdata.partners.models import Partner, PartnerVatRegistration
from evidenta.masterdata.partners.services.directory import (
    VatRegistrationOverlapError,
    VatValidFromRequiredError,
    create_partner,
    deregister_vat,
    is_vat_registered,
    partners_of,
    register_vat,
    vat_registration_on,
)
from evidenta.masterdata.uom.models import UnitOfMeasure
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="md")


@pytest.fixture
def outsider(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="md-b")


@pytest.fixture
def partner(context: TenantContext, world: dict[str, uuid.UUID]) -> Partner:
    with tenant_context(context):
        return create_partner(
            tenant_id=world["tenant_a"],
            legal_name='Societatea cu Raspundere Limitata "Gama"',
            internal_name="Гамма",
            idno="1003600022222",
            is_supplier=True,
        )


# --- VAT registration --------------------------------------------------------


def test_a_vat_code_without_a_start_date_is_refused(
    context: TenantContext, world: dict[str, uuid.UUID]
) -> None:
    """A start date invented at data-entry time answers "was this counterparty
    registered on the day of the document" with the day somebody typed the card
    -- silently, and wrongly for every document before it."""
    with tenant_context(context), pytest.raises(VatValidFromRequiredError):
        create_partner(
            tenant_id=world["tenant_a"],
            legal_name="Delta SRL",
            idno="1003600033333",
            vat_code="0301234",
            is_customer=True,
        )


def test_the_status_is_resolved_by_date_in_both_directions(
    context: TenantContext, partner: Partner
) -> None:
    with tenant_context(context):
        register_vat(partner.id, vat_code="0301234", valid_from=date(2026, 2, 1))
        deregister_vat(partner.id, last_day=date(2026, 5, 31))

        assert not is_vat_registered(partner.id, date(2026, 1, 31))
        assert is_vat_registered(partner.id, date(2026, 2, 1))
        assert is_vat_registered(partner.id, date(2026, 5, 31))
        # Half-open upper bound: the day after the last day is outside.
        assert not is_vat_registered(partner.id, date(2026, 6, 1))

        found = vat_registration_on(partner.id, date(2026, 3, 1))
        assert found is not None
        assert found.vat_code == "0301234"


def test_a_partner_re_registering_keeps_the_old_code_readable(
    context: TenantContext, partner: Partner
) -> None:
    """A struck-off partner that registers again receives a different code.

    A single column on the partner would have overwritten the old one -- which is
    the code the invoices already issued still carry.
    """
    with tenant_context(context):
        register_vat(partner.id, vat_code="0301234", valid_from=date(2024, 1, 1))
        deregister_vat(partner.id, last_day=date(2024, 12, 31))
        register_vat(partner.id, vat_code="0409999", valid_from=date(2026, 1, 1))

        old = vat_registration_on(partner.id, date(2024, 6, 1))
        new = vat_registration_on(partner.id, date(2026, 6, 1))
    assert old is not None and old.vat_code == "0301234"
    assert new is not None and new.vat_code == "0409999"


def test_two_registrations_cannot_cover_one_day(context: TenantContext, partner: Partner) -> None:
    """Two answers to "was this a VAT payer then" is no answer, and the resolver
    would pick one by accident."""
    with tenant_context(context):
        register_vat(partner.id, vat_code="0301234", valid_from=date(2026, 1, 1))
        with pytest.raises(VatRegistrationOverlapError):
            register_vat(partner.id, vat_code="0409999", valid_from=date(2026, 6, 1))


def test_the_directory_reports_the_open_registration_not_a_dated_one(
    context: TenantContext, partner: Partner
) -> None:
    """ "Open" is a fact about the row, not a resolution against a date.

    The directory can show it without answering a question nobody asked; a screen
    that needs the status on a day calls `vat_registration_on`, which takes the
    day.
    """
    with tenant_context(context):
        register_vat(partner.id, vat_code="0301234", valid_from=date(2026, 1, 1))
        row = next(r for r in partners_of(partner.tenant_id) if r["id"] == str(partner.id))
        assert row["vat_code"] == "0301234"
        assert row["vat_registered"] is True

        deregister_vat(partner.id, last_day=date(2026, 6, 30))
        row = next(r for r in partners_of(partner.tenant_id) if r["id"] == str(partner.id))
        assert row["vat_code"] is None
        assert row["vat_registered"] is False


def test_a_registration_of_another_tenant_is_absent(
    context: TenantContext, outsider: TenantContext, partner: Partner
) -> None:
    with tenant_context(context):
        register_vat(partner.id, vat_code="0301234", valid_from=date(2026, 1, 1))
    with tenant_context(outsider):
        assert PartnerVatRegistration.objects.count() == 0


# --- names -------------------------------------------------------------------


def test_the_internal_name_is_searchable_and_the_legal_one_is_authoritative(
    context: TenantContext, partner: Partner
) -> None:
    """ADR-034. The user works in their own alphabet; the document does not.

    Search covers the internal name because that is what the accountant typed and
    therefore what they will look for. `legal_name` stays the only value a
    document, a register or an export may read (`C39`).
    """
    with tenant_context(context):
        found = partners_of(partner.tenant_id, query="Гамма")
        assert [row["id"] for row in found] == [str(partner.id)]
        assert found[0]["legal_name"].startswith("Societatea")
        assert found[0]["display_name"] == "Гамма"


# --- items -------------------------------------------------------------------


@pytest.fixture
def item(context: TenantContext, world: dict[str, uuid.UUID]) -> Item:
    with tenant_context(context):
        unit = UnitOfMeasure.objects.create(
            tenant_id=world["tenant_a"], code="BUC", name="Bucata", decimal_places=0
        )
        return Item.objects.create(
            tenant_id=world["tenant_a"],
            sku="A-001",
            name="Ciment M400, sac 25 kg",
            internal_name="Цемент 400",
            kind=ItemKind.GOODS,
            base_unit=unit,
            vat_rate_key="vat.rate.standard",
            tariff_code="2523 29 000",
        )


def test_the_five_kinds_include_the_two_the_catalogue_needed(
    context: TenantContext, world: dict[str, uuid.UUID], item: Item
) -> None:
    """Material and OMVSD are kinds an entity here actually keeps.

    What each one resolves to in the ledger is not a property of the catalogue
    and is not decided by this column.
    """
    assert {"material", "low_value_short_lived"} <= set(ItemKind.values)
    with tenant_context(context):
        item.kind = ItemKind.LOW_VALUE_SHORT_LIVED
        item.save(update_fields=["kind"])
        assert Item.objects.get(id=item.id).kind == "low_value_short_lived"


def test_an_alternative_unit_carries_a_ratio_not_a_rounded_factor(
    context: TenantContext, world: dict[str, uuid.UUID], item: Item
) -> None:
    """A box of twelve is exact; a kilogram of a liquid in litres is not.

    Rounding the second into one decimal factor at definition time loses
    precision every later quantity inherits.
    """
    with tenant_context(context):
        box = UnitOfMeasure.objects.create(
            tenant_id=world["tenant_a"], code="CUT", name="Cutie", decimal_places=0
        )
        ItemUnit.objects.create(
            tenant_id=world["tenant_a"],
            item=item,
            unit=box,
            numerator=Decimal(12),
            denominator=Decimal(1),
        )
        with (
            pytest.raises(IntegrityError, match="item_unit_positive"),
            transaction.atomic(),
        ):
            ItemUnit.objects.create(
                tenant_id=world["tenant_a"],
                item=item,
                unit=box,
                numerator=Decimal(0),
                denominator=Decimal(1),
            )


def test_a_barcode_identifies_one_item_in_the_tenant(
    context: TenantContext, world: dict[str, uuid.UUID], item: Item
) -> None:
    """The whole purpose of a barcode is that scanning it identifies one thing.

    A code resolving to two items would be found by whoever scanned it into a
    document, which is the worst place to find it.
    """
    with tenant_context(context):
        ItemBarcode.objects.create(tenant_id=world["tenant_a"], item=item, barcode="4820000000017")
        other = Item.objects.create(
            tenant_id=world["tenant_a"],
            sku="A-002",
            name="Var hidratat, sac 20 kg",
            kind=ItemKind.MATERIAL,
            base_unit=item.base_unit,
        )
        with (
            pytest.raises(IntegrityError, match="item_barcode_unique"),
            transaction.atomic(),
        ):
            ItemBarcode.objects.create(
                tenant_id=world["tenant_a"], item=other, barcode="4820000000017"
            )


def test_the_catalogue_of_another_tenant_is_absent(
    context: TenantContext,
    outsider: TenantContext,
    world: dict[str, uuid.UUID],
    item: Item,
) -> None:
    with tenant_context(context):
        ItemBarcode.objects.create(tenant_id=world["tenant_a"], item=item, barcode="4820000000024")
    with tenant_context(outsider):
        assert ItemBarcode.objects.count() == 0
        assert ItemUnit.objects.count() == 0


# --- the rate comes from the nomenclature, or nothing happens ----------------


def test_a_catalogue_line_refuses_when_no_rate_is_registered(
    context: TenantContext, item: Item
) -> None:
    """No rate is in this repository, and none is invented here.

    `R15` makes rates data with provenance; loading them is `OD-22`, open. Until
    a rate exists, building a line from the catalogue **refuses** -- which is the
    correct behaviour and not a gap: a missing rate is not a rate of zero, and a
    document produced with an invented one is wrong in a way nobody notices until
    an inspection.
    """
    from evidenta.fiscal.parameters.services.resolution import FiscalResolutionError
    from evidenta.operations.sales.services.lines import line_from_catalogue

    with tenant_context(context), pytest.raises(FiscalResolutionError) as caught:
        line_from_catalogue(
            item.id,
            on=date(2026, 3, 1),
            quantity=Decimal(1),
            unit_price=Decimal("100.00"),
            net_amount=Decimal("100.0000"),
            vat_amount=Decimal("20.0000"),
            total_amount=Decimal("120.0000"),
            vat_regime_code="standard",
        )
    assert caught.value.code == "fiscal.no_parameter"


def test_a_catalogue_line_takes_the_legal_name_and_the_rate_of_the_day(
    context: TenantContext, seed: Callable[..., None], world: dict[str, uuid.UUID], item: Item
) -> None:
    """ADR-034 and `R17` in one line of a document.

    The **legal** name prints, never the internal one -- even though the internal
    one exists here and differs, which is the case the rule is about. The rate is
    resolved by the date of the document, so re-entering a March document in June
    reaches March's rate (ADR-044).
    """
    from evidenta.operations.sales.services.lines import line_from_catalogue

    source_id = uuid.uuid4()
    seed(
        "INSERT INTO fiscal_parameter_source (id, act_type, act_number, act_date,"
        " official_gazette_number, official_gazette_article, published_at,"
        " effective_from, created_at)"
        " VALUES (%s, 'test', 'TEST-1/0000', DATE '2000-01-01', 'TEST 1', 'art. 1',"
        " DATE '2000-01-01', DATE '2000-01-01', now())",
        [source_id],
    )
    for value, valid_from, valid_to in (
        ("20", "2020-01-01", "2026-02-01"),
        ("18", "2026-02-01", None),
    ):
        seed(
            # `OD-92`: a VAT rate's margin comes from an act's final article. The
            # fixture cites the synthetic source it seeded rather than leaving the
            # margin unsourced, which the constraint would refuse.
            "INSERT INTO fiscal_parameter (id, parameter_key, scope, value_type, value,"
            " valid_from, margin_basis, margin_reference, valid_to, source_id, status,"
            " approved_by_user_id, approved_at, source_confidence, created_at, updated_at)"
            " VALUES (%s, 'vat.rate.standard', 'global', 'percentage', %s::jsonb, %s,"
            " 'platform_convention', 'fixture — act sintetic, fără MO', %s,"
            " %s, 'active', %s, now(), 'confirmed', now(), now())",
            [uuid.uuid4(), value, valid_from, valid_to, source_id, world["user_a"]],
        )

    with tenant_context(context):
        old = line_from_catalogue(
            item.id,
            on=date(2026, 1, 15),
            quantity=Decimal(1),
            unit_price=Decimal("100.00"),
            net_amount=Decimal("100.0000"),
            vat_amount=Decimal("20.0000"),
            total_amount=Decimal("120.0000"),
            vat_regime_code="standard",
        )
        current = line_from_catalogue(
            item.id,
            on=date(2026, 3, 1),
            quantity=Decimal(1),
            unit_price=Decimal("100.00"),
            net_amount=Decimal("100.0000"),
            vat_amount=Decimal("18.0000"),
            total_amount=Decimal("118.0000"),
            vat_regime_code="standard",
        )

    assert old.vat_rate == Decimal("20")
    assert current.vat_rate == Decimal("18")
    assert old.description == "Ciment M400, sac 25 kg"
    assert item.internal_name is not None and item.internal_name != old.description
    assert old.vat_rate_key == "vat.rate.standard"
