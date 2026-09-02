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

from evidenta.platform.identity.permissions import PermissionScope
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
    # Enrolment state, not a preference: MFA is mandatory for everyone
    # (ADR-021), so this records whether the user has finished enrolling, and a
    # user who has not cannot complete authentication.
    mfa_enabled = models.BooleanField(default=False)

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


class RoleLevel(models.TextChoices):
    """Where a role applies. Membership carries a tenant role, CompanyAccess a company one.

    The values come from the catalogue rather than being repeated here: a role
    and the permissions it may hold are the same vocabulary, and two copies of it
    would drift the first time one gains a third value.
    """

    TENANT = PermissionScope.TENANT
    COMPANY = PermissionScope.COMPANY


class Permission(models.Model):
    """The fixed catalogue -- ADR-020. Global, fed from code, never by a client.

    The primary key is the key itself, and that is deliberate. This is reference
    data whose identity *is* its name: a surrogate id would add a join to answer
    "what may this role do", and would let two rows carry the same meaning the
    day someone drops the unique index. It is neither an externally exposed
    entity nor a high-volume table, so C6 does not apply.

    No label column. What a permission is called in the interface belongs in the
    frontend resource files (C32), in Romanian, not in a column that would need a
    migration to translate.
    """

    key = models.TextField(primary_key=True)
    scope = models.TextField(choices=RoleLevel.choices)

    class Meta:
        db_table = "permission"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(scope__in=RoleLevel.values), name="permission_scope_valid"
            ),
        ]

    def __str__(self) -> str:
        return self.key


class Role(models.Model):
    """A named set of permissions, owned by one tenant -- ADR-020.

    Roles are data, not code: the tenant composes them. What keeps that safe is
    that they are composed from :mod:`evidenta.platform.identity.permissions`,
    through a foreign key -- so a role can be wrong about who holds it, never
    about what exists.

    ``is_system`` marks the roles the platform creates with the tenant. They
    cannot be deleted and cannot lose ``tenant.manage_roles``; without that, the
    first client who edits their roles badly is locked out of their own tenant
    and recovery becomes a manual intervention in production.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")

    # A code, not a name: byte ordering (C34), applied in the accompanying SQL.
    key = models.TextField()
    # The display name the tenant chose. A name, so the database collation.
    name = models.TextField()

    level = models.TextField(choices=RoleLevel.choices)
    is_system = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "role"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "key"], name="role_key_unique"),
            models.CheckConstraint(
                condition=models.Q(level__in=RoleLevel.values), name="role_level_valid"
            ),
        ]
        indexes = [models.Index(fields=["tenant", "level"], name="role_tenant_level_idx")]

    def __str__(self) -> str:
        return f"{self.key}@{self.tenant_id}"


class RolePermission(models.Model):
    """One permission held by one role.

    ``tenant_id`` is denormalised so the policy decides without joining ``role``.
    It is also what the composite foreign key in the accompanying SQL uses: a row
    here cannot point at another tenant's role, and that is enforced by the
    database rather than by the service that writes it.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, db_column="role_id")
    permission = models.ForeignKey(Permission, on_delete=models.PROTECT, db_column="permission_key")

    # Denormalised, and not for speed: it lets one composite foreign key carry
    # two invariants at once -- the row belongs to the role's tenant, and the
    # permission has exactly the role's level. A tenant-level role cannot hold a
    # company permission, and the database is what refuses it. See
    # infra/migrations/0019_roles.up.sql.
    scope = models.TextField(choices=RoleLevel.choices)

    class Meta:
        db_table = "role_permission"
        constraints = [
            models.UniqueConstraint(fields=["role", "permission"], name="role_permission_unique"),
        ]
        indexes = [
            models.Index(fields=["tenant", "role"], name="role_permission_tenant_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.role_id}:{self.permission_id}"


class Membership(models.Model):
    """A user's belonging to a tenant.

    Read by ``rls.has_tenant_access`` on the first access path, which is why the
    ``(user_id, status)`` index is not an optimisation: every policy evaluation
    on every tenant-scoped table goes through it.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    user = models.ForeignKey(User, on_delete=models.PROTECT, db_column="user_id")

    # DN-08 is closed (ADR-020): the vocabulary is data, per tenant, and the
    # foreign key is what makes it safe. The accompanying SQL adds a *composite*
    # foreign key on (tenant_id, role_id) -- Django cannot express one, and
    # without it a membership could point at another tenant's role.
    role = models.ForeignKey(Role, on_delete=models.PROTECT, db_column="role_id")

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

    # A company-level role (ADR-020), tied to this tenant by the composite
    # foreign key in the accompanying SQL.
    role = models.ForeignKey(Role, on_delete=models.PROTECT, db_column="role_id")

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


class StaffRole(models.TextChoices):
    """The three roles of a platform employee -- ADR-076 §4.1, fixed in code.

    Not roles-as-data (ADR-020): those compose a *tenant's* roles from a
    catalogue scoped `tenant` or `company`, and a platform role has no tenant
    to belong to. Three values in a CHECK are honest; a fourth is a migration,
    deliberately.
    """

    #: May *request* a support grant (ADR-077). Touches no reference table.
    SUPPORT = "support"
    #: Runs the reference-data paths: fiscal parameters, rates, chart of accounts.
    OPERATOR = "operator"
    #: Administers `platform_staff` itself. Nothing else.
    ADMIN = "admin"


class PlatformStaff(models.Model):
    """Who is an employee of the platform -- ADR-076 §4.1.

    Global, at the level of ``user``: an employee of the platform belongs to no
    tenant, so the table has no ``tenant_id`` and cannot have one. Declared in
    infra/rls/exceptions.toml.

    **A row here grants nothing.** It does not appear in ``rls.has_tenant_access``
    or ``rls.has_company_access`` and opens no policy. It is a list of people,
    read by the console's doors to decide whether the caller may knock -- and by
    the login on the ``admin.`` host to decide whether to issue a session at all.

    Revocation is a date, not a deletion: who was staff when is part of the
    answer to "who could have run this path", which is the question the whole
    table exists to answer.
    """

    user = models.OneToOneField(
        User, on_delete=models.PROTECT, primary_key=True, db_column="user_id"
    )
    staff_role = models.TextField(choices=StaffRole.choices)
    granted_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        db_column="granted_by_user_id",
        related_name="platform_staff_granted",
    )
    granted_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "platform_staff"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(staff_role__in=StaffRole.values),
                name="platform_staff_role_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.staff_role}:{self.user_id}"


class MfaMethodType(models.TextChoices):
    """Second factors the product knows.

    WebAuthn is absent because it is not built, not because it was rejected --
    ADR-021 names it as the next method. A separate table rather than a column on
    User exists precisely so adding it is a row, not a migration of everyone.
    """

    TOTP = "totp"


class MfaMethod(models.Model):
    """An enrolled second factor -- ADR-021.

    Replaces ``User.mfa_secret_encrypted``. One column could hold one secret for
    one method, which contradicts a decision that names multiple methods; two
    places to keep an MFA secret is how one of them ends up stale.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.PROTECT, db_column="user_id", related_name="mfa_methods"
    )
    method_type = models.TextField(choices=MfaMethodType.choices)

    # Encrypted, not hashed: TOTP verification needs the secret back. The key
    # lives in the environment, never in the database -- otherwise a database
    # dump is a list of working second factors.
    secret_encrypted = models.BinaryField()

    label = models.TextField()
    confirmed_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "mfa_method"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(method_type__in=MfaMethodType.values),
                name="mfa_method_type_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user"],
                condition=models.Q(confirmed_at__isnull=False),
                name="mfa_method_confirmed_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.method_type}:{self.label}"


class MfaBackupCode(models.Model):
    """One-time recovery code -- ADR-021.

    Hashed, unlike the TOTP secret: a backup code is compared, never replayed.
    Shown once at enrolment and never again, so a database dump does not hand
    anyone a way past the second factor.

    Mandatory MFA without a recovery path produces lost accounts, and lost
    accounts produce manual exceptions in production -- which is the vector MFA
    was meant to close.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.PROTECT, db_column="user_id", related_name="backup_codes"
    )
    code_hash = models.TextField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "mfa_backup_code"
        indexes = [
            models.Index(
                fields=["user"],
                condition=models.Q(used_at__isnull=True),
                name="mfa_backup_code_unused_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"backup:{self.user_id}"


class UserSession(models.Model):
    """An authenticated session.

    Exists for one reason beyond convenience: revoking an engagement must cut the
    firm's open sessions (Spec A 4.3, IZ-20). RLS already refuses their queries,
    so this is not what keeps the data safe -- it is what stops the firm's
    interface from making requests that fail one by one instead of ending
    cleanly.

    ``actor_firm_id`` is what makes that possible: without it there is no way to
    tell which sessions belonged to the revoked relationship.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.PROTECT, db_column="user_id", related_name="sessions"
    )

    # The secret the browser holds, kept only as a SHA-256. The primary key
    # identifies the session; this authenticates it, and the two must not be the
    # same value -- a primary key travels through logs, error messages and
    # references, none of which are places for a bearer credential.
    #
    # A code, not a name: byte ordering (C34), applied in the accompanying SQL.
    token_hash = models.TextField(unique=True)

    tenant_id = models.UUIDField(null=True, blank=True)
    actor_firm_id = models.UUIDField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    revocation_reason = models.TextField(null=True, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "user_session"
        indexes = [
            models.Index(
                fields=["user"],
                condition=models.Q(revoked_at__isnull=True),
                name="user_session_live_idx",
            ),
            models.Index(
                fields=["tenant_id", "actor_firm_id"],
                condition=models.Q(revoked_at__isnull=True),
                name="user_session_firm_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"session:{self.user_id}"
