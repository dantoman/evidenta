"""Notifying somebody other than the caller -- a narrow privileged path.

The policy on `notification` narrows to the recipient: a row is visible and
insertable only by the user it is for. That is right for reading and wrong for
writing, because the whole point of a notification is that somebody else creates
it -- the client administrator is told their accountant's access was withdrawn by
the code that withdrew it, not by themselves.

So the insert goes through two SECURITY DEFINER functions, and **the judgement
lives in the SQL**: the recipient must actually be an active member of the tenant
being notified, and the caller's context must be that tenant. Putting either
check in Python would make it a condition a caller can forget, and forgetting it
means arbitrary text delivered to any user in the installation, in an inbox that
carries the product's name.

See infra/migrations/0030_notifications.up.sql.
"""

from __future__ import annotations

import json
import uuid

from django.db import connection

from evidenta.platform.rls.context import unguarded

#: Stated once. Every suspension of the query guard here is the same suspension
#: for the same reason, and a second wording would read as a second reason.
_REASON = "notifications: creating a row for another user (spec-a 5.2)"


def create_notification(
    *,
    tenant_id: uuid.UUID,
    recipient_user_id: uuid.UUID,
    type_key: str,
    params: dict[str, object],
    company_id: uuid.UUID | None = None,
) -> uuid.UUID:
    with unguarded(_REASON), connection.cursor() as cursor:
        cursor.execute(
            "SELECT rls.create_notification(%s, %s, %s, %s::jsonb, %s)",
            [tenant_id, recipient_user_id, type_key, json.dumps(params), company_id],
        )
        row = cursor.fetchone()
    return uuid.UUID(str(row[0]))


def notify_tenant_members(
    *,
    tenant_id: uuid.UUID,
    type_key: str,
    params: dict[str, object],
    company_id: uuid.UUID | None = None,
) -> list[uuid.UUID]:
    """One notification per active member of the tenant.

    The recipient list is computed in SQL rather than here, and not for speed:
    `membership` belongs to `identity`, and a service importing another module's
    models is exactly what D6 forbids. In SQL the lookup sits beside the access
    judgement that had to happen anyway.
    """
    with unguarded(_REASON), connection.cursor() as cursor:
        cursor.execute(
            "SELECT rls.notify_tenant_members(%s, %s, %s::jsonb, %s)",
            [tenant_id, type_key, json.dumps(params), company_id],
        )
        return [uuid.UUID(str(row[0])) for row in cursor.fetchall()]


def create_delivery(
    *,
    tenant_id: uuid.UUID,
    notification_id: uuid.UUID,
    channel: str,
    status: str,
) -> uuid.UUID:
    with unguarded(_REASON), connection.cursor() as cursor:
        cursor.execute(
            "SELECT rls.create_notification_delivery(%s, %s, %s, %s)",
            [tenant_id, notification_id, channel, status],
        )
        row = cursor.fetchone()
    return uuid.UUID(str(row[0]))
