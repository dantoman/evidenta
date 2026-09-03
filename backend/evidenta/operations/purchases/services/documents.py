"""Opening and converting purchase-side documents.

The mirror of the sales services, with the one difference the domain actually
has: **the supplier's number and date are required and are theirs.** They are
recorded as received, not allocated, and they do not travel through our series --
a register that claimed authorship of a number the supplier issued would be
wrong in a way that only surfaces during a cross-check.

Our own registration number is still ours, allocated by the core at validation
like any other document's.

**Identifiers cross the seam, not rows** -- see the note in the sales services.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction

from evidenta.accounting.currency.services.rates import rate_on
from evidenta.operations.purchases.models import (
    CostDestination,
    PurchaseDocument,
    SupplierOrder,
)
from evidenta.operations.purchases.types import PURCHASE_DOCUMENT, SUPPLIER_ORDER
from evidenta.platform.api.errors import ApiError
from evidenta.platform.documents.errors import PartnerRequiredError
from evidenta.platform.documents.services.conversion import convert
from evidenta.platform.documents.services.lifecycle import open_draft
from evidenta.platform.tenancy.services.companies import functional_currency


class SupplierReferenceRequiredError(ApiError):
    """A purchase with no reference to the document it records.

    Not optional and not defaulted. The supplier's number and date are how the
    same document is recognised when it arrives a second time by another road --
    an import, a scan, an e-Factura -- and deduplication on a natural business
    key (`R20`) has nothing to work with without them.
    """

    code = "purchases.supplier_reference_required"
    status = 422


class SupplierDocumentAlreadyRecordedError(ApiError):
    """The same supplier document, entered twice. `R20`, refused by a constraint."""

    code = "purchases.supplier_document_already_recorded"
    status = 409


class CostDestinationInvalidError(ApiError):
    """Where the cost lands is asked for, and the vocabulary is closed.

    Its own code rather than a generic validation error: the caller has to
    *choose*, and the four values are not interchangeable -- one of them decides
    whether the amount lands in the profit and loss account or in the cost of
    production.
    """

    code = "purchases.cost_destination_invalid"
    status = 422


def _destination(value: str) -> str:
    if value not in CostDestination.values:
        raise CostDestinationInvalidError(
            f"cost_destination is {value!r}; it selects the expense role, so it is "
            f"chosen from {sorted(CostDestination.values)} and never defaulted"
        )
    return value


@transaction.atomic
def open_purchase(
    *,
    company_id: uuid.UUID,
    partner_id: uuid.UUID,
    document_date: date,
    supplier_document_number: str,
    supplier_document_date: date,
    cost_destination: str,
    partner_resident: bool,
    accounting_date: date | None = None,
    currency: str | None = None,
    exchange_rate: Decimal | None = None,
    notes: str | None = None,
    rate_term: str = "payment_date",
    contract_denomination: str | None = None,
) -> uuid.UUID:
    """Start a purchase as a draft.

    In another currency the document carries its denomination and a rate; the
    rate, when none is given, is the official rate of the document's date, as on
    the sale (ADR-039 section 3.2, ADR-097).
    """
    destination = _destination(cost_destination)
    reference = (supplier_document_number or "").strip()
    if not reference:
        raise SupplierReferenceRequiredError(
            "a purchase records a document somebody else issued; without their "
            "number the same document cannot be recognised when it arrives again"
        )

    document = open_draft(
        company_id=company_id,
        document_type=PURCHASE_DOCUMENT,
        document_date=document_date,
        accounting_date=accounting_date,
        partner_id=partner_id,
        currency=currency,
        exchange_rate=rate_of_the_day(company_id, currency, document_date, exchange_rate),
        notes=notes,
        rate_term=rate_term,
        contract_denomination=contract_denomination,
    )
    try:
        PurchaseDocument.objects.create(
            document=document,
            tenant_id=document.tenant_id,
            company_id=document.company_id,
            # From the header, not from the argument: `Document.partner_id` is
            # the column the deduplication key has to agree with, and reading it
            # back is what makes the two impossible to set apart later.
            partner_id=_supplier_of(document.partner_id),
            supplier_document_number=reference,
            supplier_document_date=supplier_document_date,
            cost_destination=destination,
            partner_resident=partner_resident,
        )
    except IntegrityError as clash:
        if "purchase_document_supplier_reference_unique" in str(clash):
            raise SupplierDocumentAlreadyRecordedError(
                f"supplier document {reference} of {supplier_document_date} from "
                f"this supplier is already recorded in this company"
            ) from clash
        raise
    return document.id


def rate_of_the_day(
    company_id: uuid.UUID, currency: str | None, on: date, supplied: Decimal | None
) -> Decimal | None:
    """The caller's rate, or the official rate of the document's day -- the
    sales twin of this helper says why it lives here and not in the core."""
    if supplied is not None or currency is None or currency == functional_currency(company_id):
        return supplied
    return rate_on(currency, on)


@transaction.atomic
def open_supplier_order(
    *,
    company_id: uuid.UUID,
    partner_id: uuid.UUID,
    document_date: date,
    expected_delivery_date: date | None = None,
    currency: str | None = None,
    exchange_rate: Decimal | None = None,
    notes: str | None = None,
    rate_term: str = "payment_date",
) -> uuid.UUID:
    document = open_draft(
        company_id=company_id,
        document_type=SUPPLIER_ORDER,
        document_date=document_date,
        partner_id=partner_id,
        currency=currency,
        exchange_rate=exchange_rate,
        notes=notes,
        rate_term=rate_term,
    )
    SupplierOrder.objects.create(
        document=document,
        tenant_id=document.tenant_id,
        company_id=document.company_id,
        expected_delivery_date=expected_delivery_date,
    )
    return document.id


@transaction.atomic
def convert_to_purchase(
    source_id: uuid.UUID,
    *,
    document_date: date,
    supplier_document_number: str,
    supplier_document_date: date,
    cost_destination: str,
    partner_resident: bool,
    accounting_date: date | None = None,
    exchange_rate: Decimal | None = None,
) -> uuid.UUID:
    """Turn a supplier order into the purchase that records what arrived.

    The supplier's reference is required here too, and cannot be carried over
    from the order: the order is ours, the invoice is theirs, and they have
    different numbers by construction.
    """
    destination = _destination(cost_destination)
    reference = (supplier_document_number or "").strip()
    if not reference:
        raise SupplierReferenceRequiredError(
            "the supplier's own number cannot be carried over from our order: the "
            "order is ours and the invoice is theirs"
        )

    purchase = convert(
        source_id,
        target_type=PURCHASE_DOCUMENT,
        document_date=document_date,
        accounting_date=accounting_date,
        exchange_rate=exchange_rate,
    )
    try:
        PurchaseDocument.objects.create(
            document=purchase,
            tenant_id=purchase.tenant_id,
            company_id=purchase.company_id,
            partner_id=_supplier_of(purchase.partner_id),
            supplier_document_number=reference,
            supplier_document_date=supplier_document_date,
            cost_destination=destination,
            partner_resident=partner_resident,
        )
    except IntegrityError as clash:
        if "purchase_document_supplier_reference_unique" in str(clash):
            raise SupplierDocumentAlreadyRecordedError(
                f"supplier document {reference} of {supplier_document_date} from "
                f"this supplier is already recorded in this company"
            ) from clash
        raise
    return purchase.id


def _supplier_of(partner_id: uuid.UUID | None) -> uuid.UUID:
    """The counterparty, refusing the absence rather than assuming it away.

    The header carries a nullable counterparty because a draft is allowed to be
    incomplete -- that is what a draft is. A purchase is not: the supplier is
    half of the key `R20` deduplicates on, and a row that reached the table
    without one would make the same document enterable twice and the constraint
    silent about it.

    Three callers away this cannot happen: `open_purchase` takes the supplier as
    a required argument, and a conversion copies it from a source that was
    validated, which the registry refuses without one. An invariant held three
    functions away is an invariant nobody re-checks, so it is checked here.
    """
    if partner_id is None:
        raise PartnerRequiredError(
            "a purchase records a document somebody else issued; without the "
            "supplier the deduplication key has nothing to agree with"
        )
    return partner_id


@dataclass(frozen=True, slots=True)
class PurchaseView:
    """What another module may know about a purchase without reading its table."""

    supplier_document_number: str
    supplier_document_date: date
    cost_destination: str
    partner_resident: bool


def details_of(document_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, PurchaseView]:
    """The purchase-side facts of many documents at once, for a register.

    The supplier's number and date are what the register of purchases carries
    beside our own number: the paper the person holds is identified by them.
    Batched for a month, absent for ids that are not purchases.
    """
    rows = PurchaseDocument.objects.filter(document_id__in=list(document_ids)).values(
        "document_id",
        "supplier_document_number",
        "supplier_document_date",
        "cost_destination",
        "partner_resident",
    )
    return {
        row["document_id"]: PurchaseView(
            supplier_document_number=str(row["supplier_document_number"]),
            supplier_document_date=row["supplier_document_date"],
            cost_destination=str(row["cost_destination"]),
            partner_resident=bool(row["partner_resident"]),
        )
        for row in rows
    }


def residence_of(document_id: uuid.UUID) -> bool:
    """Whether the supplier on this invoice was recorded as a resident.

    The mirror of the sales helper, and public for the same reason: settlement
    reads the discriminator from the document that carries it, never from the
    partner card, which has none (ADR-073 §2).
    """
    resident = (
        PurchaseDocument.objects.filter(document_id=document_id)
        .values_list("partner_resident", flat=True)
        .first()
    )
    if resident is None:
        raise SupplierReferenceRequiredError(f"document {document_id} is not a purchase")
    return bool(resident)
