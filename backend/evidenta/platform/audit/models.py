"""The audit trail -- Spec A section 1, backlog F0.4.

An append-only, high-volume table, so the discipline of R21 and R22 applies from
the first migration rather than being retrofitted:

* **No foreign key points at it.** Links are made the other way. A table with no
  incoming keys is repartitioned; one with ten is redesigned.
* **It holds no outgoing keys either.** Not required by R21, but every INSERT
  here happens on the write path of something else, and ten key checks per row is
  a cost paid on every action in the system. Referential integrity is asserted at
  write time by the service.
* ``occurred_at`` is ``NOT NULL`` from the start -- the natural partition column.
* ``bigint`` primary key (C6), not UUID: nothing outside the system addresses an
  audit row, and at this volume the index size is the difference that matters.

The amendment notes that the first real candidate for partitioning is this table,
not ``journal_lines``: high write volume, value that decays quickly with age, old
partitions that can be archived or dropped.
"""

from __future__ import annotations

from django.db import models


class AuditSource(models.TextChoices):
    WEB = "web"
    API = "api"
    TASK = "task"
    SYSTEM = "system"
    MIGRATION = "migration"


class AuditEvent(models.Model):
    id = models.BigAutoField(primary_key=True)

    # No ForeignKey anywhere in this model. See the module docstring.
    tenant_id = models.UUIDField()
    company_id = models.UUIDField(null=True, blank=True)

    occurred_at = models.DateTimeField()

    actor_user_id = models.UUIDField()

    # Was the actor a firm acting under an engagement? This single column is what
    # makes "who had access to this data in March 2027" answerable after the firm
    # itself is gone -- without it, the actor is a user id with no relationship.
    actor_firm_id = models.UUIDField(null=True, blank=True)

    # Correlates every effect of one request or task. Spec A 9.3: this is what
    # turns "undo Monday" from an impossible restore into an enumerable set of
    # effects that can be reversed.
    request_id = models.TextField()

    action = models.TextField()
    entity_type = models.TextField()
    entity_id = models.UUIDField(null=True, blank=True)

    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    source = models.TextField(choices=AuditSource.choices)

    class Meta:
        db_table = "audit_event"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(source__in=AuditSource.values),
                name="audit_event_source_valid",
            ),
        ]
        indexes = [
            # Every index leads with the tenant context (amendment B.3).
            models.Index(
                fields=["tenant_id", "company_id", "occurred_at"],
                name="audit_event_scope_idx",
            ),
            # The enumeration query of Spec A 9.3. Without this index, "what did
            # this user do on Monday" is a sequential scan over the largest table
            # in the system -- which is how the feature quietly becomes unusable.
            models.Index(
                fields=["tenant_id", "actor_user_id", "occurred_at"],
                name="audit_event_actor_idx",
            ),
            models.Index(
                fields=["tenant_id", "entity_type", "entity_id", "occurred_at"],
                name="audit_event_entity_idx",
            ),
            # Spec A 9.3 again, but for the tenant alone -- "what happened here,
            # most recent first", which is the screen this table exists for.
            #
            # It looks redundant next to audit_event_scope_idx and is not, and the
            # difference was measured rather than reasoned (F0.11). With
            # company_id in the middle, a tenant's rows are ordered by company and
            # only then by time, so ordering by occurred_at alone cannot be served
            # from that index: on a million rows in one tenant, LIMIT 50 read all
            # million and took 6.7 seconds. Not a sequential scan -- an index scan
            # of everything, which is why a check for "Seq Scan" passed happily.
            models.Index(
                fields=["tenant_id", "-occurred_at"],
                name="audit_event_recent_idx",
            ),
            models.Index(fields=["request_id"], name="audit_event_request_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.action}@{self.occurred_at:%Y-%m-%d %H:%M:%S}"


class PrivilegedPath(models.TextChoices):
    """Spec A section 6.2, plus P-10 from ADR-049, P-11 from ADR-081 and P-12 from ADR-092.

    The codes are data on the log row, not a hint: a compliance report groups by
    them, and a path that never appears is either dead or uninstrumented.
    """

    P1_BILLING = "P-1"
    P2_SFS_POLLING = "P-2"
    P3_BNM_RATES = "P-3"
    P4_FISCAL_RULES = "P-4"
    P5_COUNTERPARTY_REGISTRY = "P-5"
    P6_READ_MODELS = "P-6"
    P7_SUPPORT_ACCESS = "P-7"
    P8_OFFBOARDING_EXPORT = "P-8"
    P9_PROVISIONING = "P-9"
    P10_CHART_OF_ACCOUNTS = "P-10"
    #: Claiming an unclaimed tenant (ADR-081). Enumerated in Spec A §6.2; no
    #: caller yet -- a row with this code would be the claim path arriving.
    P11_CLAIM = "P-11"
    #: Granting and revoking platform staff roles from the console (ADR-092).
    P12_PLATFORM_STAFF = "P-12"


class PrivilegedAccessLog(models.Model):
    """One row per run of a privileged path -- Spec A section 6.3, ADR-049.

    Declared in the RLS contract since F0 and built by nobody until the first role
    that had something to write in it. Global, append-only, no keys in either
    direction: the tenant identifiers are bare uuids because a foreign key would
    tie the platform's own audit trail to the lifecycle of the rows it mentions.

    ``actor_user_id`` is nullable where the spec says NOT NULL, and the deviation
    is written down rather than papered over with a placeholder: section 3.4's
    system users (``system:bnm``, ``system:efactura``) are reserved and not yet
    created, and a loader run from an operator's shell has no user row at all. So
    the actor is two columns -- the user, when there is one, and ``actor``, which
    always says who or what ran the path (an operator's login, a job name). When
    system users exist the first column is filled and the second keeps saying
    which process it was.
    """

    id = models.BigAutoField(primary_key=True)

    occurred_at = models.DateTimeField()
    path_code = models.TextField(choices=PrivilegedPath.choices)

    actor_user_id = models.UUIDField(null=True, blank=True)
    actor = models.TextField()

    #: The tenant the run touched, if exactly one. Spec A 6.3 calls the column
    #: `tenant_id`; here it is not, and the model guard is why: `tenant_id` on a
    #: table declared without tenant context reads as drift (IZ-76), and
    #: declaring it as the context column would be a lie -- nothing scopes this
    #: table by it. The name says what the value is: the subject, not the caller.
    subject_tenant_id = models.UUIDField(null=True, blank=True)
    tenant_count = models.IntegerField(null=True, blank=True)

    request_id = models.TextField()
    justification = models.TextField(null=True, blank=True)
    #: The call's parameters, never business data: a template code and version,
    #: a count of rows written, a file name. What one would need to repeat the
    #: run, not what the run wrote.
    payload = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "privileged_access_log"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(path_code__in=PrivilegedPath.values),
                name="privileged_access_log_path_valid",
            ),
            # P-7 without a justification is the case the column exists for.
            models.CheckConstraint(
                condition=~models.Q(path_code=PrivilegedPath.P7_SUPPORT_ACCESS)
                | (~models.Q(justification__isnull=True) & ~models.Q(justification="")),
                name="privileged_access_log_p7_justified",
            ),
        ]
        indexes = [
            # The monthly compliance report: per path, most recent first.
            models.Index(fields=["path_code", "-occurred_at"], name="privileged_log_path_idx"),
            models.Index(fields=["request_id"], name="privileged_log_request_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.path_code} {self.actor} @{self.occurred_at:%Y-%m-%d %H:%M:%S}"
