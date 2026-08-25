"""User and Membership -- Spec A sections 1.5 and 1.6.

Not built on ``django.contrib.auth``. That is a decision, not an omission: auth
brings Group and Permission, an entire authorisation model, while the role
vocabulary is still open (DN-08). It would also create ``auth_user``,
``auth_group`` and ``auth_permission``, which do not match the ``django_*``
pattern in the RLS contract and have no tenant column -- so the model guard would
fail on them, and the easy fix would be the wrong one.
"""

from __future__ import annotations

import uuid

from django.db import models

from evidenta.platform.tenancy.models import Tenant


class GrantedVia(models.TextChoices):
    """How a company access came to exist.

    The distinction is not bookkeeping: access granted through an engagement must
    not survive the engagement, and the only way to enforce that is to know which
    rows came from where.
    """

    MEMBERSHIP = "membership"
    ENGAGEMENT = "engagement"


class MembershipStatus(models.TextChoices):
    INVITED = "invited"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REMOVED = "removed"


class User(models.Model):
    """Global identity. One accountant, one account, sixty clients.

    Has no ``tenant_id`` -- declared in infra/rls/exceptions.toml with policy
    shape ``self_row``.

    **It carries no business fields, and that is load-bearing.** The table is
    reachable outside any tenant context, so an attribute added here would leak
    between tenants without tripping a single policy. Anything specific to a
    user's relationship with a tenant belongs on Membership.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # citext in the accompanying SQL: case-insensitivity by type, so it cannot be
    # forgotten at the one place it matters -- authentication.
    email = models.TextField(unique=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    full_name = models.TextField()

    # Null when authentication is delegated (SSO, later). Authentication itself
    # is F0.3.7, blocked on DN-09.
    password_hash = models.TextField(null=True, blank=True)
    mfa_enabled = models.BooleanField(default=False)
    mfa_secret_encrypted = models.BinaryField(null=True, blank=True)

    locale = models.TextField(default="ro")

    # Deactivation cuts access to *every* tenant. There is no per-tenant kill
    # switch here; that is Membership.status.
    is_active = models.BooleanField(default=True)
    last_login_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user"
        indexes = [models.Index(fields=["is_active"], name="user_is_active_idx")]

    def __str__(self) -> str:
        return self.email


class Membership(models.Model):
    """A user's belonging to a tenant.

    Read by ``rls.has_tenant_access`` on the first access path, which is why the
    ``(user_id, status)`` index is not an optimisation: every policy evaluation
    on every tenant-scoped table goes through it.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    user = models.ForeignKey(User, on_delete=models.PROTECT, db_column="user_id")

    # No CHECK on the values, deliberately: the role vocabulary is DN-08, still
    # open. Constraining it to an invented list would close that decision in a
    # migration, where it is hardest to notice and most expensive to undo. The
    # constraint lands with the decision.
    role = models.TextField()

    status = models.TextField(choices=MembershipStatus.choices, default=MembershipStatus.INVITED)

    invited_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        db_column="invited_by_user_id",
        null=True,
        blank=True,
        related_name="memberships_invited",
    )
    invited_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    removed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "membership"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "user"],
                condition=~models.Q(status=MembershipStatus.REMOVED),
                name="membership_live_unique",
            ),
            models.CheckConstraint(
                condition=~models.Q(status=MembershipStatus.ACTIVE)
                | models.Q(accepted_at__isnull=False),
                name="membership_active_requires_acceptance",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=MembershipStatus.values),
                name="membership_status_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "status"], name="membership_user_status_idx"),
            models.Index(fields=["tenant", "status"], name="membership_tenant_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}@{self.tenant_id}"


class CompanyAccess(models.Model):
    """A user's access to one company -- Spec A section 1.7.

    Exists for members of the tenant *and* for the firm's users acting through an
    engagement; ``granted_via`` tells them apart.

    Read by ``rls.has_company_access`` on every company-scoped policy, so the
    partial index on ``(user_id, company_id)`` is load-bearing rather than an
    optimisation.

    **Membership alone is not access to a company.** A tenant may hold several
    companies and a user may be entitled to one of them; without a row here, the
    company is invisible.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Denormalised: the policy decides without joining company.
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey("tenancy.Company", on_delete=models.PROTECT, db_column="company_id")
    user = models.ForeignKey(
        User, on_delete=models.PROTECT, db_column="user_id", related_name="company_access"
    )

    # DN-08 again: no CHECK until the vocabulary is decided.
    role = models.TextField()

    granted_via = models.TextField(choices=GrantedVia.choices)
    engagement = models.ForeignKey(
        "engagement.Engagement",
        on_delete=models.PROTECT,
        db_column="engagement_id",
        null=True,
        blank=True,
    )

    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    granted_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        db_column="granted_by_user_id",
        related_name="company_access_granted",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "company_access"
        constraints = [
            # An engagement-derived grant without an engagement, or a
            # membership-derived one carrying an engagement, is a row nobody can
            # revoke correctly.
            models.CheckConstraint(
                condition=models.Q(granted_via=GrantedVia.ENGAGEMENT, engagement__isnull=False)
                | models.Q(granted_via=GrantedVia.MEMBERSHIP, engagement__isnull=True),
                name="company_access_engagement_consistency",
            ),
            models.CheckConstraint(
                condition=models.Q(granted_via__in=GrantedVia.values),
                name="company_access_granted_via_valid",
            ),
            models.UniqueConstraint(
                fields=["company", "user", "granted_via"],
                condition=models.Q(revoked_at__isnull=True),
                name="company_access_live_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "company"],
                condition=models.Q(revoked_at__isnull=True),
                name="company_access_live_idx",
            ),
            models.Index(
                fields=["engagement"],
                condition=models.Q(revoked_at__isnull=True),
                name="company_access_engagement_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}@{self.company_id}"
