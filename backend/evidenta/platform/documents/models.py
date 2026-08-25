"""Document core -- the concepts every business document shares.

One table with a type discriminator rather than a base class per module. The
reason is not tidiness: numbering, state, attachments and history have to work
identically for an invoice and for a bank statement line, and four
implementations of "what state is this in" become four answers to the same
question within a year.

Typed modules add their own tables from F2, each linked one-to-one to a row here.
This module knows nothing about them -- accounting does not know the source
(D2), and neither does the document core.
"""

from __future__ import annotations

import uuid

from django.db import models

from evidenta.platform.identity.models import User
from evidenta.platform.tenancy.models import Company, Tenant


class DocumentState(models.TextChoices):
    """The generic lifecycle. Domain variants extend it, never replace it.

    ``Draft`` is editable and means nothing has happened. ``Confirmed`` is the
    business commitment. ``Posted`` means the accounting effect exists -- and from
    that point the document is immutable, because the ledger is (R10). ``Cancelled``
    is terminal and does **not** free the number.
    """

    DRAFT = "draft"
    CONFIRMED = "confirmed"
    POSTED = "posted"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


#: Which moves are allowed. Absent pairs are refused, as in the engagement
#: matrix, and for the same reason: adding one should be an edit to a table
#: rather than a condition slipped into a branch.
DOCUMENT_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {
        (DocumentState.DRAFT, DocumentState.CONFIRMED),
        (DocumentState.DRAFT, DocumentState.CANCELLED),
        (DocumentState.CONFIRMED, DocumentState.DRAFT),
        (DocumentState.CONFIRMED, DocumentState.POSTED),
        (DocumentState.CONFIRMED, DocumentState.CANCELLED),
        (DocumentState.POSTED, DocumentState.COMPLETED),
        # No way out of POSTED except forward. Correcting a posted document is a
        # reversal and a re-entry (R10), which produces new documents rather than
        # editing this one.
    }
)


class Document(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")

    document_type = models.TextField()

    # Allocated at confirmation, never at creation: a draft that is abandoned
    # must not consume a number. Once allocated it is never reused -- cancelling
    # leaves a gap, and a register with reassigned numbers is not a register.
    series = models.TextField(default="")
    number = models.BigIntegerField(null=True, blank=True)
    formatted_number = models.TextField(null=True, blank=True)
    fiscal_year = models.SmallIntegerField(null=True, blank=True)

    document_date = models.DateField()
    state = models.TextField(choices=DocumentState.choices, default=DocumentState.DRAFT)

    currency = models.CharField(max_length=3, default="MDL")

    # The counterparty, without a foreign key: partners live in masterdata, and a
    # key from every document to them is a cost paid on every write for an
    # integrity the service already asserts.
    partner_id = models.UUIDField(null=True, blank=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        db_column="created_by_user_id",
        related_name="documents_created",
    )
    confirmed_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        db_column="confirmed_by_user_id",
        null=True,
        blank=True,
        related_name="documents_confirmed",
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(null=True, blank=True)

    notes = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "document"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(state__in=DocumentState.values),
                name="document_state_valid",
            ),
            # A number belongs to a year and a series or to nothing. Half a
            # number is how a duplicate slips past the unique constraint.
            models.CheckConstraint(
                condition=models.Q(number__isnull=True, fiscal_year__isnull=True)
                | models.Q(number__isnull=False, fiscal_year__isnull=False),
                name="document_number_complete",
            ),
            models.CheckConstraint(
                condition=~models.Q(state=DocumentState.DRAFT) | models.Q(number__isnull=True),
                name="document_draft_has_no_number",
            ),
            # ADR-022: uniqueness in the database. A service that checks and then
            # inserts produces duplicates on the first concurrent write.
            models.UniqueConstraint(
                fields=["company", "document_type", "series", "fiscal_year", "number"],
                condition=models.Q(number__isnull=False),
                name="document_number_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "company", "document_date"], name="document_scope_idx"),
            models.Index(fields=["company", "document_type", "state"], name="document_state_idx"),
            models.Index(fields=["company", "partner_id"], name="document_partner_idx"),
        ]

    def __str__(self) -> str:
        return self.formatted_number or f"{self.document_type}:draft"


class DocumentEvent(models.Model):
    """The state history of documents -- append-only, high volume (R21, R22).

    Named in the amendment's list alongside journal lines and audit events, so it
    carries the same discipline from the first migration: no incoming foreign
    keys, ``occurred_at`` NOT NULL, bigint key, indexes leading with the tenant.

    Distinct from ``audit_event``: that records who did what across the system,
    this records what happened to one document. Merging them would make the
    largest table in the system the answer to both questions, and the drill-down
    from a document would scan it.
    """

    id = models.BigAutoField(primary_key=True)

    tenant_id = models.UUIDField()
    company_id = models.UUIDField()
    document_id = models.UUIDField()

    occurred_at = models.DateTimeField()
    event_type = models.TextField()
    from_state = models.TextField(null=True, blank=True)
    to_state = models.TextField(null=True, blank=True)

    actor_user_id = models.UUIDField()
    request_id = models.TextField()
    detail = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "document_event"
        indexes = [
            models.Index(
                fields=["tenant_id", "company_id", "occurred_at"],
                name="document_event_scope_idx",
            ),
            models.Index(fields=["document_id", "occurred_at"], name="document_event_doc_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.event_type}@{self.occurred_at:%Y-%m-%d}"
