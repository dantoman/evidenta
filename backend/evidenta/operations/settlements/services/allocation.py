"""Allocating a movement to a document -- ADR-087.

**Nothing here posts anything, and in the functional currency nothing is even
emitted.** The receipt already debited the treasury and credited the receivable;
saying *which invoice* it answered moves no balance.

The first draft of this module emitted the accounting event regardless and let
the differences handler return no formulas. The engine refused it, and the reason
is worth keeping: `contract_denomination` is a closed vocabulary of exactly two
values -- `foreign_currency` and `conventional_units` -- the two notions the
standard names (pct. 4, 17). There is **no value meaning "no difference can
arise"**, because the event belongs to the difference, not to the allocation.
Spec B §10.1 says the same thing from the other end: the realised differences are
posted *as their own accounting event*.

So: an allocation inside the functional currency is recorded and audited, and
emits nothing. When settlement across currencies arrives (`OD-127`), the event is
emitted with the denomination the contract actually has.

**The discriminators come from the settled document.** Residence was asked once,
of the person who knew (ADR-073 §2); reading it back is what keeps one invoice
from carrying two answers.

**Two ceilings, both refused rather than clamped.** An allocation may not exceed
what is left on the document, nor what is left on the movement. Clamping to the
smaller would post a number nobody typed and leave the difference unexplained.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from evidenta.operations.purchases.services.documents import residence_of as purchase_residence
from evidenta.operations.sales.services.documents import residence_of as sale_residence
from evidenta.operations.settlements.models import Settlement, Side
from evidenta.operations.treasury.services.documents import movement_of
from evidenta.platform.api.errors import ApiError
from evidenta.platform.audit.services.recording import record
from evidenta.platform.documents.services.lifecycle import get_document
from evidenta.platform.documents.services.lines import totals_of
from evidenta.platform.tenancy.services.companies import functional_currency

SALE = "sales.document"
PURCHASE = "purchases.document"
RECEIPT = "treasury.receipt"
PAYMENT = "treasury.payment"

#: What kind of document has which kind of balance, and which movement clears it.
#: Enumerated rather than inferred: "a receipt settles a receivable" is a rule,
#: and a pairing derived from a naming convention would break the day a type is
#: named differently.
SIDE_OF = {SALE: Side.RECEIVABLE, PURCHASE: Side.PAYABLE}
MOVEMENT_OF = {Side.RECEIVABLE: RECEIPT, Side.PAYABLE: PAYMENT}


class SettlementRefusedError(ApiError):
    code = "settlements.refused"
    status = 409


class NotSettleableError(ApiError):
    """One of the two documents is not of a kind that settles or is settled."""

    code = "settlements.not_settleable"
    status = 422


class OverAllocatedError(ApiError):
    """More than the document, or more than the movement, still holds."""

    code = "settlements.over_allocated"
    status = 409


@dataclass(frozen=True, slots=True)
class Allocation:
    settlement_id: uuid.UUID
    #: What remains on the settled document after this allocation. Returned rather
    #: than recomputed by the caller: the number the screen shows and the number
    #: the rule used must be the same one.
    outstanding_after: Decimal


def _total_of(document_id: uuid.UUID, document_type: str) -> Decimal:
    """What the document is worth, asked of whoever owns that kind."""
    if document_type in (SALE, PURCHASE):
        return totals_of(document_id).total
    return movement_of(document_id).amount


def allocated_to(document_id: uuid.UUID) -> Decimal:
    """How much of a settled document is already answered."""
    total = Settlement.objects.filter(settled_document_id=document_id).aggregate(
        allocated=Sum("amount")
    )["allocated"]
    return Decimal(total or 0)


def allocated_from(document_id: uuid.UUID) -> Decimal:
    """How much of a movement is already spoken for."""
    total = Settlement.objects.filter(movement_document_id=document_id).aggregate(
        allocated=Sum("amount")
    )["allocated"]
    return Decimal(total or 0)


def outstanding(document_id: uuid.UUID) -> Decimal:
    """What a commercial document still has open."""
    document = get_document(document_id)
    return _total_of(document_id, document.document_type) - allocated_to(document_id)


def unallocated(document_id: uuid.UUID) -> Decimal:
    """What a movement has not yet been pointed at anything."""
    return movement_of(document_id).amount - allocated_from(document_id)


@transaction.atomic
def allocate(
    *,
    settled_document_id: uuid.UUID,
    movement_document_id: uuid.UUID,
    amount: Decimal,
    settlement_date: date | None = None,
) -> Allocation:
    """Point one movement at one document, for one amount.

    **No actor, no request id, no capability snapshot in the signature**, and their
    absence is deliberate rather than an oversight: nothing here reaches the
    Posting Engine, so there is no event to stamp with them. The audit trail takes
    the actor from the context, like every other recorded act. They come back with
    the emission, when settlement crosses currencies (`OD-127`).
    """
    if amount <= 0:
        raise SettlementRefusedError("a settlement clears a positive amount")

    settled = get_document(settled_document_id)
    movement = get_document(movement_document_id)

    side = SIDE_OF.get(settled.document_type)
    if side is None:
        raise NotSettleableError(
            f"{settled.document_type} has no balance to settle; the settled document is an invoice"
        )
    if movement.document_type != MOVEMENT_OF[side]:
        raise NotSettleableError(
            f"a {side} is cleared by {MOVEMENT_OF[side]}, not by {movement.document_type!r}"
        )
    if settled.company_id != movement.company_id:
        raise NotSettleableError("both documents belong to one company")
    if settled.state != "posted" or movement.state != "posted":
        raise SettlementRefusedError(
            "both documents are posted before they are matched: an unposted one has "
            "no balance yet, and matching it would answer a question nobody asked"
        )
    partner_id = settled.partner_id
    if partner_id is None:
        # The type requires a counterparty and `validate` has refused a document
        # without one -- but the column is nullable for the types that do not, and
        # a balance belongs to somebody. Narrowed here rather than assumed.
        raise SettlementRefusedError("a settled document has a counterparty")
    if partner_id != movement.partner_id:
        raise SettlementRefusedError("a movement clears the balance of its own counterparty")

    currency = functional_currency(settled.company_id)
    if settled.currency != currency or movement.currency != currency:
        # `OD-127`: a settlement across currencies is where the realised
        # differences live, and the treasury does not move foreign currency yet.
        raise SettlementRefusedError(
            f"settlement outside {currency} needs the exchange treatment, which "
            f"arrives with treasury in foreign currency"
        )

    left_on_document = outstanding(settled_document_id)
    if amount > left_on_document:
        raise OverAllocatedError(
            f"{amount} exceeds the {left_on_document} still open on this document"
        )
    left_on_movement = unallocated(movement_document_id)
    if amount > left_on_movement:
        raise OverAllocatedError(
            f"{amount} exceeds the {left_on_movement} of this movement that is not "
            f"already pointed at something"
        )

    resident = (
        sale_residence(settled_document_id)
        if side == Side.RECEIVABLE
        else purchase_residence(settled_document_id)
    )
    on = settlement_date or movement.accounting_date

    settlement = Settlement.objects.create(
        tenant_id=settled.tenant_id,
        company_id=settled.company_id,
        side=side,
        partner_id=partner_id,
        settled_document_id=settled_document_id,
        movement_document_id=movement_document_id,
        amount=amount,
        settlement_date=on,
    )

    # The trail lives in the audit log rather than in a column: who matched what
    # is the same kind of fact as who accepted an engagement, and it is kept the
    # same way. The discriminator is recorded with it, because it is what a later
    # difference would be computed against.
    record(
        action="settlement.allocated",
        entity_type="settlement",
        entity_id=settlement.id,
        old_value=None,
        new_value={
            "side": str(side),
            "settled_document_id": str(settled_document_id),
            "movement_document_id": str(movement_document_id),
            "amount": str(amount),
            "partner_resident": resident,
            "currency": currency,
        },
    )

    return Allocation(
        settlement_id=settlement.id,
        outstanding_after=left_on_document - amount,
    )
