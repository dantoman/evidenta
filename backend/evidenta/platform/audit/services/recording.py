"""Recording audit events -- explicitly, from services.

No signals (C4). A signal would make the audit trail a side effect of saving a
model, which sounds convenient and has two failure modes that matter here: it
records changes nobody meant to audit, and it silently stops recording when a
write goes through a path that does not emit the signal -- bulk updates, raw SQL,
data migrations. Explicit calls are visible in the code that performs the action.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from evidenta.platform.audit.models import AuditEvent, AuditSource
from evidenta.platform.rls.context import current_context


class MissingAuditContextError(RuntimeError):
    """An audit event was recorded outside a tenant context."""


def record(
    *,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
    company_id: uuid.UUID | None = None,
    source: str = AuditSource.WEB,
    ip_address: str | None = None,
) -> AuditEvent:
    """Record one audited action, attributed to the current context.

    The actor is never a parameter. It comes from the context, because an audit
    entry whose author the caller chooses records whatever the caller prefers --
    and the database refuses it anyway: the insert policy requires
    ``actor_user_id = app.current_user_id()``.
    """
    context = current_context()
    if context is None:
        raise MissingAuditContextError(
            f"cannot record {action!r} with no tenant context: an audit entry "
            f"with no attributable actor is not evidence of anything"
        )

    return AuditEvent.objects.create(
        tenant_id=context.tenant_id,
        company_id=company_id or context.company_id,
        occurred_at=datetime.now(UTC),
        actor_user_id=context.user_id,
        actor_firm_id=context.actor_firm_id,
        request_id=context.request_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address,
        source=source,
    )
