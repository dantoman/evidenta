"""Enumerating the effects of a session, a user, or an interval -- Spec A 9.3.

This is a functional requirement, not a by-product of auditing. The product
refuses "restore my company to Friday" (amendment B.2), and that refusal is only
honest if the alternative works: identify the effects of the interval and reverse
them coherently.

So the question this module answers is not "what happened" but "what would have
to be reversed" -- which is why it groups by ``request_id``: one request is one
act, and reversing half an act is worse than reversing none of it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from evidenta.platform.audit.models import AuditEvent
from evidenta.platform.rls.context import current_context


@dataclass(frozen=True)
class EffectGroup:
    """One request or task, and everything it did."""

    request_id: str
    started_at: datetime
    actor_user_id: uuid.UUID
    actor_firm_id: uuid.UUID | None
    events: list[AuditEvent]


def effects_in_interval(
    start: datetime,
    end: datetime,
    *,
    actor_user_id: uuid.UUID | None = None,
    company_id: uuid.UUID | None = None,
) -> list[EffectGroup]:
    """Every audited effect in ``[start, end)``, grouped by the act that caused it.

    Scoped to the current tenant by RLS, not by a filter here -- which is the
    point of C3: a filter would look like the safety and would hide its absence.
    """
    if current_context() is None:
        raise RuntimeError("effects_in_interval requires a tenant context")

    query = AuditEvent.objects.filter(occurred_at__gte=start, occurred_at__lt=end)
    if actor_user_id is not None:
        query = query.filter(actor_user_id=actor_user_id)
    if company_id is not None:
        query = query.filter(company_id=company_id)

    grouped: dict[str, list[AuditEvent]] = {}
    for event in query.order_by("occurred_at", "id"):
        grouped.setdefault(event.request_id, []).append(event)

    return [
        EffectGroup(
            request_id=request_id,
            started_at=events[0].occurred_at,
            actor_user_id=events[0].actor_user_id,
            actor_firm_id=events[0].actor_firm_id,
            events=events,
        )
        for request_id, events in sorted(grouped.items(), key=lambda item: item[1][0].occurred_at)
    ]


def history_of(entity_type: str, entity_id: uuid.UUID) -> list[AuditEvent]:
    """Everything recorded about one entity, oldest first."""
    if current_context() is None:
        raise RuntimeError("history_of requires a tenant context")
    return list(
        AuditEvent.objects.filter(entity_type=entity_type, entity_id=entity_id).order_by(
            "occurred_at", "id"
        )
    )
