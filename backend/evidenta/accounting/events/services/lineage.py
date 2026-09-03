"""The events module's hops in the lineage chain -- R13.

    Journal Line -> Journal Entry -> Accounting Event -> Source Document -> Source

`ledger.services.lineage` owns the first hop and its reverse; this module owns
the next one. **No module answers the whole chain**, and that is the design
rather than a gap: a single resolver would have to import every module's models,
which is `D6` written as a convenience. The caller composes.

**Where the chain honestly stops.** The last hop -- to the source document
itself -- is a pair of columns, not a joinable row. `source_document_id` carries
no foreign key by design: the document lives in the module that produced it, and
a key here would force `accounting` to know that module's schema, which is `D2`.
So this module answers *which document*, in the source module's own vocabulary,
and the source module answers *what the document is*. At F1 there are no business
modules yet, so the chain ends at the identifier -- and saying so is more useful
than pretending otherwise.

Returns plain data, never model instances, for the reason the ledger's module
gives: a caller handed an `AccountingEvent` starts reading fields off it, and the
coupling `D6` stops would have arrived through a service.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from evidenta.accounting.events.models import AccountingEvent, EventStatus


@dataclass(frozen=True, slots=True)
class EventOrigin:
    """Which document produced an event, and under what.

    `capability_snapshot` is included because R13 is about being able to explain
    a figure years later, and "which capabilities were active when this was
    resolved" is part of that explanation -- R26 makes the profile an input to
    the treatment, so an entry cannot be justified without it.
    """

    accounting_event_id: uuid.UUID
    company_id: uuid.UUID
    event_type: str
    source_module: str
    source_document_type: str
    source_document_id: uuid.UUID
    occurred_at: datetime
    accounting_date: date
    idempotency_key: str
    request_id: str
    capability_snapshot: dict[str, object]


def origin_of_event(event_id: uuid.UUID) -> EventOrigin | None:
    """The document behind one event.

    `None` for an event that does not exist **and** for one belonging to another
    tenant -- the same absence of an answer, because RLS makes the second
    invisible rather than forbidden. Distinguishing them here would be an
    enumeration oracle built by hand (IZ-04).
    """
    event = AccountingEvent.objects.filter(pk=event_id).first()
    if event is None:
        return None
    return EventOrigin(
        accounting_event_id=event.id,
        company_id=event.company_id,
        event_type=event.event_type,
        source_module=event.source_module,
        source_document_type=event.source_document_type,
        source_document_id=event.source_document_id,
        occurred_at=event.occurred_at,
        accounting_date=event.accounting_date,
        idempotency_key=event.idempotency_key,
        request_id=event.request_id,
        capability_snapshot=event.capability_snapshot,
    )


def event_ids_of_document(document_type: str, document_id: uuid.UUID) -> list[uuid.UUID]:
    """Every event a document produced, oldest first -- the reverse direction.

    R13 requires the chain to be navigable **both ways**, and this is the hop
    that makes "what did this invoice cause" answerable. A document produces more
    than one event more often than it seems: an invoice, its correction, its
    settlement.

    Served by `acc_event_source_idx` on `(source_document_type,
    source_document_id)`, which exists for exactly this query.
    """
    return list(
        AccountingEvent.objects.filter(
            source_document_type=document_type, source_document_id=document_id
        )
        .order_by("occurred_at", "created_at")
        .values_list("id", flat=True)
    )


def posted_payloads_of(
    document_type: str, document_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, dict[str, Any]]:
    """The fact each posted document was posted from -- its event's payload.

    For a reader that needs what the engine *recorded* rather than what it would
    derive again: the VAT register asks whether a purchase's VAT was deductible,
    and the answer is on the event (`vat_deductible`, ADR-089), stamped beside
    the status it was read from. Re-deriving it from today's registration table
    would be a second implementation of the rule, and one that changes when the
    registration is corrected -- exactly what ADR-088 built the stamp to prevent.

    Only **posted** events, and the latest per document if there are several: a
    failed attempt's payload describes a posting that never happened. Documents
    without a posted event are absent from the answer.
    """
    ids = list(document_ids)
    found: dict[uuid.UUID, dict[str, Any]] = {}
    rows = (
        AccountingEvent.objects.filter(
            source_document_type=document_type,
            source_document_id__in=ids,
            status=EventStatus.POSTED,
        )
        .order_by("source_document_id", "occurred_at", "created_at")
        .values("source_document_id", "payload")
    )
    for row in rows:
        payload = row["payload"]
        found[row["source_document_id"]] = dict(payload) if isinstance(payload, dict) else {}
    return found


def event_ids_of_request(request_id: str) -> list[uuid.UUID]:
    """Every event one request caused -- Spec A section 9.3.

    A different question from the one above, and worth its own function: "what
    did this invoice cause" is about a document, "what did this action cause" is
    about a moment. The second is what an audit asks when somebody says they
    pressed a button and something unexpected happened.
    """
    return list(
        AccountingEvent.objects.filter(request_id=request_id)
        .order_by("created_at")
        .values_list("id", flat=True)
    )


@dataclass(frozen=True, slots=True)
class EventSummary:
    """What a source module may know about its own event without reading the ledger."""

    id: uuid.UUID
    event_type: str
    status: str
    posted_at: datetime | None


def events_of_document(document_type: str, document_id: uuid.UUID) -> list[EventSummary]:
    """The events a document produced, oldest first, with their outcome.

    The reverse hop of `R13` for a module that owns the document and may import
    `accounting.events` but not `accounting.ledger` (`D3`): a payroll run asks
    "was I posted" and gets the event's state, which the engine keeps current.
    """
    return [
        EventSummary(
            id=row.id, event_type=row.event_type, status=row.status, posted_at=row.posted_at
        )
        for row in AccountingEvent.objects.filter(
            source_document_type=document_type, source_document_id=document_id
        ).order_by("occurred_at", "created_at")
    ]
