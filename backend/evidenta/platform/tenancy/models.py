"""Tenant and Company -- Spec A sections 1.1 and 1.2.

Models hold structure and constraints; services hold logic (C2). Nothing here
filters by tenant: that is RLS's job, and a manager that filtered would create a
false sense of safety while hiding a missing context (C3).
"""

from __future__ import annotations

import uuid

from django.db import models


class TenantStatus(models.TextChoices):
    """Declared at module level, not nested.

    Django evaluates ``class Meta`` while the model class body is still running,
    so a nested choices class is not in scope for a constraint that references
    it -- and the failure is an import error, not a check error.
    """

    ACTIVE = "active"
    SUSPENDED = "suspended"
    OFFBOARDING = "offboarding"
    ARCHIVED = "archived"


class CompanyStatus(models.TextChoices):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class Tenant(models.Model):
    """The SaaS customer. Owner of the data. The root of tenancy.

    Has no ``tenant_id``: it is the root. Declared in infra/rls/exceptions.toml
    with policy shape ``tenant_predicate``.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # citext: comparison is case-insensitive by type, not by lower() sprinkled
    # through queries -- which gets forgotten exactly where it matters.
    subdomain = models.TextField(unique=True)
    legal_name = models.TextField()
    status = models.TextField(choices=TenantStatus.choices, default=TenantStatus.ACTIVE)
    default_locale = models.TextField(default="ro")

    # Administrative contact. Carries no rights -- being someone's contact is not
    # a form of access; that is Membership.
    primary_contact = models.ForeignKey(
        "identity.User",
        on_delete=models.SET_NULL,
        db_column="primary_contact_user_id",
        null=True,
        blank=True,
        related_name="primary_contact_for",
    )

    suspended_at = models.DateTimeField(null=True, blank=True)
    offboarding_started_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tenant"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=TenantStatus.values),
                name="tenant_status_valid",
            ),
        ]
        indexes = [models.Index(fields=["status"], name="tenant_status_idx")]

    def __str__(self) -> str:
        return self.subdomain


class Company(models.Model):
    """The legal entity with its own ledger. A tenant may hold several.

    Accounting is company-scoped without exception (V2 section 4.3), so this is
    the anchor every accounting table points at.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")

    # A code, not a name: byte ordering, per C34 / ADR-015. The COLLATE is applied
    # in the accompanying SQL -- Django has no field-level collation for this.
    idno = models.TextField()
    legal_name = models.TextField()
    short_name = models.TextField(null=True, blank=True)
    legal_form = models.TextField(null=True, blank=True)

    functional_currency = models.CharField(max_length=3, default="MDL")
    fiscal_year_start_month = models.SmallIntegerField(default=1)

    # Posting before this date is refused by the engine. Not a display preference.
    accounting_start_date = models.DateField()

    #: The two classifier codes every statutory return carries in its header:
    #: the administrative-territorial unit and the economic activity. Nullable
    #: because neither classifier is in this repository -- the row exists, the
    #: value arrives when somebody enters it, and a declaration generated
    #: meanwhile says so rather than inventing one. Codes, so `COLLATE "C"` in
    #: the accompanying SQL (`C34`).
    cuatm_code = models.TextField(null=True, blank=True)
    caem_code = models.TextField(null=True, blank=True)

    status = models.TextField(choices=CompanyStatus.choices, default=CompanyStatus.ACTIVE)
    registered_address = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "company"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "idno"], name="company_idno_unique"),
            models.CheckConstraint(
                condition=models.Q(fiscal_year_start_month__gte=1)
                & models.Q(fiscal_year_start_month__lte=12),
                name="company_fiscal_year_start_month_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=CompanyStatus.values),
                name="company_status_valid",
            ),
        ]
        indexes = [models.Index(fields=["tenant", "status"], name="company_tenant_status_idx")]

    def __str__(self) -> str:
        return self.legal_name


class CompanyVatRegistration(models.Model):
    """VAT registration is state with an effective date, not a boolean.

    A company registers and can be struck off during the year. Recalculating a
    past period must use the status valid then (R18) -- which a boolean cannot
    express.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")

    vat_code = models.TextField()
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    source = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "company_vat_registration"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(valid_to__isnull=True)
                | models.Q(valid_to__gt=models.F("valid_from")),
                name="company_vat_registration_period_valid",
            ),
        ]

    def __str__(self) -> str:
        return self.vat_code
