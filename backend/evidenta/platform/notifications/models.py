"""In-app and email notifications -- Spec A section 5.2, task F0.6.5.

The module is marked F0 in the module map and in V2 section 10 but had no task in
section 6.1; that gap is conflict X-9, and this closes it.

**A notification stores a type and parameters, never a rendered sentence.** Two
reasons, and the second is the one that matters later. Rendering at read time
keeps the text out of the database, so correcting a wording is a deployment
rather than a migration over rows nobody can rewrite. And ADR-014 keeps Russian
as a presentation layer: a body frozen in Romanian at write time could never be
shown in another language, so the decision to defer Russian would quietly become
the decision to refuse it.

**Notifications are personal.** The policy narrows to the recipient, not just to
the tenant. A firm's user with a live engagement can reach the client's data --
that is what the engagement is for -- but reading the client administrator's own
notifications is not part of it.
"""

from __future__ import annotations

import uuid

from django.db import models


class Channel(models.TextChoices):
    IN_APP = "in_app"
    EMAIL = "email"


class DeliveryStatus(models.TextChoices):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    #: The channel exists in the model and has no transport yet -- see OD-50.
    #: A row parked here is visible and countable, which a silently dropped
    #: notification is not.
    UNAVAILABLE = "unavailable"


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    recipient_user = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, db_column="recipient_user_id"
    )

    #: The message identifier, resolved against `messages.CATALOGUE`. A key that
    #: is not in the catalogue is refused at dispatch, so a typo cannot become a
    #: notification nobody can render.
    type_key = models.TextField()

    #: Substitutions for the rendered text. **Business data does not belong
    #: here.** The in-app row is read under the recipient's own context, but the
    #: email channel will copy from it, and an email leaves the system's access
    #: control permanently -- a revoked engagement does not unsend one, and a
    #: mailbox is not covered by the tenant's retention obligations. What that
    #: means for what an email may contain is part of OD-50.
    #:
    #: Today no catalogue entry takes a substitution at all, and a test in
    #: `test_notifications.py` keeps it that way.
    params = models.JSONField(default=dict)

    company_id = models.UUIDField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notification"
        indexes = [
            # Leads with the tenant context, then the recipient: the query that
            # matters is "my unread notifications" (R22 discipline, applied here
            # because the table grows per user per event).
            models.Index(
                fields=["tenant", "recipient_user", "created_at"],
                name="notification_inbox_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.type_key} -> {self.recipient_user_id}"


class NotificationDelivery(models.Model):
    """One attempt to put a notification on one channel.

    Separate from the notification because a notification has one meaning and
    several fates: in-app delivery succeeds by existing, email can fail, be
    retried, or -- today -- have no transport at all. Collapsing them would make
    "was this delivered" a question with no single answer.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    notification = models.ForeignKey(
        "notifications.Notification",
        on_delete=models.PROTECT,
        db_column="notification_id",
        related_name="deliveries",
    )

    channel = models.TextField(choices=Channel.choices)
    status = models.TextField(choices=DeliveryStatus.choices, default=DeliveryStatus.PENDING)

    attempts = models.IntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_delivery"
        constraints = [
            models.UniqueConstraint(
                fields=["notification", "channel"], name="notification_delivery_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(channel__in=Channel.values),
                name="notification_delivery_channel_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=DeliveryStatus.values),
                name="notification_delivery_status_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "status", "created_at"],
                name="notification_delivery_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.channel}:{self.status}"
