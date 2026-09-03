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
emits nothing. **Across currencies** (ADR-097, closing `OD-127`) the event is
emitted with the denomination the document carries: a movement in lei settling
an invoice in another currency is worth, in that currency, its lei at the
official rate of the settlement day (SNC "Diferenţe de curs valutar şi de
sumă" pct. 8, pct. 19 sub 1 and pct. 20), and the difference between that and
what the invoice was carried at is the realised difference C4 posts -- on the
pair the counterparty selects. The base is the *carried* rate, not the
invoice's, when a revaluation restated the balance in between (pct. 15).

What is deliberately **not** here: a bank's own rate. The third pair of ADR-057
posts the spread against the lei account the conversion touched, which is right
when the currency arrived in a currency account and was sold from it; with a
movement already booked in lei for what the bank credited, that pair would count
the bank twice. It comes with the treasury in currency (step 5c), where the
movement carries the currency amount itself.

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
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import F, Sum
from django.db.models.functions import Coalesce

from evidenta.accounting.currency.money import rounding_for
from evidenta.accounting.currency.services.rates import rate_on
from evidenta.accounting.currency.services.revaluation import carrying_rate_of
from evidenta.accounting.posting.services.settlement import (
    PAYABLE,
    RECEIVABLE,
    SettlementFact,
    post_settlement_differences,
)
from evidenta.fiscal.parameters.services.scales import amount_scale
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


class SettlementContextRequiredError(ApiError):
    """A settlement across currencies posts, and a posting needs the actor, the
    request and the capability profile. Refused before anything is written."""

    code = "settlements.context_required"
    status = 400


@dataclass(frozen=True, slots=True)
class Allocation:
    settlement_id: uuid.UUID
    #: What remains on the settled document after this allocation, **in the
    #: document's currency**. Returned rather than recomputed by the caller: the
    #: number the screen shows and the number the rule used must be the same one.
    outstanding_after: Decimal
    #: The document's currency and how much of it this settled. In the
    #: functional currency both restate the amount.
    currency: str
    amount_currency: Decimal
    #: The entry of the realised difference, when the settlement crossed
    #: currencies and one arose; None otherwise.
    journal_entry_id: uuid.UUID | None = None


def _total_of(document_id: uuid.UUID, document_type: str) -> Decimal:
    """What the document is worth, asked of whoever owns that kind."""
    if document_type in (SALE, PURCHASE):
        return totals_of(document_id).total
    return movement_of(document_id).amount


def allocated_to(document_id: uuid.UUID) -> Decimal:
    """How much of a settled document is already answered, in its own currency."""
    total = Settlement.objects.filter(settled_document_id=document_id).aggregate(
        allocated=Sum(Coalesce(F("amount_currency"), F("amount")))
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
    actor_user_id: uuid.UUID | None = None,
    request_id: str | None = None,
    capability_snapshot: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> Allocation:
    """Point one movement at one document, for one amount -- the movement's.

    ``amount`` is in the movement's currency, which is the functional one. Inside
    the functional currency nothing reaches the Posting Engine, and the three
    posting arguments are not needed: the audit trail takes the actor from the
    context, like every other recorded act. Across currencies they are required,
    because the realised difference is a posting (ADR-097).
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
    if movement.currency != currency:
        # The treasury moves the functional currency only (ADR-073 section 5); a
        # movement in another currency is step 5c's, with the bank's rate.
        raise SettlementRefusedError(
            f"a movement outside {currency} needs the treasury in foreign currency, "
            f"which is not built"
        )
    on = settlement_date or movement.accounting_date

    crosses = settled.currency != currency
    if crosses:
        # pct. 8, 19 sub 1: the lei that arrived are worth, in the document's
        # currency, their amount at the official rate of the settlement day.
        # Reduced once to the scale in force, with the rule in force (R17).
        settlement_rate = rate_on(settled.currency, on)
        settled_currency = rounding_for(on).quantize(amount / settlement_rate, amount_scale(on))
        if settled_currency <= 0:
            raise SettlementRefusedError(
                f"{amount} {currency} is worth nothing in {settled.currency} at the scale in force"
            )
    else:
        settlement_rate = None
        settled_currency = amount

    left_on_document = outstanding(settled_document_id)
    if settled_currency > left_on_document:
        raise OverAllocatedError(
            f"{settled_currency} {settled.currency} exceeds the {left_on_document} still "
            f"open on this document"
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

    # R19: the same request twice is one settlement. Checked before the row and
    # again by the constraint, so two arrivals racing each other cannot both
    # allocate -- the loser reads the winner's row and answers with it.
    if idempotency_key is not None:
        earlier = Settlement.objects.filter(
            company_id=settled.company_id, idempotency_key=idempotency_key
        ).first()
        if earlier is not None:
            return _replayed(earlier, settled_document_id)

    try:
        with transaction.atomic():
            settlement = _create_settlement(
                settled=settled,
                side=side,
                partner_id=partner_id,
                settled_document_id=settled_document_id,
                movement_document_id=movement_document_id,
                amount=amount,
                on=on,
                crosses=crosses,
                settled_currency=settled_currency,
                settlement_rate=settlement_rate,
                idempotency_key=idempotency_key,
            )
    except IntegrityError:
        if idempotency_key is None:
            raise
        winner = Settlement.objects.filter(
            company_id=settled.company_id, idempotency_key=idempotency_key
        ).first()
        if winner is None:
            raise
        return _replayed(winner, settled_document_id)

    journal_entry_id: uuid.UUID | None = None
    if crosses:
        if actor_user_id is None or request_id is None or capability_snapshot is None:
            raise SettlementContextRequiredError(
                "a settlement across currencies posts the realised difference, and a "
                "posting needs the actor, the request and the capability profile"
            )
        denomination = settled.contract_denomination
        if denomination is None:
            # Opened before the column existed. Refused rather than assumed, for
            # the reason ADR-057 section 2.2 gives: the value picks the pair.
            raise SettlementRefusedError(
                f"document {settled_document_id} in {settled.currency} does not say "
                f"what its contract is denominated in; the pair of accounts depends "
                f"on it and it is not assumed"
            )
        assert settlement_rate is not None
        posted = post_settlement_differences(
            tenant_id=settled.tenant_id,
            company_id=settled.company_id,
            functional_currency=currency,
            fact=SettlementFact(
                settlement_id=settlement.id,
                document_id=settled_document_id,
                document_type=settled.document_type,
                side=RECEIVABLE if side == Side.RECEIVABLE else PAYABLE,
                currency=settled.currency,
                amount_currency=settled_currency,
                # The rate the open balance is carried at: the header's, unless
                # a revaluation dated before this day restated it (pct. 15).
                issue_rate=carrying_rate_of(
                    settled_document_id, before=on, default=Decimal(settled.exchange_rate)
                ),
                settlement_rate=settlement_rate,
                settlement_date=on,
                rate_term=str(settled.rate_term),
                partner_resident=resident,
                contract_denomination=str(denomination),
                # An advance is refused at issuing (ADR-073 section 6), so no
                # posted sale settled here is one; a purchase has no advance
                # nature. Stated, not derived from a field that does not exist.
                settles_advance=False,
                bank_rate=None,
            ),
            actor_user_id=actor_user_id,
            request_id=request_id,
            capability_snapshot=capability_snapshot,
        )
        journal_entry_id = posted.journal_entry_id

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
            "settled_currency": settled.currency,
            "amount_currency": str(settled_currency),
            "settlement_rate": None if settlement_rate is None else str(settlement_rate),
        },
    )

    return Allocation(
        settlement_id=settlement.id,
        outstanding_after=left_on_document - settled_currency,
        currency=settled.currency,
        amount_currency=settled_currency,
        journal_entry_id=journal_entry_id,
    )


def _create_settlement(
    *,
    settled: Any,
    side: str,
    partner_id: uuid.UUID,
    settled_document_id: uuid.UUID,
    movement_document_id: uuid.UUID,
    amount: Decimal,
    on: date,
    crosses: bool,
    settled_currency: Decimal,
    settlement_rate: Decimal | None,
    idempotency_key: str | None,
) -> Settlement:
    return Settlement.objects.create(
        tenant_id=settled.tenant_id,
        company_id=settled.company_id,
        side=side,
        partner_id=partner_id,
        settled_document_id=settled_document_id,
        movement_document_id=movement_document_id,
        amount=amount,
        settlement_date=on,
        currency=settled.currency if crosses else None,
        amount_currency=settled_currency if crosses else None,
        settlement_rate=settlement_rate,
        idempotency_key=idempotency_key,
    )


def _replayed(earlier: Settlement, settled_document_id: uuid.UUID) -> Allocation:
    """The first arrival's answer, for a request that arrived again (R19).

    The entry of a realised difference is not repeated here: the event's own
    key already answered it once, and `operations` does not read the ledger
    (`D3`). A caller that needs it follows the settlement's event.
    """
    return Allocation(
        settlement_id=earlier.id,
        outstanding_after=outstanding(settled_document_id),
        currency=earlier.currency or functional_currency(earlier.company_id),
        amount_currency=earlier.amount_currency
        if earlier.amount_currency is not None
        else earlier.amount,
        journal_entry_id=None,
    )
