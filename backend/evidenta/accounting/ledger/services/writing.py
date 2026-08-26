"""The only way rows arrive in the ledger -- R9, Spec B sections 1.2, 1.5, 1.6.

``reverse_entry`` writes the mirror of an entry that already exists. This writes
an entry that does not exist yet, from lines the Posting Engine has already
judged. Between them they are the whole write surface of the ledger, and neither
is callable from a business module: `D3` forbids `operations` from importing
`accounting.ledger` at all, and the engine is the only caller inside `accounting`.

**Nothing here validates the posting.** Not an omission -- a division of labour
stated in ADR-036 section 5.2: the *engine* refuses, so that one implementation
of the six invariants exists rather than one per writer. What is checked here is
only what would otherwise reach the database as a shape it cannot express: an
empty entry, or a dimension name no column matches. Everything else is the
engine's answer above and the database's below, and this module is the seam.

**Why the writer lives in `ledger` and not in `posting`.** `D6`: a service that
imports another module's ``models`` is the violation the rule is about, and the
dependency guard reads ``evidenta.accounting.posting`` and
``evidenta.accounting.ledger`` as two modules. So the engine hands over data and
the ledger writes its own tables -- which is also what makes the ledger's
docstring true when it says no module writes here.

**The order of the three statements is not arbitrary.**

1. the entry is created ``draft`` -- ``journal_entry_needs_open_period`` fires on
   INSERT and refuses a closed period in the database, whatever the engine
   concluded a moment earlier
2. the lines are inserted -- ``journal_line_maintains_totals`` accumulates
   ``total_debit``/``total_credit`` as they land
3. the entry flips to ``posted`` -- after which
   ``journal_entry_stays_immutable`` refuses every further change to it, and
   ``journal_line_stays_immutable`` refuses every change to its lines (R10)

The balance is verified at COMMIT by ``journal_entry_balance_at_commit``, which is
deferred because between the first line and the last the entry is unbalanced by
construction. This module therefore requires the transaction to be running with
constraints deferred, which is the default and what a request gets; it does not
set the mode itself, because a writer that quietly re-deferred every constraint in
the caller's transaction would be changing a decision that is not its own.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.db import transaction

from evidenta.accounting.coa.dimensions import DIMENSION_KEYS
from evidenta.accounting.ledger.models import (
    EntryStatus,
    EntryType,
    JournalEntry,
    JournalLine,
)
from evidenta.platform.api.errors import ApiError


class NothingToWriteError(ApiError):
    """An entry with no lines.

    The database says the same thing at COMMIT -- ``journal_entry % has no
    amount`` -- and says it as a ``check_violation`` with no stable code, from a
    deferred trigger, after the caller has returned. Refusing here costs one
    ``if`` and produces a code (C10).
    """

    code = "ledger.nothing_to_write"
    status = 409


class UnknownDimensionError(ApiError):
    """A dimension name that matches no column of ``journal_line``.

    The vocabulary is closed (ADR-029) and lives in ``coa.dimensions``. Passing a
    name outside it is a caller bug, and left unchecked it would be a silently
    ignored dimension -- a line that looks analysed and is not, which no report
    can show as odd.
    """

    code = "ledger.unknown_dimension"
    status = 400


#: ``partner`` -> ``partner_id``. The fifteen columns are named exactly this way
#: on ``journal_line``, named and generic alike, so the mapping is a suffix rather
#: than a table that could drift from the vocabulary.
_COLUMN = {key: f"{key}_id" for key in DIMENSION_KEYS}


@dataclass(frozen=True, slots=True)
class LineToWrite:
    """One journal line, in the shape the ledger stores it.

    **This is the table, not the handler contract.** What a posting handler must
    return in general is F1.4.4, blocked on the accounting questions `C1`-`C5` of
    ADR-036 section 11; nothing here answers it. These are the columns
    ``journal_line`` has, and a caller that fills them has described a row.

    ``debit`` and ``credit`` are **functional-currency** amounts. ``currency``,
    ``amount_currency`` and ``exchange_rate`` describe the transaction's own
    currency; for a domestic line they are the functional currency, the same
    number, and 1 (ADR-039 section 3). Nothing here multiplies one by the other:
    the rounding rule that would require is `DNB-08`, open.
    """

    account_id: uuid.UUID
    debit: Decimal
    credit: Decimal
    currency: str
    amount_currency: Decimal
    exchange_rate: Decimal
    accounting_date: date
    document_date: date
    rate_date: date
    description: str | None = None
    quantity: Decimal | None = None
    uom_id: uuid.UUID | None = None
    #: Keyed by the ADR-029 vocabulary -- ``partner``, ``dim_1`` -- never by
    #: column name. The engine checks which of them an account requires; this
    #: only places them.
    dimensions: Mapping[str, uuid.UUID] = field(default_factory=dict)


@transaction.atomic
def post_entry(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    entry_number: str,
    accounting_date: date,
    period_id: uuid.UUID,
    accounting_event_id: uuid.UUID,
    description: str,
    request_id: str,
    lines: Sequence[LineToWrite],
    entry_type: str = EntryType.STANDARD,
    posted_by_user_id: uuid.UUID | None = None,
    corrects_period_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Write one posted entry with its lines. Returns the entry's id.

    An id rather than the model instance, for the reason
    ``ledger.services.lineage`` gives: a caller handed a ``JournalEntry`` starts
    reading fields off it, and the coupling `D6` exists to stop would have
    arrived through a service instead of an import.

    ``period_id`` is passed in rather than resolved here, and that is the point of
    ``invariants.verify`` returning it: resolving the period twice can give two
    answers, because a month can be closed between the two reads, and the entry
    would then land in a period the engine checked as open.

    ``accounting_event_id`` has no default and cannot be omitted. Spec B section
    1.5: even a manual note has one, because two paths into the ledger means
    lineage, idempotency and effect enumeration implemented twice.
    """
    if not lines:
        raise NothingToWriteError(
            f"entry {entry_number} for company {company_id} has no lines; an entry "
            f"that records nothing is not an entry"
        )

    entry = JournalEntry.objects.create(
        tenant_id=tenant_id,
        company_id=company_id,
        entry_number=entry_number,
        accounting_date=accounting_date,
        period_id=period_id,
        entry_type=entry_type,
        accounting_event_id=accounting_event_id,
        corrects_period_id=corrects_period_id,
        description=description,
        request_id=request_id,
    )

    JournalLine.objects.bulk_create(
        [
            JournalLine(
                tenant_id=tenant_id,
                company_id=company_id,
                accounting_date=line.accounting_date,
                document_date=line.document_date,
                rate_date=line.rate_date,
                journal_entry=entry,
                line_number=number,
                account_id=line.account_id,
                debit=line.debit,
                credit=line.credit,
                currency=line.currency,
                amount_currency=line.amount_currency,
                exchange_rate=line.exchange_rate,
                quantity=line.quantity,
                uom_id=line.uom_id,
                description=line.description,
                **_dimension_columns(line.dimensions),
            )
            for number, line in enumerate(lines, start=1)
        ]
    )

    entry.status = EntryStatus.POSTED
    entry.posted_at = entry.created_at
    entry.posted_by_user_id = posted_by_user_id
    entry.save(update_fields=["status", "posted_at", "posted_by_user_id"])
    return entry.id


def _dimension_columns(dimensions: Mapping[str, uuid.UUID]) -> dict[str, uuid.UUID]:
    unknown = sorted(set(dimensions) - set(_COLUMN))
    if unknown:
        raise UnknownDimensionError(
            f"{', '.join(unknown)} is not in the closed vocabulary of ADR-029; a "
            f"dimension no column matches would be dropped, and the line would "
            f"look analysed without being it"
        )
    return {_COLUMN[key]: value for key, value in dimensions.items() if value is not None}


def entry_id_of_event(accounting_event_id: uuid.UUID) -> uuid.UUID | None:
    """The entry one event produced, or None.

    The reverse of ``lineage.event_id_of_entry``, and the question a replayed
    command asks: the idempotency key found an event that already exists, so what
    did it produce? Without it the engine cannot tell "already posted" from
    "emitted and never posted", and those need opposite actions -- return the
    first result, or finish the work.

    Kept in this module rather than in ``lineage`` because the writer is its only
    caller today; it belongs there the moment a second one appears.

    ``None`` also covers an entry that exists in another tenant, which RLS makes
    invisible rather than forbidden -- the same absence of an answer, on purpose
    (IZ-04).
    """
    return (
        JournalEntry.objects.filter(accounting_event_id=accounting_event_id)
        .values_list("id", flat=True)
        .first()
    )
