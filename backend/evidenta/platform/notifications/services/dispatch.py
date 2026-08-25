"""Sending a notification. Called explicitly from services.

No signals (C4). The rule is written for financial effects, and a notification is
not one -- but the reason carries over intact: a notification that appears as a
side effect of saving a row is a notification nobody can find the origin of when
a client asks why they received it.

The dispatcher runs under the **acting user's** context, which is what makes the
row insertable at all: the policy narrows notifications to their recipient, and
inserting one for somebody else needs a path that says so. That path is
`deliver_to_tenant_members`, and it goes through a privileged function for the
same reason `company_access` did -- see `notifications/privileged.py`.
"""

from __future__ import annotations

import uuid

from django.db import transaction

from evidenta.platform.notifications import privileged
from evidenta.platform.notifications.messages import CATALOGUE, UnknownMessageError
from evidenta.platform.notifications.models import Channel, DeliveryStatus


class MissingParameterError(ValueError):
    """The catalogue entry needs a substitution the caller did not supply.

    Checked here rather than at render time. A notification missing a
    substitution would otherwise be stored successfully and fail in the
    recipient's inbox, where nobody who can fix it will ever see it.
    """


def notify_tenant(
    *,
    tenant_id: uuid.UUID,
    type_key: str,
    params: dict[str, object] | None = None,
    company_id: uuid.UUID | None = None,
    channels: tuple[str, ...] = (Channel.IN_APP,),
) -> list[uuid.UUID]:
    """Notify every active member of a tenant.

    The shape Spec A section 4.6 asks for: "notifying the affected tenants is
    mandatory, not optional". Who counts as affected is every active member,
    because losing an accountant is not an administrative detail somebody else
    can be told about later.
    """
    params = _checked(type_key, params or {})
    with transaction.atomic():
        created = privileged.notify_tenant_members(
            tenant_id=tenant_id,
            type_key=type_key,
            params=params,
            company_id=company_id,
        )
        for notification_id in created:
            _deliver(tenant_id, notification_id, channels)
    return created


def _checked(type_key: str, params: dict[str, object]) -> dict[str, object]:
    try:
        message = CATALOGUE[type_key]
    except KeyError:
        raise UnknownMessageError(
            f"{type_key!r} is not in the catalogue. A notification nobody can "
            f"render is worse than one nobody sends."
        ) from None
    missing = [name for name in message.required_params if name not in params]
    if missing:
        raise MissingParameterError(
            f"{type_key!r} needs {', '.join(missing)}; a sentence with a hole in "
            f"it reaches the recipient and nobody who can fix it sees it"
        )
    return params


def _deliver(tenant_id: uuid.UUID, notification_id: uuid.UUID, channels: tuple[str, ...]) -> None:
    for channel in channels:
        privileged.create_delivery(
            tenant_id=tenant_id,
            notification_id=notification_id,
            channel=channel,
            # The email channel has no transport yet: the sender runs without a
            # user identity, which needs a privileged path of its own, and no
            # provider is chosen. Parked as `unavailable` rather than `pending`
            # so the queue does not fill with rows that look like they are about
            # to be sent. See OD-50.
            status=(
                DeliveryStatus.SENT if channel == Channel.IN_APP else DeliveryStatus.UNAVAILABLE
            ),
        )


def notify(
    *,
    tenant_id: uuid.UUID,
    recipient_user_ids: list[uuid.UUID],
    type_key: str,
    params: dict[str, object] | None = None,
    company_id: uuid.UUID | None = None,
    channels: tuple[str, ...] = (Channel.IN_APP,),
) -> list[uuid.UUID]:
    """Notify named recipients.

    Returns the notification ids. Callers do not usually need them; the return
    exists so a test can assert on what was produced rather than on what a log
    line said.
    """
    params = _checked(type_key, params or {})
    created: list[uuid.UUID] = []
    with transaction.atomic():
        for recipient in recipient_user_ids:
            notification_id = privileged.create_notification(
                tenant_id=tenant_id,
                recipient_user_id=recipient,
                type_key=type_key,
                params=params,
                company_id=company_id,
            )
            created.append(notification_id)
            _deliver(tenant_id, notification_id, channels)
    return created
