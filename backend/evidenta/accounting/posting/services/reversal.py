"""Storno through the engine -- `R10`, `R14`, ADR-006, ADR-038 section 7.2.

`ledger.services.reversal` has known how to mirror a posted entry since F1.2, and
nothing called it. So the ledger could cancel an entry and the product could not:
a manual note posted with the wrong account was, until this file, uncorrectable
except by someone with a database session -- which is the one correction `R10`
exists to prevent.

**The type is derived, not chosen.** ADR-038 section 7.2 fixes the convention as
`*.reversed`: every reversible type has its pair. So the reversal of
`manual.journal_entry` is `manual.journal_entry_reversed`, and this service reads
the original event's type rather than naming one -- which is what makes it work
for the sales invoice and the payroll run when those arrive, without a second
storno path to keep in step.

**Why the handler needs no treatment selection.** A reversal mirrors the lines the
original actually produced. It does not recompute them, so no capability profile
and no fiscal parameter enters into it -- and *that* is the property worth having:
a company that gains a capability in June cannot, by correcting a March entry,
post a March correction under June's rules (`R18`). The handler is the ledger's
own `reverse_entry` for the same reason: ADR-038 says the handler inverts the
signs, and the signs are inverted in exactly one place.

**Which date the reversal carries is not decided here.** ADR-007 is `Propus` with
three questions of accounting treatment open. The caller passes `accounting_date`;
the period follows from it deterministically, so deriving the period is not a
guess -- choosing the date would be, and this service does not.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from django.db import transaction

from evidenta.accounting.events.registry import HANDLERS, EventType, HandlerVersion, register
from evidenta.accounting.events.services.emission import emit
from evidenta.accounting.events.services.lifecycle import mark_failed, mark_posted
from evidenta.accounting.events.services.lineage import EventOrigin, origin_of_event
from evidenta.accounting.ledger.services.lineage import event_id_of_entry
from evidenta.accounting.ledger.services.reversal import reverse_entry
from evidenta.accounting.ledger.services.writing import entry_id_of_event
from evidenta.accounting.periods.services.resolution import assert_postable
from evidenta.accounting.posting.resolution import selected_treatment
from evidenta.platform.api.errors import ApiError
from evidenta.platform.numbering.services.allocation import NumberingError, allocate

#: The suffix ADR-038 section 7.2 fixes -- attached to the **action**, not as a
#: third segment.
#:
#: Section 7.2 writes the convention as `*.reversed`, which reads like a segment
#: appended to the type. It cannot be: Spec B section 1.4 fixes an event type as
#: `<domain>.<action>` and the registry enforces it with a two-segment pattern, so
#: `manual.journal_entry.reversed` is refused at registration. The only reading
#: that satisfies both is the pair formed inside the action --
#: `<domain>.<action>_reversed` -- and that is what this is. Measured by writing
#: the other one first and watching `register()` refuse it.
#:
#: Written once, here, because a second spelling of it elsewhere is a type that
#: silently never resolves.
REVERSAL_SUFFIX = "_reversed"

#: The one reversible type at F1. The pair is registered rather than derived at
#: runtime: the vocabulary is closed (ADR-038), and a type nobody registered
#: cannot be emitted -- which is the point.
ORIGINAL_EVENT_TYPE = "manual.journal_entry"
EVENT_TYPE = ORIGINAL_EVENT_TYPE + REVERSAL_SUFFIX

HANDLER_REF = "manual.journal_entry_reversed.v1"

#: Same counter as the entry it cancels. A storno that drew from its own series
#: would leave the register with two numbering schemes for one kind of document,
#: and a gap in neither is worth less than a reader who can follow one.
NUMBERING_DOCUMENT_TYPE = "journal_entry"


class ReversalPayloadError(ApiError):
    """The reversal was asked for without saying what it cancels, or why.

    A reason is required and not decorative: a storno with no reason is the
    entry an inspection asks about first, and the answer "somebody clicked it"
    is the one nobody can give a year later.
    """

    code = "posting.reversal_payload_invalid"
    status = 422


class ReversalOriginError(ApiError):
    """The entry has no traceable event, so its reversal has no type to take.

    `R13` says the chain is navigable in both directions. If it is not, the
    failure belongs here loudly rather than in a reversal posted under a guessed
    type.
    """

    code = "posting.reversal_origin_missing"
    status = 409


HANDLERS[HANDLER_REF] = reverse_entry

register(
    EventType(
        name=EVENT_TYPE,
        #: What the correction cancels, and why somebody asked for it. No lines:
        #: they are the original's, mirrored, and a payload that carried them
        #: would let a caller cancel an entry with something other than itself.
        payload_fields=("reverses_entry_id", "reason"),
        #: None, like the note it cancels. A mirror names no roles because it
        #: derives no accounts -- it uses the ones already posted.
        account_roles=(),
        handlers=(HandlerVersion(implementation_ref=HANDLER_REF, valid_from=date.min),),
        description=(
            "The cancellation of a manual journal entry: the original's lines "
            "with debit and credit swapped, linked to both the source document "
            "and the entry it cancels (R14)."
        ),
    )
)


@dataclass(frozen=True, slots=True)
class ReversalResult:
    """What the caller needs to tell a retry from a first arrival.

    Same shape and same reason as ``ManualEntryResult``: a caller that cannot
    distinguish the two notifies twice.
    """

    accounting_event_id: uuid.UUID
    journal_entry_id: uuid.UUID
    posted_now: bool


def post_reversal(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    entry_id: uuid.UUID,
    accounting_date: date,
    reason: str,
    idempotency_key: str,
    actor_user_id: uuid.UUID,
    request_id: str,
    capability_snapshot: dict[str, Any],
    corrects_period_id: uuid.UUID | None = None,
    occurred_at: datetime | None = None,
) -> ReversalResult:
    """Cancel a posted entry, through the engine, or refuse with a stable code.

    ``accounting_date`` is the date the *correction* carries -- ADR-006's second
    date. It is required and has no default: which date a reversal takes is
    ADR-007, open, and a default here would answer it from the module least able
    to argue about it.

    ``corrects_period_id`` is ADR-006's other half -- where the correction
    *belongs*, when that differs from where it posts. Left None for a correction
    inside its own open period, where the two coincide.

    ``capability_snapshot`` is carried on the event like every other, so the
    chain reads uniformly -- but nothing here consults it to build lines. See the
    module docstring: a mirror cannot drift with capabilities, and that is the
    property, not an omission.
    """
    if not reason or not reason.strip():
        raise ReversalPayloadError(
            f"reversing entry {entry_id} needs a reason. It is the only part of a "
            f"storno that a reader cannot reconstruct from the ledger itself"
        )

    origin = _origin_of(entry_id)
    event_type = origin.event_type + REVERSAL_SUFFIX

    # Refuses here if no implementation is valid on this date: the reversal of a
    # type whose pair nobody registered must not reach the ledger under a name
    # the vocabulary does not know (ADR-038).
    treatment = selected_treatment(event_type, accounting_date, capability_snapshot)

    payload = {"reverses_entry_id": str(entry_id), "reason": reason.strip()}

    event, created = emit(
        tenant_id=tenant_id,
        company_id=company_id,
        event_type=event_type,
        source_module=origin.source_module,
        #: The same document as the original. A correction does not invent a
        #: document; it says something further about the one already there, and
        #: `R13`'s chain reads the same from either entry.
        source_document_type=origin.source_document_type,
        source_document_id=origin.source_document_id,
        occurred_at=occurred_at or datetime.now(UTC),
        accounting_date=accounting_date,
        idempotency_key=idempotency_key,
        payload=payload,
        capability_snapshot=capability_snapshot,
        actor_user_id=actor_user_id,
        request_id=request_id,
    )

    if not created:
        settled = entry_id_of_event(event.id)
        if settled is not None:
            return ReversalResult(event.id, settled, posted_now=False)
        # Emitted and never posted: a previous attempt that died after the event
        # landed. Finishing it is why `failed` is not terminal.

    try:
        with transaction.atomic():
            reversal_entry_id = _write(
                event_id=event.id,
                entry_id=entry_id,
                tenant_id=tenant_id,
                company_id=company_id,
                accounting_date=accounting_date,
                reason=reason.strip(),
                request_id=request_id,
                actor_user_id=actor_user_id,
                corrects_period_id=corrects_period_id,
                rule_ref=treatment.ref,
            )
    except (ApiError, NumberingError) as refusal:
        mark_failed(event.id, code=refusal.code, detail={"event_type": event_type})
        raise

    mark_posted(event.id)
    return ReversalResult(event.id, reversal_entry_id, posted_now=True)


def _origin_of(entry_id: uuid.UUID) -> EventOrigin:
    """The original's event, which is where the reversal's type comes from."""
    event_id = event_id_of_entry(entry_id)
    if event_id is None:
        raise ReversalOriginError(
            f"entry {entry_id} is not visible in this context, or names no "
            f"accounting event; a reversal takes its type from the original's"
        )
    origin = origin_of_event(event_id)
    if origin is None:
        raise ReversalOriginError(
            f"event {event_id} behind entry {entry_id} is not visible; without it "
            f"the reversal has no source document to point at (R13)"
        )
    return origin


def _write(
    *,
    event_id: uuid.UUID,
    entry_id: uuid.UUID,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    accounting_date: date,
    reason: str,
    request_id: str,
    actor_user_id: uuid.UUID,
    corrects_period_id: uuid.UUID | None,
    rule_ref: str,
) -> uuid.UUID:
    """Check the period, take a number, hand it to the ledger.

    The order is the same contract the manual note keeps and for the same reason:
    the number is allocated last, because allocation consumes one and a refusal
    after it leaves a permanent gap for a correction that never happened.

    The period is only *checked* here -- `R12` is enforced by the database on the
    way in, and this exists so the refusal carries a stable code instead of
    arriving as a trigger message.
    """
    period = assert_postable(company_id, accounting_date)
    number = allocate(tenant_id, company_id, NUMBERING_DOCUMENT_TYPE, accounting_date)

    reversal = reverse_entry(
        entry_id,
        accounting_event_id=event_id,
        period_id=period.id,
        accounting_date=accounting_date,
        entry_number=number.formatted,
        request_id=request_id,
        rule_ref=rule_ref,
        posted_by_user_id=actor_user_id,
        corrects_period_id=corrects_period_id,
        description=reason,
    )
    return reversal.id
