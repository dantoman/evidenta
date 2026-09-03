"""What is still open, on both sides of a match -- ADR-087.

Two lists, and they answer different questions. *Open documents* is what a partner
still owes or is still owed; *open movements* is money that has arrived or left
and has not been pointed at anything. A matching screen needs both, and computing
one from the other is not possible: a receipt with nothing to match is not an
error, and neither is an invoice nobody has paid.

**The totals come from the same services the documents' own screens use**, not
from a second query over their tables: an open balance that disagreed with the
invoice it names would be worse than no balance at all.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import F, Sum
from django.db.models.functions import Coalesce

from evidenta.operations.settlements.models import Settlement
from evidenta.operations.settlements.services.allocation import (
    MOVEMENT_OF,
    PURCHASE,
    SALE,
    SIDE_OF,
)
from evidenta.operations.treasury.services.documents import movement_of
from evidenta.platform.documents.services.lifecycle import posted_of_types
from evidenta.platform.documents.services.lines import totals_of


@dataclass(frozen=True, slots=True)
class OpenItem:
    document_id: uuid.UUID
    document_type: str
    formatted_number: str | None
    document_date: date
    partner_id: uuid.UUID | None
    side: str
    #: The figures below are in this currency: a document's in its own, a
    #: movement's in the functional one. What is open on a EUR invoice is EUR.
    currency: str
    total: Decimal
    allocated: Decimal

    @property
    def outstanding(self) -> Decimal:
        return self.total - self.allocated


def _allocations(field: str, document_ids: list[uuid.UUID]) -> dict[uuid.UUID, Decimal]:
    """Allocated amounts for many documents in one query.

    One query rather than one per row: a balances screen is the first place in
    this product where the number of documents is not small, and a per-row query
    there is how a screen becomes slow before anybody has entered a year of data.
    """
    # In the settled document's currency when the settlement crossed currencies
    # (ADR-097): `amount` is the movement's lei, `amount_currency` what they
    # settled of a EUR invoice, and it is the latter that counts the invoice down.
    # A movement's own allocations are always in its currency, so the same
    # expression is right from either side.
    measure = (
        Coalesce(F("amount_currency"), F("amount"))
        if field == "settled_document_id"
        else F("amount")
    )
    rows = (
        Settlement.objects.filter(**{f"{field}__in": document_ids})
        .values(field)
        .annotate(total=Sum(measure))
    )
    return {row[field]: Decimal(row["total"]) for row in rows}


def open_documents(company_id: uuid.UUID) -> tuple[OpenItem, ...]:
    """Posted invoices with something still open, oldest first."""
    documents = posted_of_types(company_id, (SALE, PURCHASE))
    allocated = _allocations("settled_document_id", [d.id for d in documents])

    items = []
    for document in documents:
        item = OpenItem(
            document_id=document.id,
            document_type=document.document_type,
            formatted_number=document.formatted_number,
            document_date=document.document_date,
            partner_id=document.partner_id,
            side=str(SIDE_OF[document.document_type]),
            currency=document.currency,
            total=totals_of(document.id).total,
            allocated=allocated.get(document.id, Decimal(0)),
        )
        if item.outstanding > 0:
            items.append(item)
    return tuple(items)


def open_movements(company_id: uuid.UUID) -> tuple[OpenItem, ...]:
    """Posted receipts and payments with something not yet pointed at anything."""
    types = tuple(MOVEMENT_OF.values())
    documents = posted_of_types(company_id, types)
    allocated = _allocations("movement_document_id", [d.id for d in documents])

    items = []
    for document in documents:
        movement = movement_of(document.id)
        item = OpenItem(
            document_id=document.id,
            document_type=document.document_type,
            formatted_number=document.formatted_number,
            document_date=document.document_date,
            partner_id=document.partner_id,
            side="receivable" if movement.direction == "receipt" else "payable",
            currency=document.currency,
            total=movement.amount,
            allocated=allocated.get(document.id, Decimal(0)),
        )
        if item.outstanding > 0:
            items.append(item)
    return tuple(items)
