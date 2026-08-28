"""The document layer: structure, lifecycle, and the freeze.

Everything here runs **under the application role** (`T1`). A test that ran as
owner would pass whatever the policies said, and the freeze it checks is a
trigger -- which the owner is subject to only because of `FORCE ROW LEVEL
SECURITY` on the table it protects.

The tests are grouped by the claim they defend, not by the function they call:

* a draft is free, and holds no number
* validation allocates the number and freezes the document -- **in the database**
* cancellation needs a reason and keeps the number
* a storno copies the positions with the sign inverted, once
* a conversion follows the route the type declares, once
* none of it crosses a tenant
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from django.db import transaction
from django.db.utils import IntegrityError

from evidenta.masterdata.partners.models import Partner
from evidenta.operations.purchases.models import PurchaseDocument
from evidenta.operations.purchases.services.documents import (
    SupplierDocumentAlreadyRecordedError,
    open_purchase,
    open_supplier_order,
)
from evidenta.operations.purchases.types import PURCHASE_DOCUMENT
from evidenta.operations.sales.models import SaleNature, SalesDocument
from evidenta.operations.sales.services.documents import (
    convert_to_sale,
    open_customer_order,
    open_proforma,
    open_sale,
)
from evidenta.operations.sales.types import PROFORMA, SALES_DOCUMENT
from evidenta.platform.documents.errors import (
    AlreadyConvertedError,
    AlreadyReversedError,
    CancellationReasonRequiredError,
    DocumentNotEditableError,
    LineAmountsInconsistentError,
    NoLinesError,
    PartnerRequiredError,
    SourceNotConvertibleError,
    SourceNotValidatedError,
)
from evidenta.platform.documents.models import (
    Document,
    DocumentLine,
    DocumentState,
    ReversalDocument,
)
from evidenta.platform.documents.registry import UnknownDocumentTypeError, spec_for
from evidenta.platform.documents.services.history import history_of
from evidenta.platform.documents.services.lifecycle import (
    cancel,
    delete_draft,
    get_document,
    open_draft,
    validate,
)
from evidenta.platform.documents.services.lines import LineInput, replace_lines, totals_of
from evidenta.platform.documents.services.reversal import REVERSAL_TYPE, create_reversal
from evidenta.platform.numbering.regimes import NumberingRegime
from evidenta.platform.numbering.services.templates import create_general_template, create_series
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

#: One ordinary date. Written once so a test about the lifecycle is not also a
#: test about which period something falls in.
ON = date(2026, 3, 10)


@pytest.fixture
def company(
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> uuid.UUID:
    company_id = company_of(world["tenant_a"], "1002600000001", "Alpha Trading")
    grant_company(world["tenant_a"], company_id, world["user_a"], world["user_a"])
    return company_id


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="docs")


@pytest.fixture
def series(context: TenantContext, world: dict[str, uuid.UUID], company: uuid.UUID) -> None:
    """The company's general series, as `provision_company` would have created it."""
    with tenant_context(context):
        create_general_template(
            world["tenant_a"], company, valid_from=date(2020, 1, 1), separator="-"
        )


@pytest.fixture
def partner(context: TenantContext, world: dict[str, uuid.UUID]) -> uuid.UUID:
    with tenant_context(context):
        return Partner.objects.create(
            tenant_id=world["tenant_a"],
            legal_name='Societatea cu Raspundere Limitata "Beta"',
            internal_name="Бета",
            idno="1003600011111",
            is_customer=True,
            is_supplier=True,
        ).id


def line(net: str = "100.0000", vat: str = "20.0000", quantity: str = "1") -> LineInput:
    """One ordinary position, with the amounts already computed by the caller.

    They are inputs rather than results, and that is the design: the single
    rounding step that would produce them is versioned fiscal logic and is still
    open (`DNB-08`, ADR-037). See `documents.services.lines`.
    """
    return LineInput(
        description="Servicii de consultanta",
        quantity=Decimal(quantity),
        unit_price=Decimal(net),
        vat_regime_code="standard",
        vat_rate=Decimal("20.0000"),
        net_amount=Decimal(net),
        vat_amount=Decimal(vat),
        total_amount=Decimal(net) + Decimal(vat),
    )


def a_sale(company: uuid.UUID, partner_id: uuid.UUID, **kwargs: Any) -> Document:
    """One sale with one position, still a draft, returned as the row.

    The services take and return **identifiers** -- that is the module seam, and
    the reason a module above the document core never has to import its models
    (`D6`). Reading the row back is the test's business, not the caller's.
    """
    document_id = open_sale(company_id=company, partner_id=partner_id, document_date=ON, **kwargs)
    replace_lines(document_id, [line()])
    return get_document(document_id)


# --- a draft is free ---------------------------------------------------------


def test_a_draft_holds_no_number_and_is_deleted_without_trace_but_the_audit(
    context: TenantContext, company: uuid.UUID, partner: uuid.UUID, series: None
) -> None:
    """A draft made no commitment, so there is nothing to account for afterwards.

    Which is exactly why anything past draft is cancelled instead: the number is
    already out.
    """
    with tenant_context(context):
        document = a_sale(company, partner)
        assert document.number is None
        assert document.state == DocumentState.DRAFT

        delete_draft(document.id)
        assert not Document.objects.filter(id=document.id).exists()


def test_an_unregistered_type_cannot_be_created(
    context: TenantContext, company: uuid.UUID, series: None
) -> None:
    """A type nobody declared carries validation rules nobody chose.

    The failure would otherwise surface wherever the missing declaration was
    first needed, which is never where it was introduced.
    """
    with tenant_context(context), pytest.raises(UnknownDocumentTypeError):
        open_draft(company_id=company, document_type="sales.invented", document_date=ON)


def test_the_second_date_defaults_to_the_first_and_is_not_the_same_column(
    context: TenantContext, company: uuid.UUID, partner: uuid.UUID, series: None
) -> None:
    """A delivery on the 28th recorded on the 5th has two answers to "when".

    The default exists so an ordinary document needs one date; the column exists
    so an extraordinary one can say both.
    """
    with tenant_context(context):
        ordinary = a_sale(company, partner)
        assert ordinary.accounting_date == ordinary.document_date

        late = get_document(
            open_sale(
                company_id=company,
                partner_id=partner,
                document_date=date(2026, 2, 28),
                accounting_date=date(2026, 3, 5),
            )
        )
        assert late.document_date != late.accounting_date


# --- validation --------------------------------------------------------------


def test_validation_allocates_the_number_and_records_who(
    context: TenantContext,
    world: dict[str, uuid.UUID],
    company: uuid.UUID,
    partner: uuid.UUID,
    series: None,
) -> None:
    with tenant_context(context):
        document = a_sale(company, partner)
        document = validate(document.id)

    assert document.state == DocumentState.CONFIRMED
    assert document.number == 1
    assert document.formatted_number == "2026-000001"
    assert document.fiscal_year == 2026
    assert document.confirmed_by_id == world["user_a"]
    assert document.confirmed_at is not None


def test_a_document_without_a_counterparty_is_not_validated(
    context: TenantContext, company: uuid.UUID, series: None
) -> None:
    with tenant_context(context):
        document = open_draft(company_id=company, document_type=SALES_DOCUMENT, document_date=ON)
        replace_lines(document.id, [line()])
        with pytest.raises(PartnerRequiredError):
            validate(document.id)


def test_a_document_without_positions_is_not_validated(
    context: TenantContext, company: uuid.UUID, partner: uuid.UUID, series: None
) -> None:
    with tenant_context(context):
        document = get_document(open_sale(company_id=company, partner_id=partner, document_date=ON))
        with pytest.raises(NoLinesError):
            validate(document.id)


def test_an_order_may_be_validated_empty_and_an_invoice_may_not(
    context: TenantContext, company: uuid.UUID, partner: uuid.UUID, series: None
) -> None:
    """The difference is declared by the type, not decided by the function.

    An order is a commitment to buy something that is not fully specified yet;
    an invoice with no positions has no content.
    """
    assert spec_for(SALES_DOCUMENT).requires_lines
    with tenant_context(context):
        order = get_document(
            open_customer_order(company_id=company, partner_id=partner, document_date=ON)
        )
        order = validate(order.id)
    assert order.state == DocumentState.CONFIRMED


# --- the freeze, in the database ---------------------------------------------


def test_a_validated_document_cannot_be_edited_even_through_the_orm(
    context: TenantContext, company: uuid.UUID, partner: uuid.UUID, series: None
) -> None:
    """The requirement is "at model level, not by convention in views".

    A service is not model level: a bulk import, a data migration and a psql
    session all bypass every service ever written, and that is exactly where a
    document already issued gets quietly edited. So this test does not call the
    service -- it writes through the ORM, which is the nearest thing to those
    paths the suite can reach.
    """
    with tenant_context(context):
        document = a_sale(company, partner)
        document = validate(document.id)

        document.document_date = date(2026, 4, 1)
        with pytest.raises(IntegrityError, match="frozen"), transaction.atomic():
            document.save(update_fields=["document_date"])


def test_a_validated_document_cannot_return_to_draft(
    context: TenantContext, company: uuid.UUID, partner: uuid.UUID, series: None
) -> None:
    """Un-validating either releases a number or burns one silently.

    A register may do neither, so the move is absent from the state machine and
    refused by the trigger as well -- because the state machine is a service and
    the trigger is not.
    """
    with tenant_context(context):
        document = a_sale(company, partner)
        document = validate(document.id)

        document.state = DocumentState.DRAFT
        with pytest.raises(IntegrityError, match="draft"), transaction.atomic():
            document.save(update_fields=["state"])


def test_a_validated_document_is_not_deleted(
    context: TenantContext, company: uuid.UUID, partner: uuid.UUID, series: None
) -> None:
    with tenant_context(context):
        document = a_sale(company, partner)
        document = validate(document.id)

        with pytest.raises(DocumentNotEditableError):
            delete_draft(document.id)

        # And through the ORM, which is the path an importer takes. The refusal
        # arrives from the type table's trigger rather than the header's, because
        # Django deletes children first -- either way the row survives, which is
        # the claim.
        with pytest.raises(IntegrityError, match=r"frozen|cancelled"), transaction.atomic():
            Document.objects.filter(id=document.id).delete()
        assert Document.objects.filter(id=document.id).exists()


def test_positions_cannot_be_written_on_a_validated_document(
    context: TenantContext, company: uuid.UUID, partner: uuid.UUID, series: None
) -> None:
    """The rule belongs to the parent document, so it cannot be a CHECK on the
    line -- it is a trigger that reads the header's state."""
    with tenant_context(context):
        document = a_sale(company, partner)
        document = validate(document.id)

        with pytest.raises(DocumentNotEditableError):
            replace_lines(document.id, [line()])

        with pytest.raises(IntegrityError, match="frozen"), transaction.atomic():
            DocumentLine.objects.create(
                tenant_id=document.tenant_id,
                company_id=document.company_id,
                document=document,
                line_no=99,
                description="smuggled",
                quantity=Decimal(1),
                unit_price=Decimal(1),
                vat_regime_code="standard",
                vat_rate=Decimal(0),
                net_amount=Decimal(1),
                vat_amount=Decimal(0),
                total_amount=Decimal(1),
            )


def test_the_lifecycle_columns_still_move_after_validation(
    context: TenantContext, company: uuid.UUID, partner: uuid.UUID, series: None
) -> None:
    """The freeze is an allow-list, not a lock.

    Cancelling a validated document writes four columns, and the trigger has to
    let exactly those through -- otherwise the freeze would also forbid the one
    transition the law requires to be recorded.
    """
    with tenant_context(context):
        document = a_sale(company, partner)
        document = validate(document.id)
        document = cancel(document.id, reason="Comanda anulata de client")
    assert document.state == DocumentState.CANCELLED


# --- cancellation ------------------------------------------------------------


def test_cancelling_needs_a_reason(
    context: TenantContext, company: uuid.UUID, partner: uuid.UUID, series: None
) -> None:
    with tenant_context(context):
        document = a_sale(company, partner)
        document = validate(document.id)
        with pytest.raises(CancellationReasonRequiredError):
            cancel(document.id, reason="   ")


def test_cancelling_keeps_the_number_and_the_gap_is_permanent(
    context: TenantContext,
    world: dict[str, uuid.UUID],
    company: uuid.UUID,
    partner: uuid.UUID,
    series: None,
) -> None:
    """A register with reassigned numbers is not a register.

    The next document takes the next number, not the cancelled one -- which is
    the property that makes the register answerable at all.
    """
    with tenant_context(context):
        first = a_sale(company, partner)
        first = validate(first.id)
        first = cancel(first.id, reason="Tiparita gresit")

        second = a_sale(company, partner)
        second = validate(second.id)

    assert first.number == 1
    assert first.formatted_number is not None
    assert second.number == 2


def test_a_cancelled_document_cannot_be_written_by_hand_without_a_reason(
    context: TenantContext, company: uuid.UUID, partner: uuid.UUID, series: None
) -> None:
    """The service refuses it and so does the database, which is the half that
    survives an importer."""
    with tenant_context(context):
        document = a_sale(company, partner)
        document.state = DocumentState.CANCELLED
        with (
            pytest.raises(IntegrityError, match="document_cancelled_has_reason"),
            transaction.atomic(),
        ):
            document.save(update_fields=["state"])


# --- positions ---------------------------------------------------------------


def test_a_position_whose_total_is_not_net_plus_vat_is_refused() -> None:
    """Exact addition, no rounding involved -- the one identity this layer is
    entitled to enforce, and it enforces it before the row is built."""
    with pytest.raises(LineAmountsInconsistentError):
        LineInput(
            description="x",
            quantity=Decimal(1),
            unit_price=Decimal(100),
            vat_regime_code="standard",
            vat_rate=Decimal(20),
            net_amount=Decimal(100),
            vat_amount=Decimal(20),
            total_amount=Decimal(121),
        )


def test_a_float_amount_is_refused_rather_than_converted() -> None:
    """`float` makes the same document total differently depending on the order
    the positions were added, and the difference shows up as bani nobody can
    attribute to anything."""
    with pytest.raises(TypeError, match="Decimal"):
        LineInput(
            description="x",
            quantity=1.0,  # type: ignore[arg-type]
            unit_price=Decimal(1),
            vat_regime_code="standard",
            vat_rate=Decimal(0),
            net_amount=Decimal(1),
            vat_amount=Decimal(0),
            total_amount=Decimal(1),
        )


def test_a_position_needs_a_vat_treatment() -> None:
    """Exempt and zero-rated both carry a rate of 0 and are different facts."""
    with pytest.raises(Exception, match="VAT treatment"):
        LineInput(
            description="x",
            quantity=Decimal(1),
            unit_price=Decimal(1),
            vat_regime_code="  ",
            vat_rate=Decimal(0),
            net_amount=Decimal(1),
            vat_amount=Decimal(0),
            total_amount=Decimal(1),
        )


def test_positions_are_renumbered_from_one_on_every_replace(
    context: TenantContext, company: uuid.UUID, partner: uuid.UUID, series: None
) -> None:
    with tenant_context(context):
        document = get_document(open_sale(company_id=company, partner_id=partner, document_date=ON))
        replace_lines(document.id, [line(), line(net="50.0000", vat="10.0000")])
        replace_lines(document.id, [line(net="7.0000", vat="1.4000")])
        assert list(document.lines.values_list("line_no", flat=True)) == [1]
        assert totals_of(document.id).total == Decimal("8.4000")


# --- the two numbering regimes ----------------------------------------------


def test_a_document_under_an_external_regime_validates_without_a_number(
    context: TenantContext, world: dict[str, uuid.UUID], company: uuid.UUID, partner: uuid.UUID
) -> None:
    """The number is not ours to have yet.

    An e-Factura identifier is assigned by the tax service's exchange; refusing
    to validate without one would block a document the exchange has not answered
    about, and generating one would collide with the identifier that arrives.
    """
    with tenant_context(context):
        create_series(
            world["tenant_a"],
            company,
            document_type=None,
            valid_from=date(2020, 1, 1),
            regime=NumberingRegime.EXTERNAL,
        )
        document = a_sale(company, partner, external_number="E01000000123")
        document = validate(document.id)

    assert document.number is None
    assert document.external_number == "E01000000123"
    assert document.state == DocumentState.CONFIRMED


def test_one_external_identifier_belongs_to_one_document(
    context: TenantContext, world: dict[str, uuid.UUID], company: uuid.UUID, partner: uuid.UUID
) -> None:
    """Two documents carrying one e-Factura number is the same compliance defect
    as two carrying one of ours, reached by the other road."""
    with tenant_context(context):
        create_series(
            world["tenant_a"],
            company,
            document_type=None,
            valid_from=date(2020, 1, 1),
            regime=NumberingRegime.EXTERNAL,
        )
        a_sale(company, partner, external_number="E01000000123")
        with (
            pytest.raises(IntegrityError, match="document_external_number_unique"),
            transaction.atomic(),
        ):
            a_sale(company, partner, external_number="E01000000123")


# --- storno ------------------------------------------------------------------


def test_the_storno_copies_the_positions_with_the_sign_inverted(
    context: TenantContext, company: uuid.UUID, partner: uuid.UUID, series: None
) -> None:
    """Quantity and the four amounts flip; the unit price and the rate do not.

    A storno undoes the amount, not the price list -- and `total = net + vat`
    survives the flip, because negating both sides of an addition is still an
    addition.
    """
    with tenant_context(context):
        original = a_sale(company, partner)
        original = validate(original.id)

        storno = create_reversal(
            original.id, reason="Factura emisa gresit", document_date=date(2026, 3, 20)
        )
        undone = storno.lines.get()
        kept = original.lines.get()
        reversed_id = storno.reversal.reversed_document_id

    assert storno.document_type == REVERSAL_TYPE
    assert storno.state == DocumentState.DRAFT
    assert undone.quantity == -kept.quantity
    assert undone.net_amount == -kept.net_amount
    assert undone.vat_amount == -kept.vat_amount
    assert undone.total_amount == -kept.total_amount
    assert undone.unit_price == kept.unit_price
    assert undone.vat_rate == kept.vat_rate
    assert undone.source_line_id == kept.id
    assert reversed_id == original.id


def test_a_document_is_reversed_once(
    context: TenantContext, company: uuid.UUID, partner: uuid.UUID, series: None
) -> None:
    with tenant_context(context):
        original = a_sale(company, partner)
        original = validate(original.id)
        create_reversal(original.id, reason="Prima corectie", document_date=ON)
        with pytest.raises(AlreadyReversedError):
            create_reversal(original.id, reason="A doua", document_date=ON)


def test_a_draft_is_deleted_not_reversed(
    context: TenantContext, company: uuid.UUID, partner: uuid.UUID, series: None
) -> None:
    with tenant_context(context):
        draft = a_sale(company, partner)
        with pytest.raises(SourceNotValidatedError):
            create_reversal(draft.id, reason="Nimic de anulat", document_date=ON)


def test_the_storno_takes_its_own_number_at_its_own_validation(
    context: TenantContext, company: uuid.UUID, partner: uuid.UUID, series: None
) -> None:
    """One rule for every document. A storno that reserved a number when it was
    started and was then abandoned would burn one exactly as any other draft
    would."""
    with tenant_context(context):
        original = a_sale(company, partner)
        original = validate(original.id)
        storno = create_reversal(original.id, reason="Corectie", document_date=ON)
        assert storno.number is None
        storno = validate(storno.id)
    assert storno.number == 2


def test_a_storno_cannot_point_at_itself(
    context: TenantContext, company: uuid.UUID, partner: uuid.UUID, series: None
) -> None:
    with tenant_context(context):
        document = a_sale(company, partner)
        with (
            pytest.raises(IntegrityError, match="reversal_document_not_itself"),
            transaction.atomic(),
        ):
            ReversalDocument.objects.create(
                document=document,
                tenant_id=document.tenant_id,
                company_id=document.company_id,
                reversed_document=document,
                reason="imposibil",
            )


# --- conversion --------------------------------------------------------------


def test_a_proforma_becomes_a_sale_and_the_positions_carry_the_link_back(
    context: TenantContext, company: uuid.UUID, partner: uuid.UUID, series: None
) -> None:
    with tenant_context(context):
        proforma = get_document(
            open_proforma(company_id=company, partner_id=partner, document_date=ON)
        )
        replace_lines(proforma.id, [line()])
        proforma = validate(proforma.id)

        sale = get_document(convert_to_sale(proforma.id, document_date=date(2026, 3, 15)))
        carried = sale.lines.get()
        offered = proforma.lines.get()
        nature = SalesDocument.objects.filter(document=sale).get().nature

    assert sale.document_type == SALES_DOCUMENT
    assert sale.source_document_id == proforma.id
    assert carried.source_line_id == offered.id
    assert nature == SaleNature.DELIVERY


def test_an_undeclared_conversion_is_refused(
    context: TenantContext, company: uuid.UUID, partner: uuid.UUID, series: None
) -> None:
    """What becomes what is a declaration, not a branch inside a function."""
    assert PROFORMA in spec_for(PROFORMA).code
    with tenant_context(context):
        sale = a_sale(company, partner)
        sale = validate(sale.id)
        with pytest.raises(SourceNotConvertibleError):
            convert_to_sale(sale.id, document_date=ON)


def test_a_source_is_converted_once(
    context: TenantContext, company: uuid.UUID, partner: uuid.UUID, series: None
) -> None:
    with tenant_context(context):
        proforma = get_document(
            open_proforma(company_id=company, partner_id=partner, document_date=ON)
        )
        replace_lines(proforma.id, [line()])
        proforma = validate(proforma.id)
        convert_to_sale(proforma.id, document_date=ON)
        with pytest.raises(AlreadyConvertedError):
            convert_to_sale(proforma.id, document_date=ON)


def test_a_draft_proforma_is_not_a_commitment(
    context: TenantContext, company: uuid.UUID, partner: uuid.UUID, series: None
) -> None:
    with tenant_context(context):
        proforma = get_document(
            open_proforma(company_id=company, partner_id=partner, document_date=ON)
        )
        replace_lines(proforma.id, [line()])
        with pytest.raises(SourceNotValidatedError):
            convert_to_sale(proforma.id, document_date=ON)


# --- purchases: the supplier's number is the supplier's ----------------------


def test_the_same_supplier_document_is_not_recorded_twice(
    context: TenantContext, company: uuid.UUID, partner: uuid.UUID, series: None
) -> None:
    """`R20`: deduplication on the natural business key, separate from idempotency.

    The same invoice arriving through an import and typed by hand is one
    document, and the triple (supplier, their number, their date) is what says so.
    """
    with tenant_context(context):
        open_purchase(
            company_id=company,
            partner_id=partner,
            document_date=ON,
            supplier_document_number="AA 0000123",
            supplier_document_date=date(2026, 3, 1),
        )
        with pytest.raises(SupplierDocumentAlreadyRecordedError):
            open_purchase(
                company_id=company,
                partner_id=partner,
                document_date=ON,
                supplier_document_number="AA 0000123",
                supplier_document_date=date(2026, 3, 1),
            )


def test_two_suppliers_may_issue_the_same_number_on_the_same_day(
    context: TenantContext,
    world: dict[str, uuid.UUID],
    company: uuid.UUID,
    partner: uuid.UUID,
    series: None,
) -> None:
    """Which is ordinary, and which a key without the supplier would refuse.

    That refusal is the failure worth a test of its own: it looks like the
    deduplication working, and it is the deduplication rejecting a document that
    was never a duplicate. Nothing in the message would say so.
    """
    with tenant_context(context):
        other = Partner.objects.create(
            tenant_id=world["tenant_a"],
            legal_name='Societatea cu Raspundere Limitata "Delta"',
            idno="1003600044444",
            is_supplier=True,
        )
        for supplier in (partner, other.id):
            open_purchase(
                company_id=company,
                partner_id=supplier,
                document_date=ON,
                supplier_document_number="001",
                supplier_document_date=date(2026, 3, 1),
            )
        assert PurchaseDocument.objects.filter(supplier_document_number="001").count() == 2


def test_a_supplier_order_becomes_a_purchase_with_the_supplier_own_reference(
    context: TenantContext, company: uuid.UUID, partner: uuid.UUID, series: None
) -> None:
    from evidenta.operations.purchases.services.documents import convert_to_purchase

    with tenant_context(context):
        order = get_document(
            open_supplier_order(company_id=company, partner_id=partner, document_date=ON)
        )
        replace_lines(order.id, [line()])
        order = validate(order.id)
        purchase = get_document(
            convert_to_purchase(
                order.id,
                document_date=date(2026, 3, 18),
                supplier_document_number="BB 0000777",
                supplier_document_date=date(2026, 3, 17),
            )
        )
        reference = purchase.purchase.supplier_document_number

    assert purchase.document_type == PURCHASE_DOCUMENT
    assert purchase.source_document_id == order.id
    assert reference == "BB 0000777"


# --- history -----------------------------------------------------------------


def test_the_document_carries_its_own_history(
    context: TenantContext, company: uuid.UUID, partner: uuid.UUID, series: None
) -> None:
    """Distinct from the audit trail: that answers "who did what in the system",
    this answers "what happened to this document", read from the document."""
    with tenant_context(context):
        document = a_sale(company, partner)
        document = validate(document.id)
        document = cancel(document.id, reason="Livrare refuzata")
        moves = [event.event_type for event in history_of(document.id)]

    assert moves == ["document.drafted", "document.validated", "document.cancelled"]


# --- isolation ---------------------------------------------------------------


def test_a_document_of_another_tenant_is_absent_not_forbidden(
    context: TenantContext,
    world: dict[str, uuid.UUID],
    company: uuid.UUID,
    partner: uuid.UUID,
    series: None,
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> None:
    """IZ-04. A 403 would confirm the identifier exists, which is the leak."""
    with tenant_context(context):
        mine = a_sale(company, partner)

    other_company = company_of(world["tenant_b"], "1002600000002", "Beta Trading")
    grant_company(world["tenant_b"], other_company, world["user_b"], world["user_b"])
    outsider = TenantContext(
        tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="docs-b"
    )

    with tenant_context(outsider):
        assert not Document.objects.filter(id=mine.id).exists()
        assert not DocumentLine.objects.filter(document_id=mine.id).exists()
        assert Document.objects.count() == 0
