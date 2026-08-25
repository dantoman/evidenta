"""Storno -- Spec B section 9, R10, R14.

A correction is a reversal plus a re-entry. Never an ``UPDATE``: the posted
ledger is immutable, and the database enforces that whether or not this module is
involved.

**The reversal's lines are the original's with debit and credit swapped, not with
negative amounts.** A negative line breaks turnover: the month's debit turnover
would go *down* by the correction instead of up, and a trial balance would stop
showing the activity that actually happened. Spec B section 9.2 states it; the
constraint ``journal_line_one_side_only`` makes it unwriteable anyway.

**Which period a reversal posts into is not decided here.** That is ADR-007, and
it is `Propus` -- three questions of accounting treatment are unanswered. Spec B
section 9.3 says in as many words that F1.2 may be built on ADR-006's structure
while the service that *chooses* the period stays unwritten. So the caller passes
the period, and this module refuses to guess: a default here would answer an open
decision by accident, in the module least able to argue about it.
"""

from __future__ import annotations

import uuid
from datetime import date

from django.db import transaction

from evidenta.accounting.ledger.errors import (
    AlreadyReversedError,
    EntryNotFoundError,
    NotPostedError,
)
from evidenta.accounting.ledger.models import (
    EntryStatus,
    EntryType,
    JournalEntry,
    JournalLine,
)

#: Columns copied to the reversal unchanged. Everything that describes *what* was
#: recorded travels; only the two amount columns swap and the three
#: entry-level fields are the caller's.
_CARRIED = (
    "account_id",
    "currency",
    "amount_currency",
    "exchange_rate",
    "rate_date",
    "document_date",
    "quantity",
    "uom_id",
    "partner_id",
    "item_id",
    "employee_id",
    "contract_id",
    "warehouse_id",
    "project_id",
    "department_id",
    "cost_center_id",
    "asset_id",
    "production_order_id",
    "dim_1_id",
    "dim_2_id",
    "dim_3_id",
    "dim_4_id",
    "dim_5_id",
)


@transaction.atomic
def reverse_entry(
    entry_id: uuid.UUID,
    *,
    accounting_event_id: uuid.UUID,
    period_id: uuid.UUID,
    accounting_date: date,
    entry_number: str,
    request_id: str,
    posted_by_user_id: uuid.UUID | None = None,
    corrects_period_id: uuid.UUID | None = None,
    description: str | None = None,
) -> JournalEntry:
    """Cancel a posted entry with its mirror image.

    The result carries **two** links (R14): ``accounting_event`` to the event that
    asked for the correction, and ``reverses_entry`` to the entry being cancelled.
    Without the second, a drill-down on a corrected account shows two entries with
    opposite amounts and nothing saying one cancels the other.

    ``corrects_period_id`` is the ADR-006 half: where the correction *belongs*,
    when that differs from where it posts. Left None for a correction inside its
    own open period, where the two coincide.

    **The exchange rate is the original's, not today's.** The reversal has to
    cancel the same functional amount; taking a fresh rate would leave the
    difference behind as a silent balance drift -- and that difference is an
    exchange-difference event, a different economic fact with its own treatment,
    not a rounding artefact of a correction.
    """
    original = JournalEntry.objects.filter(id=entry_id).first()
    if original is None:
        raise EntryNotFoundError(f"entry {entry_id} is not visible in this context")

    if original.status != EntryStatus.POSTED:
        raise NotPostedError(
            f"entry {entry_id} is {original.status}; a draft records nothing, so "
            f"there is nothing to cancel"
        )

    if JournalEntry.objects.filter(reverses_entry_id=entry_id).exists():
        raise AlreadyReversedError(
            f"entry {entry_id} already has a reversal; a second one is a process "
            f"error, and its result is a ledger that cancels the entry twice"
        )

    reversal = JournalEntry.objects.create(
        tenant_id=original.tenant_id,
        company_id=original.company_id,
        entry_number=entry_number,
        accounting_date=accounting_date,
        period_id=period_id,
        entry_type=EntryType.REVERSAL,
        accounting_event_id=accounting_event_id,
        reverses_entry=original,
        corrects_period_id=corrects_period_id,
        description=description or f"Storno {original.entry_number}",
        request_id=request_id,
    )

    source = JournalLine.objects.filter(journal_entry_id=entry_id).order_by("line_number")
    JournalLine.objects.bulk_create(
        [
            JournalLine(
                tenant_id=original.tenant_id,
                company_id=original.company_id,
                accounting_date=accounting_date,
                journal_entry=reversal,
                line_number=line.line_number,
                # The swap. Not a negation -- see the module docstring.
                debit=line.credit,
                credit=line.debit,
                description=line.description,
                **{name: getattr(line, name) for name in _CARRIED},
            )
            for line in source
        ]
    )

    reversal.status = EntryStatus.POSTED
    reversal.posted_at = reversal.created_at
    reversal.posted_by_user_id = posted_by_user_id
    reversal.save(update_fields=["status", "posted_at", "posted_by_user_id"])
    return reversal
