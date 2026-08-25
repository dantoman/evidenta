"""Feature flags and release rings -- Spec A section 10.5, R23, R24.

The distinction that gets lost, and what it costs when it does:

**A capability is what the tenant activated.** Functional, with an effective date
and an initialisation state, visible to the client, and an input to the Posting
Engine.

**A flag is what code is running.** Technical, no accounting date, invisible to
the client.

Confuse them and a rate change ships to some tenants and not others, which is the
one thing R24 forbids.

Rings control *when* code reaches a tenant, never *what* code runs for them -- a
single codebase is R23, and a permanent per-tenant override is a per-tenant
version wearing a different name. Which is why every override must carry a reason
and an expiry, both required by the database.
"""

from __future__ import annotations

import uuid

from django.db import models

from evidenta.platform.identity.models import User
from evidenta.platform.tenancy.models import Tenant


class FeatureFlag(models.Model):
    """The catalogue. Global: a flag is a property of the code, not of a tenant."""

    key = models.TextField(primary_key=True)
    description = models.TextField()
    default_state = models.BooleanField(default=False)

    # Compliance never rides a ring and never takes an override (R24). Marked
    # here so the rule is enforced by the database rather than remembered: see
    # the trigger in the accompanying SQL.
    is_compliance = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "feature_flag"

    def __str__(self) -> str:
        return self.key


class ReleaseRing(models.Model):
    """Who gets new code first. Global, ordered."""

    code = models.TextField(primary_key=True)
    description = models.TextField()
    sequence = models.SmallIntegerField(unique=True)

    class Meta:
        db_table = "release_ring"

    def __str__(self) -> str:
        return self.code


class TenantReleaseRing(models.Model):
    """Which ring a tenant sits in. Tenant-scoped: this is about them."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.OneToOneField(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    ring = models.ForeignKey(ReleaseRing, on_delete=models.PROTECT, db_column="ring_code")
    assigned_at = models.DateTimeField()
    assigned_by = models.ForeignKey(User, on_delete=models.PROTECT, db_column="assigned_by_user_id")

    class Meta:
        db_table = "tenant_release_ring"

    def __str__(self) -> str:
        return f"{self.tenant_id}:{self.ring_id}"


class FeatureFlagOverride(models.Model):
    """A flag forced on or off for one tenant.

    ``reason`` and ``expires_at`` are both required, and that is the whole design.
    An override with no expiry is a per-tenant version of the product; an override
    with no reason is one nobody can safely remove, because nobody remembers why
    it is there.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    flag = models.ForeignKey(FeatureFlag, on_delete=models.PROTECT, db_column="flag_key")
    state = models.BooleanField()

    reason = models.TextField()
    expires_at = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, db_column="created_by_user_id")

    class Meta:
        db_table = "feature_flag_override"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "flag"], name="feature_flag_override_unique"),
        ]
        indexes = [
            models.Index(fields=["tenant", "expires_at"], name="feature_flag_override_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.tenant_id}:{self.flag_id}={self.state}"
