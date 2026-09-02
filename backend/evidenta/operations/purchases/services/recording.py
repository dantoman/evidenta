"""Recording a purchase: validate it, then post it -- ADR-073.

The mirror of `sales.services.issuing`, and the same two steps for the same
reason: **validation** freezes the document and allocates *our* registration
number, **posting** is the accounting effect and goes through the Posting Engine
like every other effect (`R9`).

The word is *recording*, not *issuing*, and the difference is the domain's rather
than the vocabulary's: we issue our invoices and we record theirs. Their number
and date are already on the document; validation does not touch them.

**What crosses the seam is a fact, not a row.** `PurchaseInvoiceFact` belongs to
`accounting`; this module fills it in.

**Idempotent through the event** (`R19`). A second recording of the same document
returns what the first produced -- distinct from `R20`, which stops the same
supplier document being entered twice as two documents.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.db import transaction

from evidenta.accounting.posting.services.commercial import (
    PurchaseInvoiceFact,
    PurchasePostingResult,
    post_purchase_invoice,
    vat_shares,
)
from evidenta.operations.purchases.models import PurchaseDocument
from evidenta.platform.api.errors import ApiError
from evidenta.platform.documents.services.lifecycle import (
    get_document,
    mark_posted,
    validate,
)
from evidenta.platform.documents.services.lines import totals_of, vat_breakdown
from evidenta.platform.tenancy.services.companies import functional_currency
from evidenta.platform.tenancy.services.tax_status import tax_status_at


class PurchaseNotRecordableError(ApiError):
    code = "purchases.not_recordable"
    status = 409


def record_and_post(
    *,
    document_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    request_id: str,
    capability_snapshot: dict[str, Any],
) -> PurchasePostingResult:
    """Validate the document if it is still a draft, then post it."""
    document = get_document(document_id)
    extension = PurchaseDocument.objects.filter(document_id=document_id).first()
    if extension is None:
        raise PurchaseNotRecordableError(f"document {document_id} is not a purchase")

    if document.state == "draft":
        with transaction.atomic():
            document = validate(document_id)

    if document.state not in ("confirmed", "posted"):
        raise PurchaseNotRecordableError(
            f"a purchase is posted from `confirmed`; this one is {document.state!r}"
        )

    if document.partner_id is None:
        raise PurchaseNotRecordableError(
            "a purchase has a counterparty; the debt is owed to somebody"
        )

    totals = totals_of(document_id)
    if totals.total <= 0:
        raise PurchaseNotRecordableError(
            "a purchase with no positive total has nothing to record; an empty "
            "invoice is a draft somebody abandoned, not a document"
        )

    # Whether the VAT the supplier charged is ours to deduct follows from our
    # registration on the **accounting** date -- the day the invoice enters the
    # books and the day the event is stamped with the same status (ADR-088), so
    # the engine can hold the two against each other. Read here, in the module
    # that owns the document, and handed to the engine as a discriminator on the
    # pattern of `partner_resident`; how a status is meant to reach treatment
    # selection stays `OD-130` (ADR-089).
    deductible = bool(
        tax_status_at(document.company_id, document.accounting_date)["vat"]["registered"]
    )

    result = post_purchase_invoice(
        tenant_id=document.tenant_id,
        company_id=document.company_id,
        functional_currency=functional_currency(document.company_id),
        fact=PurchaseInvoiceFact(
            document_id=document_id,
            partner_id=document.partner_id,
            accounting_date=document.accounting_date,
            document_date=document.document_date,
            total=totals.total,
            net=totals.net,
            vat=totals.vat,
            vat_by_rate=vat_shares(vat_breakdown(document_id)),
            vat_deductible=deductible,
            currency=document.currency,
            cost_destination=extension.cost_destination,
            partner_resident=extension.partner_resident,
            # Romanian, and the supplier's own number rather than ours: in the
            # register, "which document is this" is answered by the number the
            # person holding the paper can see (`C33`).
            description=(
                f"Factură primită {extension.supplier_document_number} "
                f"din {extension.supplier_document_date:%d.%m.%Y}"
            ),
        ),
        actor_user_id=actor_user_id,
        request_id=request_id,
        capability_snapshot=capability_snapshot,
    )

    # The document follows the ledger, not the other way round.
    mark_posted(document_id)
    return result
