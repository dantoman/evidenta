"""What happened to one document, written down as it happens.

Explicit calls from the services that perform the action, never a signal (`C4`).
A signal would record changes nobody meant to record and would silently stop
recording the moment a write went through a path that does not emit one -- a bulk
import, raw SQL, a data migration.

Two trails, deliberately not one:

* ``audit_event`` answers *who did what in the system* and is read by an
  administrator across modules;
* ``document_event`` answers *what happened to this document* and is read from
  the document itself.

Merging them would make the largest table in the system the answer to both
questions, and the drill-down from one invoice would scan it.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from evidenta.platform.documents.models import Document, DocumentEvent
from evidenta.platform.rls.context import TenantContext, current_context


class MissingDocumentContextError(RuntimeError):
    """A document event was recorded outside a tenant context.

    The database refuses it as well -- the insert policy requires
    ``actor_user_id = app.current_user_id()`` -- so this is the message rather
    than the guarantee.
    """


def require_context() -> TenantContext:
    context = current_context()
    if context is None:
        raise MissingDocumentContextError(
            "the document layer needs a tenant context: an entry with no "
            "attributable actor is not evidence of anything"
        )
    return context


def record_event(
    document: Document,
    *,
    event_type: str,
    from_state: str | None = None,
    to_state: str | None = None,
    detail: dict[str, Any] | None = None,
) -> DocumentEvent:
    """One line of the document's own history.

    The actor is never a parameter. It comes from the context, because an entry
    whose author the caller chooses records whatever the caller prefers.
    """
    context = require_context()
    return DocumentEvent.objects.create(
        tenant_id=context.tenant_id,
        company_id=document.company_id,
        document_id=document.id,
        occurred_at=datetime.now(UTC),
        event_type=event_type,
        from_state=from_state,
        to_state=to_state,
        actor_user_id=context.user_id,
        request_id=context.request_id,
        detail=detail,
    )


def history_of(document_id: uuid.UUID) -> list[DocumentEvent]:
    """The document's states in the order they happened.

    Ordered by `occurred_at` and then by `id`: two events recorded in the same
    transaction share a timestamp to the microsecond often enough that the
    ordering would otherwise be whatever the plan returned.
    """
    return list(DocumentEvent.objects.filter(document_id=document_id).order_by("occurred_at", "id"))
