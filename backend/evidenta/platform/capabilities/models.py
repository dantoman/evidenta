"""Capability activation -- Spec A section 1.8, R24, R25.

**An activation is an entity, not a boolean.** The common mistake is a flag on the
tenant, and V2 section 8 names what it costs: activating Inventory needs opening
quantities and costs, a valuation method and a cutover date; activating Payroll
mid-year needs each employee's cumulative figures from 1 January, or the IPC comes
out wrong. Neither is expressible as true.

So an activation carries an effective date aligned to a period boundary and an
initialisation state -- and the Posting Engine reads the *profile*, because the
same invoice is booked differently depending on what was active on its date
(R26).
"""

from __future__ import annotations

import uuid

from django.db import models

from evidenta.platform.identity.models import User
from evidenta.platform.tenancy.models import Company, Tenant

#: Capabilities that carry a legal obligation. Never paywalled, never switchable
#: (R24, V2 section 13): if a client issues invoices in Evidenta, e-Factura works
#: whatever they pay. Otherwise the product takes on responsibility for clients
#: who fail their obligations while using it.
#:
#: This is not the capability vocabulary -- that is DN-10 and still open. It is
#: only the subset the invariant names, which is decidable without it.
COMPLIANCE_CAPABILITIES = ("vat", "efactura", "statutory_reporting")


class InitialisationState(models.TextChoices):
    NOT_REQUIRED = "not_required"
    REQUIRED = "required"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"


class ActivationSource(models.TextChoices):
    PLAN = "plan"
    MANUAL = "manual"
    MIGRATION = "migration"


class CapabilityActivation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")

    # Null for tenant-level capabilities. The overlap constraint keys on
    # COALESCE(company_id, tenant_id) so one rule covers both -- see the SQL: an
    # exclusion constraint on a nullable column never conflicts, because NULL is
    # not equal to NULL, so tenant-level rows would silently be allowed to
    # duplicate.
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, db_column="company_id", null=True, blank=True
    )

    # No CHECK on the vocabulary: DN-10 is open, and V2 section 13 already implies
    # a hierarchy ("basic payroll" in Start, "full payroll" in Business) that the
    # decision has to settle. Constraining it to an invented list would close that
    # in a migration.
    capability_key = models.TextField()

    # Aligned to an accounting period boundary. Periods arrive at F1.5, so the
    # alignment is enforced in the service with a test, and moves into the
    # database when there is a period table to align against.
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    initialisation_state = models.TextField(
        choices=InitialisationState.choices, default=InitialisationState.NOT_REQUIRED
    )
    initialisation_ref = models.TextField(null=True, blank=True)

    activated_by = models.ForeignKey(
        User, on_delete=models.PROTECT, db_column="activated_by_user_id"
    )
    activated_at = models.DateTimeField()
    source = models.TextField(choices=ActivationSource.choices)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "capability_activation"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="capability_activation_period_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(initialisation_state__in=InitialisationState.values),
                name="capability_activation_state_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(source__in=ActivationSource.values),
                name="capability_activation_source_valid",
            ),
            # R24, in the database rather than in a review comment. A compliance
            # capability with an end date is a compliance capability someone
            # switched off.
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | ~models.Q(capability_key__in=COMPLIANCE_CAPABILITIES),
                name="capability_activation_compliance_never_ends",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "capability_key", "effective_from"],
                name="capability_activation_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.capability_key}@{self.effective_from}"
