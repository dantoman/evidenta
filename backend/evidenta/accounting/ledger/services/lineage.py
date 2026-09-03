"""The ledger's public surface for the lineage chain -- R13.

    Journal Line -> Journal Entry -> Accounting Event -> Source Document -> Source

Navigable in both directions. This module owns the first hop and its reverse;
`accounting.events` owns the next one. No module answers the whole chain, and
that is the design rather than a gap: a single resolver would have to import
every module's models, which is `D6` written as a convenience.

**Returns plain data, never model instances.** A caller handed a `JournalEntry`
would start reading fields off it, and the coupling `D6` exists to stop would
have arrived through a service instead of an import. The dataclasses below carry
identifiers and the two dates a caller needs to ask the next question -- nothing
that would tempt anyone to treat them as the row.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from evidenta.accounting.ledger.models import JournalEntry, JournalLine


@dataclass(frozen=True, slots=True)
class LineOrigin:
    """Where one line came from -- the first two hops of R13, in one read.

    ``accounting_event_id`` is here rather than behind another call because the
    caller's next question is always "and which event produced that entry": two
    hops, one query, and no reason to make the second one a round trip.
    """

    line_id: int
    journal_entry_id: uuid.UUID
    accounting_event_id: uuid.UUID
    company_id: uuid.UUID
    accounting_date: date
    document_date: date


def origin_of_line(line_id: int) -> LineOrigin | None:
    """The entry and the event a line belongs to, or None if it is not visible.

    None covers both "no such line" and "not yours" -- deliberately the same
    answer, for the reason `platform.api.lookup` states: a caller that could tell
    them apart could enumerate another tenant's identifiers.
    """
    row = (
        JournalLine.objects.filter(id=line_id)
        .values_list(
            "id",
            "journal_entry_id",
            "journal_entry__accounting_event_id",
            "company_id",
            "accounting_date",
            "document_date",
        )
        .first()
    )
    return LineOrigin(*row) if row is not None else None


def line_ids_of_entry(entry_id: uuid.UUID) -> list[int]:
    """The lines of one entry, in line order.

    The reverse hop, and the reason `journal_line` carries an index on
    ``journal_entry_id`` rather than a foreign key pointing at it: nothing points
    *at* the line table (R21), so the navigation is an index read, which is what
    Spec B section 9.1 names it.
    """
    return list(
        JournalLine.objects.filter(journal_entry_id=entry_id)
        .order_by("line_number")
        .values_list("id", flat=True)
    )


def event_id_of_entry(entry_id: uuid.UUID) -> uuid.UUID | None:
    """The accounting event an entry came from, or None if it is not visible.

    The hand-off point to `accounting.events`, which answers what the event was
    and which document it names. Kept separate from `origin_of_line` because a
    caller that starts from an entry -- a report drilling down, say -- has no line
    to start from.
    """
    return (
        JournalEntry.objects.filter(id=entry_id)
        .values_list("accounting_event_id", flat=True)
        .first()
    )


def reversal_of_entry(entry_id: uuid.UUID) -> uuid.UUID | None:
    """The posted entry that cancels this one (R14), or None while it stands.

    The other direction of ``reverses_entry``, asked as a service so that a module
    which has to know whether an entry still counts -- a revaluation whose rate
    carries forward only while its entry stands -- does not read the ledger's
    table for it (`D6`). Visibility follows the policy, as everywhere here.
    """
    return (
        JournalEntry.objects.filter(reverses_entry_id=entry_id, status="posted")
        .order_by("-posted_at")
        .values_list("id", flat=True)
        .first()
    )
