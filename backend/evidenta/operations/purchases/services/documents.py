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
from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction

from evidenta.operations.purchases.models import PurchaseDocument, SupplierOrder
from evidenta.operations.purchases.types import PURCHASE_DOCUMENT, SUPPLIER_ORDER
from evidenta.platform.api.errors import ApiError
from evidenta.platform.documents.errors import PartnerRequiredError
from evidenta.platform.documents.services.conversion import convert
from evidenta.platform.documents.services.lifecycle import open_draft


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


@transaction.atomic
def open_purchase(
    *,
    company_id: uuid.UUID,
    partner_id: uuid.UUID,
    document_date: date,
    supplier_document_number: str,
    supplier_document_date: date,
    accounting_date: date | None = None,
    currency: str | None = None,
    exchange_rate: Decimal | None = None,
    notes: str | None = None,
) -> uuid.UUID:
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
        exchange_rate=exchange_rate,
        notes=notes,
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
        )
    except IntegrityError as clash:
        if "purchase_document_supplier_reference_unique" in str(clash):
            raise SupplierDocumentAlreadyRecordedError(
                f"supplier document {reference} of {supplier_document_date} from "
                f"this supplier is already recorded in this company"
            ) from clash
        raise
    return document.id


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
) -> uuid.UUID:
    document = open_draft(
        company_id=company_id,
        document_type=SUPPLIER_ORDER,
        document_date=document_date,
        partner_id=partner_id,
        currency=currency,
        exchange_rate=exchange_rate,
        notes=notes,
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
    accounting_date: date | None = None,
    exchange_rate: Decimal | None = None,
) -> uuid.UUID:
    """Turn a supplier order into the purchase that records what arrived.

    The supplier's reference is required here too, and cannot be carried over
    from the order: the order is ours, the invoice is theirs, and they have
    different numbers by construction.
    """
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
