"""The engagement state machine -- Spec A section 4.2.

The matrix is data, not a chain of ``if`` statements, for one reason: a transition
that is not in the table is refused, and adding one is a visible edit to a table
rather than a condition slipped into a branch. Every transition here has an
answer to "who may trigger it" -- and where that answer is still an open decision,
the transition refuses rather than guessing.

Terminal states are terminal. ``revoked``, ``expired`` and ``transferred`` have no
way out: resuming a relationship means a **new** engagement, so that the history
stays readable. A row that went out and came back would make "who had access in
March 2027" unanswerable.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime

from django.db import transaction

from evidenta.platform.audit.services.recording import record
from evidenta.platform.engagement.models import Engagement, EngagementStatus


class IllegalTransitionError(RuntimeError):
    """The transition is not in the matrix, or the actor may not trigger it."""

    def __init__(self, code: str, message: str) -> None:
        # A stable code, not only a message (C10). Callers branch on the code;
        # the message is for the human reading the log.
        self.code = code
        super().__init__(f"{code}: {message}")


class TenantSide:
    """Who is acting. Not a role -- a side of the relationship."""

    TENANT = "tenant"
    FIRM = "firm"
    PLATFORM = "platform"


@dataclass(frozen=True)
class Transition:
    actors: frozenset[str]
    #: Set when the transition cannot be performed yet because the rule that
    #: governs it is an open decision. Refusing is the fail-closed answer.
    blocked_by: str | None = None


#: Spec A section 4.2, verbatim. Absent pairs are refused.
TRANSITIONS: dict[tuple[str, str], Transition] = {
    (EngagementStatus.INVITED, EngagementStatus.ACTIVE): Transition(
        actors=frozenset({TenantSide.TENANT, TenantSide.FIRM})
    ),
    (EngagementStatus.INVITED, EngagementStatus.REVOKED): Transition(
        actors=frozenset({TenantSide.TENANT, TenantSide.FIRM})
    ),
    (EngagementStatus.ACTIVE, EngagementStatus.SUSPENDED): Transition(
        actors=frozenset({TenantSide.TENANT, TenantSide.FIRM, TenantSide.PLATFORM})
    ),
    (EngagementStatus.SUSPENDED, EngagementStatus.ACTIVE): Transition(
        actors=frozenset({TenantSide.TENANT, TenantSide.FIRM, TenantSide.PLATFORM})
    ),
    # The tenant may revoke at any time and without motivation -- it follows from
    # INV-7, the tenant owns the data. Whether the firm may revoke unilaterally,
    # and with what notice, is DN-14 and still open, so the firm is not listed.
    (EngagementStatus.ACTIVE, EngagementStatus.REVOKED): Transition(
        actors=frozenset({TenantSide.TENANT, TenantSide.PLATFORM})
    ),
    (EngagementStatus.SUSPENDED, EngagementStatus.REVOKED): Transition(
        actors=frozenset({TenantSide.TENANT, TenantSide.PLATFORM})
    ),
    # Only the tenant, by accepting another firm's invitation (Spec A 4.5). The
    # outgoing firm cannot hand the relationship on -- that would contradict
    # INV-7.
    (EngagementStatus.ACTIVE, EngagementStatus.TRANSFERRED): Transition(
        actors=frozenset({TenantSide.TENANT})
    ),
    # Automatic, from the date. Listed so the matrix is complete, but see
    # `mark_expired`: access already stopped without it.
    (EngagementStatus.ACTIVE, EngagementStatus.EXPIRED): Transition(
        actors=frozenset({TenantSide.PLATFORM})
    ),
}


def check_transition(current: str, target: str, actor_side: str) -> None:
    """Raise unless the matrix allows this move by this side."""
    transition = TRANSITIONS.get((current, target))
    if transition is None:
        raise IllegalTransitionError(
            "engagement.transition_not_allowed",
            f"{current!r} -> {target!r} is not a transition",
        )
    if transition.blocked_by:
        raise IllegalTransitionError(
            "engagement.transition_blocked_by_open_decision",
            f"{current!r} -> {target!r} awaits {transition.blocked_by}",
        )
    if actor_side not in transition.actors:
        raise IllegalTransitionError(
            "engagement.actor_not_allowed",
            f"{actor_side!r} may not move {current!r} -> {target!r}; "
            f"allowed: {', '.join(sorted(transition.actors))}",
        )


def invite(
    *,
    firm_id: uuid.UUID,
    client_tenant_id: uuid.UUID,
    invited_by_user_id: uuid.UUID,
    initiated_by: str,
    valid_from: date,
    valid_to: date | None = None,
    covers_all_companies: bool = False,
) -> Engagement:
    """Open an invitation. Either side may start it.

    No expiry is set on the invitation: whether one exists, and how long, is
    DN-13. An invitation is a live relationship in the meantime -- it occupies the
    slot between this firm and this tenant -- but it grants nothing.
    """
    if initiated_by not in (TenantSide.TENANT, TenantSide.FIRM):
        raise IllegalTransitionError(
            "engagement.invalid_initiator", f"{initiated_by!r} cannot initiate"
        )
    return Engagement.objects.create(
        firm_id=firm_id,
        client_tenant_id=client_tenant_id,
        status=EngagementStatus.INVITED,
        covers_all_companies=covers_all_companies,
        valid_from=valid_from,
        valid_to=valid_to,
        initiated_by=initiated_by,
        invited_by_id=invited_by_user_id,
        invited_at=datetime.now(UTC),
    )


def accept(engagement_id: uuid.UUID, accepted_by_user_id: uuid.UUID, actor_side: str) -> Engagement:
    """Accept an invitation.

    The accepting side must be the one that did *not* initiate. An invitation a
    firm both sends and accepts is not delegation, and the model would not be
    able to tell the difference later.
    """
    with transaction.atomic():
        engagement = Engagement.objects.select_for_update().get(pk=engagement_id)
        check_transition(engagement.status, EngagementStatus.ACTIVE, actor_side)

        if actor_side == engagement.initiated_by:
            raise IllegalTransitionError(
                "engagement.self_acceptance",
                "the side that invited cannot also accept",
            )

        engagement.status = EngagementStatus.ACTIVE
        engagement.accepted_at = datetime.now(UTC)
        engagement.accepted_by_id = accepted_by_user_id
        engagement.save(update_fields=["status", "accepted_at", "accepted_by", "updated_at"])
        record(
            action="engagement.accepted",
            entity_type="engagement",
            entity_id=engagement.id,
            old_value={"status": EngagementStatus.INVITED},
            new_value={"status": EngagementStatus.ACTIVE, "actor_side": actor_side},
        )
        return engagement


def suspend(engagement_id: uuid.UUID, actor_side: str) -> Engagement:
    """Cut access, keep the relationship. Reversible, unlike revocation."""
    with transaction.atomic():
        engagement = Engagement.objects.select_for_update().get(pk=engagement_id)
        check_transition(engagement.status, EngagementStatus.SUSPENDED, actor_side)
        previous = engagement.status
        engagement.status = EngagementStatus.SUSPENDED
        engagement.suspended_at = datetime.now(UTC)
        engagement.save(update_fields=["status", "suspended_at", "updated_at"])
        record(
            action="engagement.suspended",
            entity_type="engagement",
            entity_id=engagement.id,
            old_value={"status": previous},
            new_value={"status": EngagementStatus.SUSPENDED, "actor_side": actor_side},
        )
        return engagement


def resume(engagement_id: uuid.UUID, actor_side: str) -> Engagement:
    """Restore access without re-acceptance -- the relationship never ended."""
    with transaction.atomic():
        engagement = Engagement.objects.select_for_update().get(pk=engagement_id)
        check_transition(engagement.status, EngagementStatus.ACTIVE, actor_side)
        engagement.status = EngagementStatus.ACTIVE
        engagement.suspended_at = None
        engagement.save(update_fields=["status", "suspended_at", "updated_at"])
        record(
            action="engagement.resumed",
            entity_type="engagement",
            entity_id=engagement.id,
            old_value={"status": EngagementStatus.SUSPENDED},
            new_value={"status": EngagementStatus.ACTIVE, "actor_side": actor_side},
        )
        return engagement


def transfer(
    *,
    outgoing_engagement_id: uuid.UUID,
    incoming_engagement_id: uuid.UUID,
    accepted_by_user_id: uuid.UUID,
) -> Engagement:
    """Move a client to another firm. Modelled as succession, not overlap.

    ADR-018 fixes this until DN-15 closes: the outgoing engagement ends as the
    incoming one starts. Spec A 4.5 raises the option of a read-only handover
    window, which is by definition an overlap on the same modules -- when DN-15
    closes that way, the non-overlap rule gets an explicit, tested exception
    rather than a deduced one.

    Transfer does not move data. It changes a relationship.
    """
    with transaction.atomic():
        outgoing = Engagement.objects.select_for_update().get(pk=outgoing_engagement_id)
        incoming = Engagement.objects.select_for_update().get(pk=incoming_engagement_id)

        if incoming.client_tenant_id != outgoing.client_tenant_id:
            raise IllegalTransitionError(
                "engagement.transfer_across_tenants",
                "a transfer stays within one client tenant",
            )

        check_transition(outgoing.status, EngagementStatus.TRANSFERRED, TenantSide.TENANT)
        check_transition(incoming.status, EngagementStatus.ACTIVE, TenantSide.TENANT)

        # Order matters: the outgoing engagement releases its modules before the
        # incoming one claims them. Reversed, the non-overlap index refuses the
        # very transfer it exists to make orderly.
        outgoing.status = EngagementStatus.TRANSFERRED
        outgoing.transferred_to_id = incoming_engagement_id
        outgoing.save(update_fields=["status", "transferred_to", "updated_at"])

        incoming.status = EngagementStatus.ACTIVE
        incoming.accepted_at = datetime.now(UTC)
        incoming.accepted_by_id = accepted_by_user_id
        incoming.save(update_fields=["status", "accepted_at", "accepted_by", "updated_at"])

        # One act, two rows. Both entries carry the caller's request_id, so the
        # transfer is enumerable as a transfer rather than as two coincidences
        # that happened to land in the same second.
        record(
            action="engagement.transferred_out",
            entity_type="engagement",
            entity_id=outgoing.id,
            old_value={"status": EngagementStatus.ACTIVE},
            new_value={"transferred_to": str(incoming.id)},
        )
        record(
            action="engagement.transferred_in",
            entity_type="engagement",
            entity_id=incoming.id,
            old_value={"transferred_from": str(outgoing.id)},
            new_value={"status": EngagementStatus.ACTIVE},
        )
        return incoming


def mark_expired(engagement_id: uuid.UUID) -> Engagement | None:
    """Move a lapsed engagement to ``expired``, for the interface and reports.

    **Security does not depend on this running.** The predicate evaluates
    ``valid_to`` against the date, so access stopped the moment the window closed.
    This exists so the interface does not show a relationship as active when it
    grants nothing -- and it is written this way on purpose: a job that fails to
    run must not be able to leave access open.
    """
    with transaction.atomic():
        engagement = Engagement.objects.select_for_update().get(pk=engagement_id)

        # Only `active` lapses into `expired`. An invitation nobody accepted and a
        # suspended relationship are different situations with different answers,
        # and the matrix says so by not containing those pairs.
        if engagement.status != EngagementStatus.ACTIVE:
            return None
        if engagement.valid_to is None or engagement.valid_to >= date.today():
            return None

        check_transition(engagement.status, EngagementStatus.EXPIRED, TenantSide.PLATFORM)
        engagement.status = EngagementStatus.EXPIRED
        engagement.save(update_fields=["status", "updated_at"])
        return engagement
