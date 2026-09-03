"""Revaluing the monetary items in foreign currency at a reporting date -- `A10`.

The service around the pure handler in `posting.services.revaluation`. It
gathers what is open (through the providers of `monetary_items`), applies the
standard's perimeter, resolves the two rates every item needs, hands the facts
to the engine, and writes the row the entry names as its source document.

**The perimeter is the act's** (SNC "Diferenţe de curs valutar şi de sumă", in
the wording in force from 01.01.2020):

* pct. 11 -- monetary items in foreign currency are recalculated at the
  reporting date; receivables and payables among them, advances excluded;
* pct. 22 -- receivables and payables from contracts between **residents**, in
  foreign currency or conventional units, are **not** recalculated: their
  difference is a sum difference and arises only at settlement (pct. 17-20).

So an item is in the perimeter exactly when its counterparty is not a resident.
That is the same discriminator ADR-057 reads to choose between 6226/7224 and
6227/7225, read the other way round -- and, like there, it is carried on the
document, never assumed.

**Two rates per item.** The *closing* rate is the official rate of the reporting
date (pct. 6 sub 3), asked of `rate_on` and refused when absent -- a revaluation
at a rate nobody published is an entry nobody can reproduce. The *carrying*
rate is what the balance stands at on that day: the invoice's, unless an earlier
revaluation restated it (pct. 15, Example 3 -- *after* a revaluation the next
difference is measured from the revalued rate). `carrying_rate_of` answers that
for the settlement handler's `issue_rate` too, so both differences are measured
from the same base.

**Idempotent on (company, date).** A second run returns the first revaluation.
A revaluation that must not stand is reversed through its entry (`R14`), and
while the reversal stands its rate no longer carries forward.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction

from evidenta.accounting.currency.models import Revaluation, RevaluationItem
from evidenta.accounting.currency.services.monetary_items import (
    MonetaryItem,
    open_monetary_items,
)
from evidenta.accounting.currency.services.rates import rate_on
from evidenta.accounting.ledger.services.lineage import reversal_of_entry
from evidenta.accounting.posting.services.revaluation import (
    RevaluedItem,
    post_revaluation,
    revaluation_difference,
)
from evidenta.platform.api.errors import ApiError
from evidenta.platform.tenancy.services.companies import functional_currency


class RevaluationRefusedError(ApiError):
    code = "currency.revaluation_refused"
    status = 409


@dataclass(frozen=True, slots=True)
class RevaluationView:
    """One revaluation as the screen and the API see it."""

    id: uuid.UUID
    as_of: date
    accounting_event_id: uuid.UUID
    journal_entry_id: uuid.UUID | None
    #: Whether the entry still stands, or has been cancelled (R14).
    reversed_by: uuid.UUID | None
    items: tuple[RevaluationItemView, ...]


@dataclass(frozen=True, slots=True)
class RevaluationItemView:
    document_id: uuid.UUID
    side: str
    partner_id: uuid.UUID
    currency: str
    amount_currency: Decimal
    rate_before: Decimal
    rate_after: Decimal
    difference: Decimal


@dataclass(frozen=True, slots=True)
class RevaluationResult:
    revaluation: RevaluationView
    posted_now: bool


def _is_live(revaluation: Revaluation) -> bool:
    """A revaluation carries its rate forward while its entry stands.

    One that posted nothing (no entry) is live too: it restated nothing, so
    there is nothing to cancel and nothing it changed.
    """
    if revaluation.journal_entry_id is None:
        return True
    return reversal_of_entry(revaluation.journal_entry_id) is None


def carrying_rate_of(document_id: uuid.UUID, *, before: date, default: Decimal) -> Decimal:
    """The rate the document's open balance is carried at on the eve of ``before``.

    The latest revaluation dated strictly before ``before`` whose entry still
    stands; the document's own rate when there is none. Strictly before, so a
    settlement dated the reporting day is measured from the previous base and
    the revaluation of that day sees the settlement as done -- the two never
    both restate the same balance for the same day.
    """
    rows = (
        RevaluationItem.objects.filter(document_id=document_id, revaluation__as_of__lt=before)
        .select_related("revaluation")
        .order_by("-revaluation__as_of", "-revaluation__created_at")
    )
    for row in rows:
        if _is_live(row.revaluation):
            return Decimal(row.rate_after)
    return default


def _in_perimeter(item: MonetaryItem) -> bool:
    # pct. 22: between residents nothing is recalculated at the reporting date.
    return not item.partner_resident


def _view(revaluation: Revaluation) -> RevaluationView:
    items = tuple(
        RevaluationItemView(
            document_id=row.document_id,
            side=row.side,
            partner_id=row.partner_id,
            currency=row.currency,
            amount_currency=Decimal(row.amount_currency),
            rate_before=Decimal(row.rate_before),
            rate_after=Decimal(row.rate_after),
            difference=Decimal(row.difference),
        )
        for row in RevaluationItem.objects.filter(revaluation=revaluation).order_by("side", "id")
    )
    return RevaluationView(
        id=revaluation.id,
        as_of=revaluation.as_of,
        accounting_event_id=revaluation.accounting_event_id,
        journal_entry_id=revaluation.journal_entry_id,
        reversed_by=(
            reversal_of_entry(revaluation.journal_entry_id)
            if revaluation.journal_entry_id is not None
            else None
        ),
        items=items,
    )


def list_revaluations(company_id: uuid.UUID) -> tuple[RevaluationView, ...]:
    """Every revaluation of the company, newest first."""
    return tuple(
        _view(row)
        for row in Revaluation.objects.filter(company_id=company_id).order_by(
            "-as_of", "-created_at"
        )
    )


@transaction.atomic
def revalue_monetary_items(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    as_of: date,
    actor_user_id: uuid.UUID,
    request_id: str,
    capability_snapshot: dict[str, Any],
) -> RevaluationResult:
    """Revalue what is open on ``as_of``, once.

    Refuses before anything is emitted when a rate is missing for a currency in
    the perimeter: the whole revaluation is one entry, and half of it at a rate
    with the other half refused would be a reporting date with two answers.
    """
    existing = Revaluation.objects.filter(company_id=company_id, as_of=as_of).first()
    if existing is not None:
        return RevaluationResult(_view(existing), posted_now=False)

    currency = functional_currency(company_id)
    perimeter = [item for item in open_monetary_items(company_id, as_of) if _in_perimeter(item)]
    closing_rates: dict[str, Decimal] = {}
    for item in perimeter:
        if item.currency not in closing_rates:
            closing_rates[item.currency] = rate_on(item.currency, as_of)

    facts: list[RevaluedItem] = []
    for item in perimeter:
        facts.append(
            RevaluedItem(
                document_id=item.document_id,
                document_type=item.document_type,
                side=item.side,
                partner_id=item.partner_id,
                currency=item.currency,
                amount_currency=item.amount_currency,
                carrying_rate=carrying_rate_of(
                    item.document_id, before=as_of, default=item.document_rate
                ),
                closing_rate=closing_rates[item.currency],
            )
        )

    revaluation_id = uuid.uuid4()
    posted = post_revaluation(
        tenant_id=tenant_id,
        company_id=company_id,
        revaluation_id=revaluation_id,
        as_of=as_of,
        functional_currency=currency,
        items=facts,
        actor_user_id=actor_user_id,
        request_id=request_id,
        capability_snapshot=capability_snapshot,
    )
    if not posted.posted_now:
        # The event existed from an earlier attempt that wrote no row -- the
        # transaction it ran in did not commit past the posting. Its entry is the
        # revaluation's; the row is written now, against it.
        pass
    revaluation = Revaluation.objects.create(
        id=revaluation_id,
        tenant_id=tenant_id,
        company_id=company_id,
        as_of=as_of,
        accounting_event_id=posted.accounting_event_id,
        journal_entry_id=posted.journal_entry_id,
    )
    RevaluationItem.objects.bulk_create(
        [
            RevaluationItem(
                tenant_id=tenant_id,
                company_id=company_id,
                revaluation=revaluation,
                document_id=fact.document_id,
                side=fact.side,
                partner_id=fact.partner_id,
                currency=fact.currency,
                amount_currency=fact.amount_currency,
                rate_before=fact.carrying_rate,
                rate_after=fact.closing_rate,
                difference=revaluation_difference(
                    fact.amount_currency, fact.carrying_rate, fact.closing_rate, as_of
                ),
            )
            for fact in facts
        ]
    )
    return RevaluationResult(_view(revaluation), posted_now=True)


def items_of(views: Sequence[RevaluationView]) -> list[dict[str, Any]]:
    """The wire shape, shared by the list and the creation response."""
    return [
        {
            "id": str(view.id),
            "as_of": view.as_of.isoformat(),
            "accounting_event_id": str(view.accounting_event_id),
            "journal_entry_id": (
                str(view.journal_entry_id) if view.journal_entry_id is not None else None
            ),
            "reversed_by": str(view.reversed_by) if view.reversed_by is not None else None,
            "items": [
                {
                    "document_id": str(item.document_id),
                    "side": item.side,
                    "partner_id": str(item.partner_id),
                    "currency": item.currency,
                    "amount_currency": str(item.amount_currency),
                    "rate_before": str(item.rate_before),
                    "rate_after": str(item.rate_after),
                    "difference": str(item.difference),
                }
                for item in view.items
            ],
        }
        for view in views
    ]
