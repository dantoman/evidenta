"""The support grant -- ADR-077 §3: the one door from the platform to a client's data.

Tenant-scoped, so `R1` is satisfied without an exception and the policy is the
ordinary template: the client sees their own grants with an ordinary query, and
approves or revokes them through the same policy every other write of theirs
goes through. The **request** does not go through that policy -- it is `P-7`, a
privileged function (`rls.request_support_access`, 0077) -- and the application
role holds no INSERT on the table at all, so a client cannot write a request on
somebody's behalf and then approve it.

The constraints are the decision, in the database rather than in a service: an
approval carries its approver and its expiry together; the window is at most 72
hours (the interval check is in the paired SQL, because Django cannot spell it);
nobody approves their own request; a pending request does not multiply.

No `created_at`/`updated_at`: the row's dates *are* its history -- requested,
approved, expires, revoked -- and a generic timestamp would only say which of them
was last touched.
"""

from __future__ import annotations

import uuid

from django.db import models

from evidenta.platform.identity.models import User
from evidenta.platform.tenancy.models import Tenant


class SupportGrant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    #: Null means the whole space; a value narrows the grant to one company
    #: (`rls.has_company_access` gets the symmetric branch).
    company = models.ForeignKey(
        "tenancy.Company",
        on_delete=models.PROTECT,
        db_column="company_id",
        null=True,
        blank=True,
    )
    #: The platform employee, with a live `support` row in `platform_staff` at the
    #: time of the request -- checked by the function that writes this.
    requested_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        db_column="requested_by_user_id",
        related_name="support_grants_requested",
    )
    #: The support ticket. NOT NULL because the consent sentence cannot be
    #: written without it (ADR-017): "pentru rezolvarea solicitării #1234".
    request_ref = models.TextField()
    justification = models.TextField()
    requested_at = models.DateTimeField()

    approved_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        db_column="approved_by_user_id",
        null=True,
        blank=True,
        related_name="support_grants_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        db_column="revoked_by_user_id",
        null=True,
        blank=True,
        related_name="support_grants_revoked",
    )

    class Meta:
        db_table = "support_grant"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(approved_at__isnull=True, approved_by__isnull=True)
                | models.Q(approved_at__isnull=False, approved_by__isnull=False),
                name="support_grant_approval_pair",
            ),
            # An approved grant without a term is a permanent grant written by
            # mistake.
            models.CheckConstraint(
                condition=models.Q(approved_at__isnull=True, expires_at__isnull=True)
                | models.Q(approved_at__isnull=False, expires_at__isnull=False),
                name="support_grant_expiry_pair",
            ),
            models.CheckConstraint(
                condition=models.Q(expires_at__isnull=True)
                | models.Q(expires_at__gt=models.F("approved_at")),
                name="support_grant_expires_after_approval",
            ),
            models.CheckConstraint(
                condition=models.Q(approved_by__isnull=True)
                | ~models.Q(approved_by=models.F("requested_by")),
                name="support_grant_not_self_approved",
            ),
            models.CheckConstraint(
                condition=~models.Q(request_ref=""), name="support_grant_has_request_ref"
            ),
            models.CheckConstraint(
                condition=~models.Q(justification=""), name="support_grant_has_justification"
            ),
            # One pending request per employee per space, so a request nobody has
            # answered cannot multiply because somebody clicked out of habit. Live
            # approved grants are refused a second request by the function.
            models.UniqueConstraint(
                fields=["tenant", "requested_by"],
                condition=models.Q(revoked_at__isnull=True, approved_at__isnull=True),
                name="support_grant_one_pending",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "requested_at"], name="support_grant_tenant_idx"),
            # The predicate's lookup is by id; the login's is by requester and
            # tenant among live grants.
            models.Index(
                fields=["requested_by", "tenant"],
                condition=models.Q(revoked_at__isnull=True),
                name="support_grant_live_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"support:{self.request_ref}@{self.tenant_id}"
