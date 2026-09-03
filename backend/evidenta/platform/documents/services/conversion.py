"""Turning an operational document into a commercial one.

A proforma becomes a sale, a customer order becomes a sale, a supplier order
becomes a purchase. What may become what is **declared by the type**, in the
registry, not decided here: a conversion the registry does not list is refused
rather than attempted, so adding a route is an edit to a declaration instead of a
condition inside a function.

The result is a **draft**. The number is allocated when it is validated, like
every other document's, and a conversion that is started and abandoned burns
nothing. The link runs backwards -- `source_document` on the new document,
`source_line_id` on each position -- so the chain is navigable in both directions
without a second table that could disagree with the first.

**The extension row is not created here.** A sale carries its nature, a purchase
carries the supplier's own number: those live in the module that owns the type,
and the core cannot know them. The caller creates the header through this
function and its own row in the same transaction.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from django.db import transaction

from evidenta.platform.documents.errors import (
    AlreadyConvertedError,
    SourceNotConvertibleError,
    SourceNotValidatedError,
)
from evidenta.platform.documents.models import Document, DocumentState
from evidenta.platform.documents.registry import conversion_targets
from evidenta.platform.documents.services.history import record_event
from evidenta.platform.documents.services.lifecycle import get_document, open_draft
from evidenta.platform.documents.services.lines import copy_lines

#: A document has to be a commitment before anything follows from it. A draft
#: proforma is a piece of work in progress, not an offer anybody received.
CONVERTIBLE_STATES = frozenset(
    {DocumentState.CONFIRMED, DocumentState.POSTED, DocumentState.COMPLETED}
)


@transaction.atomic
def convert(
    source_id: uuid.UUID,
    *,
    target_type: str,
    document_date: date,
    accounting_date: date | None = None,
    exchange_rate: Decimal | None = None,
    copy_positions: bool = True,
) -> Document:
    """Produce the draft of ``target_type`` from ``source``, and return it.

    ``document_date`` is required and has no default. The date of the invoice is
    not the date of the order it came from, and defaulting to either the source's
    date or today would silently decide which -- on a document that leaves the
    company.

    ``exchange_rate`` is **not** carried over from the source for the same
    reason: a rate belongs to a day, and the target's day is a different one.
    Copying it would restate a foreign-currency order at a rate nobody chose for
    the invoice. A foreign-currency conversion with no rate supplied is refused
    by `open_draft`.
    """
    source = get_document(source_id)
    allowed = conversion_targets(source.document_type)
    if target_type not in allowed:
        raise SourceNotConvertibleError(
            f"a {source.document_type} does not become a {target_type}; the type "
            f"declares {list(allowed) or 'no conversions'}"
        )
    if source.state not in CONVERTIBLE_STATES:
        raise SourceNotValidatedError(
            f"document {source.id} is {source.state}; only a validated document is "
            f"converted, because only a validated document is a commitment"
        )

    existing = (
        Document.objects.filter(source_document=source, document_type=target_type)
        .exclude(state=DocumentState.CANCELLED)
        .first()
    )
    if existing is not None:
        raise AlreadyConvertedError(
            f"document {source.id} has already produced {existing.id}; converting "
            f"again would issue the same commitment twice"
        )

    target = open_draft(
        company_id=source.company_id,
        document_type=target_type,
        document_date=document_date,
        accounting_date=accounting_date,
        partner_id=source.partner_id,
        currency=source.currency,
        exchange_rate=exchange_rate,
        # The denomination is the contract's, and the contract is the same one:
        # what was offered in conventional units is invoiced in them.
        contract_denomination=source.contract_denomination,
        source_document_id=source.id,
    )
    if copy_positions:
        copy_lines(source, target)

    record_event(
        target,
        event_type="document.converted_from",
        detail={
            "source_document_id": str(source.id),
            "source_type": source.document_type,
            "source_number": source.formatted_number or source.external_number,
        },
    )
    record_event(
        source,
        event_type="document.converted_into",
        detail={"target_document_id": str(target.id), "target_type": target_type},
    )
    return target
