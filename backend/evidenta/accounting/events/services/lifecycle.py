"""What happens to an event after it is emitted -- F1.3, Spec B section 1.1.

The emission service records the event; this one moves it. Three transitions,
and the shape of each is decided by who can act on the result:

* **posted** -- the engine produced an entry. Terminal for practical purposes:
  after it, only `superseded` remains reachable, and only of the status.
* **failed** -- the engine refused, with a stable code and detail. **Not
  terminal**: the fault is usually a configuration gap that a deployment closes,
  after which the same event is retried without the emitting module doing
  anything again.
* **superseded** -- a later event replaces this one. The row stays, because the
  ledger it may already have produced stays.

Why `failed` is a state rather than an exception the caller handles: an event
that failed to post is work somebody has to finish. An exception thrown into a
Celery task disappears into a log; a row with `status = 'failed'` and a
`posting_error` is a queue -- countable, filterable by code, and visible to the
person who can fix it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from django.db import transaction

from evidenta.accounting.events.models import AccountingEvent, EventStatus


class IllegalEventTransitionError(RuntimeError):
    """The transition is not in the matrix.

    Stable code (C10): callers branch on it, the message is for the log.
    """

    code = "accounting.illegal_event_transition"

    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(f"{self.code}: {current} -> {target} is not permitted")


#: The matrix, as data rather than a chain of `if`s. A transition absent here is
#: refused, and adding one is a visible edit to a table rather than a condition
#: slipped into a branch -- the same shape the engagement lifecycle uses, for the
#: same reason.
TRANSITIONS: dict[str, frozenset[str]] = {
    EventStatus.PENDING: frozenset(
        {EventStatus.POSTED, EventStatus.FAILED, EventStatus.SUPERSEDED}
    ),
    #: Retry after the configuration is fixed. Deliberate: the common cause of a
    #: failure is a missing handler or an unbound account role, and both are
    #: closed by a deployment rather than by re-emitting from the source module.
    EventStatus.FAILED: frozenset({EventStatus.POSTED, EventStatus.FAILED, EventStatus.SUPERSEDED}),
    #: Posted is where immutability starts. The database trigger enforces this
    #: too -- this table is the readable half of the same rule.
    EventStatus.POSTED: frozenset({EventStatus.SUPERSEDED}),
    EventStatus.SUPERSEDED: frozenset(),
}


def _transition(event: AccountingEvent, target: str) -> None:
    if target not in TRANSITIONS[event.status]:
        raise IllegalEventTransitionError(event.status, target)


@transaction.atomic
def mark_posted(event_id: uuid.UUID) -> AccountingEvent:
    """The engine produced an entry for this event.

    `select_for_update` because two workers picking the same event off the queue
    is the ordinary case, not the exotic one, and the second must find the state
    already changed rather than post a second entry.
    """
    event = AccountingEvent.objects.select_for_update().get(pk=event_id)
    _transition(event, EventStatus.POSTED)
    event.status = EventStatus.POSTED
    event.posted_at = datetime.now(UTC)
    event.posting_error = None
    event.save(update_fields=["status", "posted_at", "posting_error"])
    return event


@transaction.atomic
def mark_failed(
    event_id: uuid.UUID, *, code: str, detail: dict[str, Any] | None = None
) -> AccountingEvent:
    """The engine refused. The reason is recorded, not raised away.

    `code` is required and has no default. A failure recorded without one is a
    row nobody can count or filter, which is the same as no queue at all -- and
    the database refuses it anyway: `accounting_event_failed_has_reason`.
    """
    if not code:
        raise ValueError(
            "a failed event needs a stable code (C10); a failure nobody can "
            "branch on or count is not a recorded failure"
        )
    event = AccountingEvent.objects.select_for_update().get(pk=event_id)
    _transition(event, EventStatus.FAILED)
    event.status = EventStatus.FAILED
    event.posting_error = {"code": code, "detail": detail or {}}
    event.save(update_fields=["status", "posting_error"])
    return event


@transaction.atomic
def supersede(event_id: uuid.UUID) -> AccountingEvent:
    """A later event replaces this one.

    The row stays and the entry it produced stays. Correcting a posted effect is
    a storno and a re-registration (R10), never a rewrite -- superseding the
    event is bookkeeping about the *event*, not about the ledger.
    """
    event = AccountingEvent.objects.select_for_update().get(pk=event_id)
    _transition(event, EventStatus.SUPERSEDED)
    event.status = EventStatus.SUPERSEDED
    event.save(update_fields=["status"])
    return event


#: Failure codes that another attempt cannot resolve.
#:
#: An event whose period closed is refused identically on every retry -- the
#: state of a period does not change by itself. Left in the retry queue it would
#: be picked up for ever, and **silently**: a repeated failure with the same code
#: is indistinguishable from a fresh one, so the queue keeps a constant length
#: and the events that could have posted are lost among them.
#:
#: Named by stable code rather than by importing `periods`. That is what C10's
#: stable codes are for -- the coupling is a string that may not change, instead
#: of a dependency between two modules of one layer. `accounting.events` does not
#: need to know how periods work, only that these two answers are final until a
#: person acts.
BLOCKING_CODES: frozenset[str] = frozenset(
    {
        # The period closed between emission and the retry. Reopening is possible
        # while the fiscal year is open, with a reason and an audit trail -- a
        # decision, not a retry.
        "periods.period_not_open",
        # The fiscal year is closed. Not reopenable at all.
        "periods.period_locked",
    }
)


def _queue(company_id: uuid.UUID) -> Any:
    """Everything not yet posted, oldest accounting date first.

    Ordered by `accounting_date` rather than by creation: a late-arriving
    document for an earlier period should be posted before a later one, so that
    a period does not close over a gap.

    Served by the partial index `acc_event_queue_idx`, which covers only
    `pending` and `failed` -- after the first month those are a fraction of the
    table, and the queue has no business scanning an index over all of history.
    """
    return AccountingEvent.objects.filter(
        company_id=company_id,
        status__in=(EventStatus.PENDING, EventStatus.FAILED),
    ).order_by("accounting_date", "occurred_at")


def pending_queue(company_id: uuid.UUID) -> Any:
    """Work another attempt can actually finish.

    Excludes events blocked on a closed period. Retrying those changes nothing
    and hides them.
    """
    return _queue(company_id).exclude(posting_error__code__in=list(BLOCKING_CODES))


def blocked_queue(company_id: uuid.UUID) -> Any:
    """Work waiting on a person, not on another attempt.

    Separate rather than hidden. ADR-039 section 9 says a posting falls in the
    open period in which it is recorded, so an event whose period closed needs
    one of three things, and all three are decisions: re-dating it with
    `document_date` preserved, reopening the period, or superseding it so the
    source module emits a new one. Which of those the product does is open --
    what is not open is that the queue must stop pretending it will resolve
    itself.
    """
    return _queue(company_id).filter(posting_error__code__in=list(BLOCKING_CODES))
