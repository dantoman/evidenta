"""Revoking an engagement -- Spec A section 4.3.

Revocation cuts access instantly and erases nothing. The tenant owns the data
(INV-7); the firm's users authored some of it, and their names stay on it,
because removing them would break the lineage chain INV-9 requires.

What must happen in one transaction, and what must not.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from django.db import connection, transaction

from evidenta.platform.audit.services.recording import record
from evidenta.platform.engagement.models import Engagement, EngagementStatus
from evidenta.platform.engagement.services.lifecycle import (
    IllegalTransitionError,
    TenantSide,
    check_transition,
)
from evidenta.platform.identity.services.sessions import (
    invalidate_sessions_for_engagement,
)


class RevocationError(RuntimeError):
    """The engagement cannot be revoked from its current state."""


@dataclass(frozen=True)
class RevocationResult:
    engagement_id: uuid.UUID
    company_access_revoked: int
    sessions_ended: int = 0


#: Revocation is terminal, and reachable only from a live relationship. Getting
#: out of 'revoked' is not a transition -- resuming means a new engagement, so
#: that the history stays readable.
REVOCABLE_FROM = (
    EngagementStatus.INVITED,
    EngagementStatus.ACTIVE,
    EngagementStatus.SUSPENDED,
)


def revoke_engagement(
    engagement_id: uuid.UUID,
    revoked_by_user_id: uuid.UUID,
    reason: str | None = None,
    actor_side: str = TenantSide.TENANT,
) -> RevocationResult:
    """Revoke an engagement and every company access derived from it.

    The cascade goes through ``rls.revoke_engagement_company_access``, a narrow
    SECURITY DEFINER function, and not through the ORM. The reason is structural:
    the policy on ``company_access`` is ``user_id = app.current_user_id()``, so
    the revoking administrator cannot even see the rows they must revoke. That is
    the ``self_row`` shape applied consistently, not an oversight -- and the fix
    is a named privileged path, not a wider policy.

    Audit events are recorded here, sharing the request_id of the caller, so the
    revocation is enumerable as one act rather than as scattered rows (Spec A 9.3).

    Sessions of the firm acting for this tenant are ended in the same
    transaction. RLS already refuses their queries, so this is the usability half
    of revocation rather than the security half -- the firm's interface ends
    cleanly instead of failing one request at a time.
    """
    with transaction.atomic():
        engagement = Engagement.objects.select_for_update().get(pk=engagement_id)

        # The matrix decides, in one place, rather than a second list here that
        # would drift from it. It is also the matrix that refuses a firm revoking
        # unilaterally, because DN-14 has not decided whether it may.
        try:
            check_transition(engagement.status, EngagementStatus.REVOKED, actor_side)
        except IllegalTransitionError as illegal:
            raise RevocationError(str(illegal)) from illegal

        previous_status = engagement.status
        now = datetime.now(UTC)
        engagement.status = EngagementStatus.REVOKED
        engagement.revoked_at = now
        engagement.revoked_by_id = revoked_by_user_id
        engagement.revocation_reason = reason
        engagement.save(
            update_fields=[
                "status",
                "revoked_at",
                "revoked_by",
                "revocation_reason",
                "updated_at",
            ]
        )

        with connection.cursor() as cursor:
            cursor.execute("SELECT rls.revoke_engagement_company_access(%s)", [str(engagement_id)])
            revoked = cursor.fetchone()[0]

        sessions_ended = invalidate_sessions_for_engagement(
            engagement.client_tenant_id,
            engagement.firm_id,
            reason=f"engagement {engagement_id} revoked",
        )

        record(
            action="engagement.revoked",
            entity_type="engagement",
            entity_id=engagement_id,
            old_value={"status": previous_status},
            new_value={
                "status": EngagementStatus.REVOKED,
                "reason": reason,
                "company_access_revoked": revoked,
                "sessions_ended": sessions_ended,
            },
        )

    return RevocationResult(
        engagement_id=engagement_id,
        company_access_revoked=revoked,
        sessions_ended=sessions_ended,
    )
