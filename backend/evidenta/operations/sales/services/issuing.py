"""Issuing a sale: validate it, then post it -- ADR-073.

A credit note comes through here too, and that is the point of ADR-073 §7: a
return has the same lines, the same numbering and the same lifecycle as the
delivery it answers, so it has the same door. What differs is which event the
engine records, and the document's own nature says which.

Two steps, and they are separate on purpose. **Validation** (*validat*) is the
business commitment: the number is allocated and the document freezes. **Posting**
is the accounting effect, and it goes through the Posting Engine like every other
effect (`R9`) -- there is no second route to the ledger and this module does not
open one.

**What crosses the seam is a fact, not a row.** `SalesInvoiceFact` belongs to
`accounting`; this module fills it in. A service that handed a `SalesDocument` to
the engine would make the shape of this table part of the engine's contract.

**Idempotent through the event, not through a flag here** (`R19`). A second issue
of the same document returns what the first produced: the key is on the accounting
event, so a retry after a timeout cannot produce a second entry.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.db import transaction

from evidenta.accounting.posting.services.commercial import (
    SalesInvoiceFact,
    SalesPostingResult,
    post_sales_invoice,
)
from evidenta.operations.sales.models import SalesDocument
from evidenta.platform.api.errors import ApiError
from evidenta.platform.documents.services.lifecycle import (
    get_document,
    mark_posted,
    validate,
)
from evidenta.platform.documents.services.lines import totals_of
from evidenta.platform.tenancy.services.companies import functional_currency


class SaleNotIssuableError(ApiError):
    code = "sales.not_issuable"
    status = 409


def issue_and_post(
    *,
    document_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    request_id: str,
    capability_snapshot: dict[str, Any],
) -> SalesPostingResult:
    """Validate the document if it is still a draft, then post it.

    Validating here rather than expecting the caller to have done it: an invoice
    that is posted but not numbered is not a thing, and two calls that have to
    happen in order are two chances to do only the first.
    """
    document = get_document(document_id)
    extension = SalesDocument.objects.filter(document_id=document_id).first()
    if extension is None:
        raise SaleNotIssuableError(f"document {document_id} is not a sale")

    if document.state == "draft":
        with transaction.atomic():
            document = validate(document_id)

    if document.state not in ("confirmed", "posted"):
        raise SaleNotIssuableError(
            f"a sale is posted from `confirmed`; this one is {document.state!r}"
        )

    # The type declares `requires_partner`, so `validate` has already refused a
    # document without one -- but the column is nullable for the types that do not,
    # and narrowing it here is what lets the fact carry a partner rather than a
    # maybe-partner. A receivable belongs to somebody.
    if document.partner_id is None:
        raise SaleNotIssuableError("a sale has a counterparty; the receivable belongs to somebody")

    totals = totals_of(document_id)
    if totals.total <= 0:
        raise SaleNotIssuableError(
            "a sale with no positive total has nothing to recognise; an empty "
            "invoice is a draft somebody abandoned, not a document"
        )

    # The advance is refused here rather than at the engine, so the message names
    # the decision: ADR-073 §6 keeps its treatment unregistered on purpose, because
    # posting only the first half would leave a balance of advances that nothing
    # in the product could ever clear.
    if extension.nature == "advance":
        raise SaleNotIssuableError(
            "an advance has no posting treatment yet: crediting the advance without "
            "the settlement that clears it would grow a balance nothing can reduce "
            "(ADR-073 §6)"
        )

    result = post_sales_invoice(
        nature=str(extension.nature),
        tenant_id=document.tenant_id,
        company_id=document.company_id,
        functional_currency=functional_currency(document.company_id),
        fact=SalesInvoiceFact(
            document_id=document_id,
            partner_id=document.partner_id,
            accounting_date=document.accounting_date,
            document_date=document.document_date,
            total=totals.total,
            currency=document.currency,
            revenue_kind=extension.revenue_kind,
            partner_resident=extension.partner_resident,
            # In Romanian, and from this module: it lands in the register, which
            # `C33` keeps in Romanian whatever the interface is showing. The word
            # follows the nature, because a register that called a credit note an
            # invoice would be read wrong by whoever opens it next.
            description=(
                f"{'Notă de credit' if extension.nature == 'return' else 'Factură emisă'} "
                f"{document.formatted_number or ''}"
            ).strip(),
        ),
        actor_user_id=actor_user_id,
        request_id=request_id,
        capability_snapshot=capability_snapshot,
    )

    # The document follows the ledger, not the other way round: the state moves
    # only once an entry exists, so a failed posting leaves a `confirmed` document
    # somebody can look at rather than a `posted` one with nothing behind it.
    mark_posted(document_id)
    return result
