"""The accounting event -- Spec B section 1.1, task F1.3.1.

The layer between a business module and the ledger. R9: no business module writes
to the ledger; they emit events, and the Posting Engine turns them into entries.

**Not an append-only high-volume table in the sense of R21** -- Spec B says so
explicitly, and the consequence is that it *may* receive foreign keys. The one it
deliberately does not receive is from `source_document_id`; see below.

Idempotency lives here, not on the endpoint (R19). `UNIQUE (company_id,
idempotency_key)` is the whole mechanism: an API retry, a redelivered e-Factura,
a re-run Celery task and a re-imported bank line all converge on the same row
rather than on a second posting.
"""

from __future__ import annotations

import uuid

from django.db import models

from evidenta.platform.tenancy.models import Company, Tenant


class EventStatus(models.TextChoices):
    PENDING = "pending"
    POSTED = "posted"
    FAILED = "failed"
    #: Replaced by a later event -- the original stays, because the ledger it may
    #: already have produced stays.
    SUPERSEDED = "superseded"


class SourceModule(models.TextChoices):
    SALES = "sales"
    PURCHASES = "purchases"
    PAYROLL = "payroll"
    BANKING = "banking"
    ASSETS = "assets"
    MIGRATION = "migration"
    MANUAL = "manual"
    #: The period module acting on its own: a month or an exercise being closed
    #: (F1.5.4). Not `manual` -- nobody typed the closing chain -- and not an
    #: operational module: the source document is the period itself.
    PERIODS = "periods"
    #: Money moving -- a receipt or a payment, cash or bank (ADR-073 §5). Not
    #: `banking`, which names the *statement*: a bank feed is a different source
    #: of the same kind of fact, and it arrives with the importer. A cash receipt
    #: recorded by hand has never been near a bank, and saying it was would be
    #: false in the one column that says where a fact came from.
    TREASURY = "treasury"
    #: The production activity: the period's indirect costs allocated to the
    #: products (F1.4.4, C5). There is no production module yet; the value names
    #: the source of the fact, not an app -- `manual` would say somebody typed
    #: the split, and nobody did.
    PRODUCTION = "production"


class AccountingEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")

    #: Resolved against the registry in `accounting.events.registry` -- ADR-038.
    #: A type that is not registered cannot be emitted, and a registered type
    #: without a handler fails the boot check rather than posting to a fallback
    #: account months from now.
    event_type = models.TextField()
    event_version = models.SmallIntegerField(default=1)

    source_module = models.TextField(choices=SourceModule.choices)
    source_document_type = models.TextField()

    #: **No foreign key, deliberately.** The source document lives in the module
    #: that produced it, and a key here would force `accounting` to know that
    #: module's schema -- which is D2, the rule that says accounting does not know
    #: the source. Integrity is established by the service that emits the event,
    #: and existence is checked through the source module's public service, never
    #: through a JOIN.
    source_document_id = models.UUIDField()

    #: The economic moment. Distinct from `accounting_date`: a delivery on the
    #: 28th recorded on the 5th has two different answers to "when".
    occurred_at = models.DateTimeField()

    #: **The date that decides everything downstream**: which period the entry
    #: falls in, which fiscal parameters apply, and which version of the logic
    #: runs (R17, R18). Not `occurred_at`, and not today.
    accounting_date = models.DateField()

    #: R19. Composed per source -- the API header, the SFS document identifier,
    #: a statement line hash, `<task_name>:<task_id>` -- see Spec B section 10.1.
    idempotency_key = models.TextField()

    payload = models.JSONField()

    #: R26: the capability profile is an explicit input to the Posting Engine, so
    #: it is captured *at resolution* rather than read live. Reading it live would
    #: make a recalculation of a closed period use today's capabilities, which is
    #: the same failure R18 exists to prevent for parameters and logic.
    capability_snapshot = models.JSONField()

    status = models.TextField(choices=EventStatus.choices, default=EventStatus.PENDING)
    posted_at = models.DateTimeField(null=True, blank=True)

    #: Stable code plus detail (C10). A failed posting that recorded only a
    #: message would be a failure nobody can branch on or count.
    posting_error = models.JSONField(null=True, blank=True)

    actor_user_id = models.UUIDField()

    #: The correlator that makes "everything this action caused" enumerable --
    #: Spec A section 9.3.
    request_id = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounting_event"
        constraints = [
            #: The heart of R19.
            models.UniqueConstraint(
                fields=["company", "idempotency_key"], name="accounting_event_idempotent"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=EventStatus.values),
                name="accounting_event_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(source_module__in=SourceModule.values),
                name="accounting_event_source_module_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(status=EventStatus.POSTED) | models.Q(posted_at__isnull=False),
                name="accounting_event_posted_has_timestamp",
            ),
            #: A failure that records no reason is a failure nobody can act on.
            models.CheckConstraint(
                condition=~models.Q(status=EventStatus.FAILED)
                | models.Q(posting_error__isnull=False),
                name="accounting_event_failed_has_reason",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "company", "accounting_date"],
                name="acc_event_scope_idx",
            ),
            #: Spec A section 9.3 -- what this person did, in this company.
            models.Index(
                fields=["company", "actor_user_id", "occurred_at"],
                name="acc_event_actor_idx",
            ),
            #: Document -> effects, the reverse navigation R13 requires.
            models.Index(
                fields=["source_document_type", "source_document_id"],
                name="acc_event_source_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.event_type}@{self.accounting_date}"
