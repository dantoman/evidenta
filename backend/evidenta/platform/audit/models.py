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
