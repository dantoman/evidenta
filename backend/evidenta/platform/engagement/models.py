"""Firm and Engagement -- Spec A sections 1.3 and 1.4.

The distinction that must not collapse: a holding is ``Tenant -> Company*``,
common ownership. An accounting firm is ``Firm -> Engagement* -> Tenant*``,
delegated and revocable access. Model them the same way and changing accountants
becomes a data migration over an immutable ledger, the subdomain belongs to the
accountant rather than the client, and clients are stranded if the firm closes.
"""

from __future__ import annotations

import uuid

from django.db import models

from evidenta.platform.identity.models import User
from evidenta.platform.tenancy.models import Company, Tenant


class FirmStatus(models.TextChoices):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class EngagementStatus(models.TextChoices):
    INVITED = "invited"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    EXPIRED = "expired"
    TRANSFERRED = "transferred"


class AcceptanceBasis(models.TextChoices):
    """On whose word an engagement became accepted -- ADR-081 section 3.3.

    ``client`` is somebody on the client side pressing accept. ``declared_mandate``
    is the firm stating that a service contract exists, which is how the product
    works for a client who never signs in -- the normal case, not the exception.

    The distinction is recorded and never verified: the platform checks no
    contract, and the responsibility stays with the firm. What it buys is that
    every relationship no client ever confirmed is **enumerable by one query**,
    which is the question somebody asks the first time they wonder how much of the
    base stands on declarations.
    """

    CLIENT = "client"
    DECLARED_MANDATE = "declared_mandate"


#: The vocabulary of ``module_key`` -- ADR-019.
#:
#: Business modules from the module map, never platform ones: tenancy, identity,
#: audit, documents and numbering are infrastructure. They are not delegated to a
#: firm, so they get no scope key.
#:
#: The list lives here, in one place, and is enforced by a CHECK. A key written
#: freely into a row would produce a scope that refuses nothing, because it would
#: match nothing.
#:
#: Adding a module is a migration, deliberately. The modules of F4 and F5 --
#: orders, pricing, customs, hr, crm, contracts, workflow -- are absent because
#: they do not exist yet; they arrive with the phase that builds them. So are
#: `firmspace` (the firm's own workspace, not something a client delegates),
#: `billing` and `migration` (platform operations), and `fiscal` (a cross-cutting
#: service consumed by the others, not delegable on its own).
MODULE_KEYS = (
    "masterdata",
    "accounting",
    "tax",
    "payroll",
    "sales",
    "purchases",
    "receivables",
    "payables",
    "banking",
    "cash",
    "assets",
    "statutory",
    "efactura",
    "inventory",
)

#: ``write`` includes ``read``. The levels are ordered, not independent.
PERMISSION_LEVELS = ("read", "write")

#: States in which a relationship is still alive -- not necessarily granting
#: access, but occupying the slot between a firm and a client.
LIVE_ENGAGEMENT_STATES = (
    EngagementStatus.INVITED,
    EngagementStatus.ACTIVE,
    EngagementStatus.SUSPENDED,
)


class Firm(models.Model):
    """The accounting firm. An actor in its own right, with its own tenant."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # The firm's own tenant, where it keeps its own books. UNIQUE: one tenant
    # cannot be two firms.
    tenant = models.OneToOneField(Tenant, on_delete=models.PROTECT, db_column="tenant_id")

    name = models.TextField()
    idno = models.TextField(null=True, blank=True)
    status = models.TextField(choices=FirmStatus.choices, default=FirmStatus.ACTIVE)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "firm"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=FirmStatus.values), name="firm_status_valid"
            ),
        ]
        indexes = [models.Index(fields=["status"], name="firm_status_idx")]

    def __str__(self) -> str:
        return self.name


class Engagement(models.Model):
    """The Firm -> Tenant relationship. Delegated, revocable, dated.

    Read by ``rls.has_tenant_access`` on the second access path. Validity is
    evaluated against ``current_date`` inside the predicate, so an expired
    engagement stops granting access **without any job having run**: the state
    machine exists for the interface and for reporting, not as the security
    mechanism.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    firm = models.ForeignKey(Firm, on_delete=models.PROTECT, db_column="firm_id")
    client_tenant = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        db_column="client_tenant_id",
        related_name="engagements",
    )

    status = models.TextField(choices=EngagementStatus.choices, default=EngagementStatus.INVITED)

    # True means the scope follows the tenant's companies, existing and future.
    covers_all_companies = models.BooleanField(default=False)

    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    # An invitation may start from either side.
    initiated_by = models.TextField()
    invited_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        db_column="invited_by_user_id",
        related_name="engagements_invited",
    )
    invited_at = models.DateTimeField()

    accepted_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        db_column="accepted_by_user_id",
        null=True,
        blank=True,
        related_name="engagements_accepted",
    )
    accepted_at = models.DateTimeField(null=True, blank=True)

    #: What stands behind that acceptance -- ADR-081. NOT NULL once ``accepted_at``
    #: is, which is the pairing that makes the two kinds tellable apart.
    #:
    #: **The access predicate does not read it, and that is the point.** An
    #: engagement on a declared mandate is ``active`` like any other and travels
    #: the existing second path of ``rls.has_tenant_access`` -- no branch, no new
    #: state, no cost on the hot path. A change here that the predicate has to
    #: learn about is a change that misread section 3.3.
    acceptance_basis = models.TextField(choices=AcceptanceBasis.choices, null=True, blank=True)

    #: The service contract the firm points at when it declares a mandate.
    #: Declared, unverified. A reference, so `COLLATE "C"` in the accompanying SQL
    #: (C34) -- the same treatment as any other document number.
    mandate_ref = models.TextField(null=True, blank=True)

    #: Where the claim invitation goes, and the honest weak link of the model
    #: (ADR-081 section 3.5): the platform has no address for the client, the firm
    #: has. Mandatory on a declared mandate and unverifiable -- a firm that
    #: declares a contact nobody reads makes the claim path useless for that
    #: client, and nothing here can tell.
    #:
    #: citext in the accompanying SQL, like every other email in the schema.
    claim_contact_email = models.TextField(null=True, blank=True)

    suspended_at = models.DateTimeField(null=True, blank=True)

    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        db_column="revoked_by_user_id",
        null=True,
        blank=True,
        related_name="engagements_revoked",
    )
    revocation_reason = models.TextField(null=True, blank=True)

    # Set on the outgoing engagement when the client moves to another firm.
    transferred_to = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        db_column="transferred_to_engagement_id",
        null=True,
        blank=True,
        related_name="transferred_from",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "engagement"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(valid_to__isnull=True)
                | models.Q(valid_to__gte=models.F("valid_from")),
                name="engagement_validity_ordered",
            ),
            # Active without acceptance is impossible: the relationship is
            # delegated, and delegation nobody accepted is not delegation.
            models.CheckConstraint(
                condition=~models.Q(status=EngagementStatus.ACTIVE)
                | models.Q(accepted_at__isnull=False),
                name="engagement_active_requires_acceptance",
            ),
            # An acceptance says on whose word. Without this the two kinds are
            # indistinguishable after the fact, and "how much of the base nobody
            # confirmed" stops being answerable -- which is most of what the
            # column is for (ADR-081 section 3.3).
            models.CheckConstraint(
                condition=models.Q(accepted_at__isnull=True)
                | models.Q(acceptance_basis__isnull=False),
                name="engagement_acceptance_states_its_basis",
            ),
            models.CheckConstraint(
                condition=models.Q(acceptance_basis__isnull=True)
                | models.Q(acceptance_basis__in=AcceptanceBasis.values),
                name="engagement_acceptance_basis_valid",
            ),
            # ADR-081 section 3.5 names this the weak link and makes the column
            # mandatory anyway, because it is the only channel INV-7 has. A
            # mandatory field that nothing enforces is a field that is empty on
            # exactly the rows where it matters.
            models.CheckConstraint(
                condition=~models.Q(acceptance_basis=AcceptanceBasis.DECLARED_MANDATE)
                | models.Q(claim_contact_email__isnull=False),
                name="engagement_declared_mandate_has_claim_contact",
            ),
            models.CheckConstraint(
                condition=~models.Q(status=EngagementStatus.REVOKED)
                | models.Q(revoked_at__isnull=False),
                name="engagement_revoked_requires_timestamp",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=EngagementStatus.values),
                name="engagement_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(initiated_by__in=["firm", "tenant"]),
                name="engagement_initiated_by_valid",
            ),
            # One live relationship per firm-client pair. Whether a tenant may
            # hold live engagements with *several* firms at once is DN-06, still
            # open; option A there would add a stricter constraint on top of
            # this one, not replace it.
            models.UniqueConstraint(
                fields=["firm", "client_tenant"],
                condition=models.Q(status__in=LIVE_ENGAGEMENT_STATES),
                name="engagement_live_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["client_tenant", "status"], name="engagement_client_status_idx"),
            models.Index(fields=["firm", "status"], name="engagement_firm_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.firm_id} -> {self.client_tenant_id}"


class EngagementCompanyScope(models.Model):
    """Which companies an engagement covers, when it does not cover all."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    engagement = models.ForeignKey(Engagement, on_delete=models.CASCADE, db_column="engagement_id")
    # Denormalised for RLS: the policy must decide without joining engagement.
    client_tenant = models.ForeignKey(
        Tenant, on_delete=models.PROTECT, db_column="client_tenant_id"
    )
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "engagement_company_scope"
        constraints = [
            models.UniqueConstraint(
                fields=["engagement", "company"], name="engagement_company_scope_unique"
            ),
        ]
        indexes = [models.Index(fields=["company"], name="eng_company_scope_comp_idx")]

    def __str__(self) -> str:
        return f"{self.engagement_id}:{self.company_id}"


class EngagementModuleScope(models.Model):
    """Which modules an engagement covers, and at what level."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    engagement = models.ForeignKey(Engagement, on_delete=models.CASCADE, db_column="engagement_id")

    module_key = models.TextField()
    permission_level = models.TextField()

    # Denormalised from the parent engagement, and not for convenience: the
    # non-overlap rule of ADR-018 -- at most one live engagement per tenant may
    # claim a module -- is enforced by a partial unique index, and an index can
    # only see columns on its own table.
    #
    # A trigger check would read the parent instead, and would be wrong under
    # concurrency: two transactions inserting `payroll` for two firms would each
    # see no conflict and both commit. The unique index is the only form that
    # holds without serialising every write.
    client_tenant = models.ForeignKey(
        Tenant, on_delete=models.PROTECT, db_column="client_tenant_id"
    )
    is_live = models.BooleanField(default=True)

    class Meta:
        db_table = "engagement_module_scope"
        constraints = [
            models.UniqueConstraint(
                fields=["engagement", "module_key"], name="engagement_module_scope_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(permission_level__in=PERMISSION_LEVELS),
                name="engagement_module_scope_level_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(module_key__in=MODULE_KEYS),
                name="engagement_module_scope_key_valid",
            ),
            # ADR-018: two firms cannot both hold `payroll` at the same client.
            models.UniqueConstraint(
                fields=["client_tenant", "module_key"],
                condition=models.Q(is_live=True),
                name="engagement_module_scope_no_overlap",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.engagement_id}:{self.module_key}"
