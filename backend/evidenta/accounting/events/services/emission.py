"""Emitting an accounting event, idempotently -- R19, Spec B section 10.1.

The three behaviours on conflict are the whole of this module, and Spec B states
them as requirements rather than preferences:

* **same key, same payload** -> the first execution's result is returned, with no
  new effect;
* **same key, different payload** -> **error with a stable code**, and no effect.
  This is the case that signals a bug in the caller, and silence would hide it;
* **no key on an operation with a financial effect** -> refusal.

The second is the one worth dwelling on. It is tempting to treat a differing
payload as a new event, or to let the last write win. Both turn a caller's bug
into a silent divergence between what the caller believes it recorded and what
the ledger holds -- discovered, if ever, at a reconciliation months later.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime
from typing import Any

from django.db import IntegrityError, transaction

from evidenta.accounting.events.models import AccountingEvent, EventStatus


class IdempotencyConflictError(RuntimeError):
    """The same key arrived with a different payload.

    Carries a stable code (C10). Callers branch on the code; the message is for
    the human reading the log.
    """

    code = "accounting.idempotency_conflict"

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(
            f"{self.code}: idempotency key {key!r} was already used for a "
            f"different payload. Same key with different content is a caller "
            f"bug, not a new event."
        )


class MissingIdempotencyKeyError(ValueError):
    code = "accounting.idempotency_key_required"


def fingerprint(payload: dict[str, Any]) -> str:
    """A stable digest of the payload, for comparing two arrivals of one key.

    `sort_keys` because JSON object order is not semantic: the same event
    serialised by two library versions must compare equal, or a harmless
    reordering would read as a caller bug.

    `default=str` so dates and UUIDs digest rather than raise. They are compared
    as text, which is exactly what is wanted -- two arrivals differing only in how
    a date was serialised are the same event.
    """
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


@transaction.atomic
def emit(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    event_type: str,
    source_module: str,
    source_document_type: str,
    source_document_id: uuid.UUID,
    occurred_at: datetime,
    accounting_date: date,
    idempotency_key: str,
    payload: dict[str, Any],
    capability_snapshot: dict[str, Any],
    actor_user_id: uuid.UUID,
    request_id: str,
    event_version: int = 1,
) -> tuple[AccountingEvent, bool]:
    """Record an accounting event. Returns the event and whether it is new.

    The `created` flag is the point of the return shape: a caller that cannot
    tell a fresh event from a replayed one will send the notification twice.
    """
    if not idempotency_key:
        raise MissingIdempotencyKeyError(
            f"{MissingIdempotencyKeyError.code}: an operation with a financial "
            f"effect needs an idempotency key. A retry without one double-posts."
        )

    digest = fingerprint(payload)

    try:
        # A savepoint, so a losing race leaves the outer transaction usable. The
        # unique constraint is the arbiter rather than a prior SELECT: two
        # concurrent callers both pass a check-then-insert, and only the
        # constraint is atomic.
        with transaction.atomic():
            event = AccountingEvent.objects.create(
                tenant_id=tenant_id,
                company_id=company_id,
                event_type=event_type,
                event_version=event_version,
                source_module=source_module,
                source_document_type=source_document_type,
                source_document_id=source_document_id,
                occurred_at=occurred_at,
                accounting_date=accounting_date,
                idempotency_key=idempotency_key,
                payload=payload,
                capability_snapshot=capability_snapshot,
                actor_user_id=actor_user_id,
                request_id=request_id,
                status=EventStatus.PENDING,
            )
    except IntegrityError:
        existing = AccountingEvent.objects.get(
            company_id=company_id, idempotency_key=idempotency_key
        )
        if fingerprint(existing.payload) != digest:
            raise IdempotencyConflictError(idempotency_key) from None
        return existing, False

    return event, True
