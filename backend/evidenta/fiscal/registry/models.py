"""The registry that selects fiscal logic by effective date -- R17, R18.

The second half of the compliance split. Parameters are data; algorithms,
declaration schemas and validation rules are versioned code, and this is what
picks which version runs.

**Selection is by the effective date of the period being calculated, never by
today.** That is the whole mechanism, and the interdiction that makes it work is
in CLAUDE.md as R17: no `if year >= 2027` anywhere in business code. The
implementation written for 2026 does not know 2027 exists. The registry knows.

**An implementation is never deleted.** Recalculating a 2026 period in 2030 needs
the 2026 algorithm to still be there, so retired code stays in the repository,
covered by the regression corpus. Deleting it would make the recalculation quietly
wrong rather than impossible, which is worse.
"""

from __future__ import annotations

import uuid

from django.db import models


class LogicStatus(models.TextChoices):
    DRAFT = "draft"
    APPROVED = "approved"
    ACTIVE = "active"
    SUPERSEDED = "superseded"


class FiscalLogicVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # What is being computed, e.g. payroll contributions or VAT proration.
    logic_key = models.TextField()

    # A stable reference to the implementation -- a dotted path resolved at call
    # time. Stored rather than imported so the registry does not depend on every
    # implementation existing at import, and so a retired one can be referenced
    # without being loaded.
    implementation_ref = models.TextField()
    version = models.TextField()

    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    # Schema composition across two modules of the same layer, permitted by
    # ADR-027. Optional because an algorithm can implement a requirement that does
    # not come from a single act -- but where it exists it points at a real one,
    # and PROTECT keeps it that way.
    source = models.ForeignKey(
        "fiscal_parameters.FiscalParameterSource",
        on_delete=models.PROTECT,
        db_column="source_id",
        null=True,
        blank=True,
    )

    # Which set in the fiscal regression corpus covers this version. Required
    # before it can go active: a change to an algorithm with no regression case
    # is how a rate change for 2027 silently breaks the recalculation of 2025 --
    # and that gets discovered at a client (amendment D.2).
    regression_case_set = models.TextField()

    status = models.TextField(choices=LogicStatus.choices, default=LogicStatus.DRAFT)
    approved_by_user_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "fiscal_logic_version"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(valid_to__isnull=True)
                | models.Q(valid_to__gt=models.F("valid_from")),
                name="fiscal_logic_period_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=LogicStatus.values),
                name="fiscal_logic_status_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(status=LogicStatus.ACTIVE)
                | models.Q(approved_by_user_id__isnull=False),
                name="fiscal_logic_active_requires_approval",
            ),
            models.UniqueConstraint(
                fields=["logic_key", "version"], name="fiscal_logic_version_unique"
            ),
        ]
        indexes = [
            models.Index(fields=["logic_key", "valid_from"], name="fiscal_logic_key_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.logic_key}:{self.version}"


class EmploymentRelationshipType(models.Model):
    """The three forms of work relationship the acts distinguish -- ADR-071.

    **A vocabulary, not a configuration.** Point 1.1 of annex 1 to Law 489/1999
    names three in one clause: an individual employment contract, a *service
    relationship under an administrative act*, and a civil contract for works or
    services. Nothing else is a fourth form, and a catch-all value would be the
    road by which "invariant applied blindly" comes back under another name --
    which is why the CHECK below closes the set rather than documenting it.

    **Why it lives in `fiscal` and not in `payroll`.** `D1`: fiscal imports from
    no business module, so a fiscal invariant whose domain pointed at a table in
    `operations/payroll` would be a forbidden dependency. The other direction is
    allowed. And it is right on the merits -- the distinction is drawn by the
    contributions law, not by labour law.

    **The primary key is the code**, as in `Permission` and for the same reasons:
    reference data whose identity *is* its name, neither externally exposed nor
    high-volume, so `C6` does not apply. **No label column** either (`C32`): what
    a type is called in the interface belongs in the frontend resource files, in
    Romanian, not in a column that needs a migration to reword.

    **No validity margins**, and that is argued rather than assumed (ADR-071
    section 4ter): nothing resolves a *type* by date. What resolves by date is
    what a type is *referenced by* -- the domain of an invariant, versioned in
    the logic registry. A repealed type stays, with `PROTECT` on every key into
    it, so historic references keep resolving.
    """

    #: `COLLATE "C"` in the SQL file -- a code column, not a name (`C34`).
    code = models.TextField(primary_key=True)

    #: The anchor, carried by the row rather than only by the ADR. A type whose
    #: citation lives one document away is a value somebody typed; the project
    #: has paid for that distinction often enough to write it into the table.
    statutory_reference = models.TextField()

    class Meta:
        db_table = "employment_relationship_type"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    code__in=[
                        "employment_contract",
                        "service_relationship",
                        "civil_contract",
                    ]
                ),
                name="employment_relationship_type_vocabulary_closed",
            ),
        ]

    def __str__(self) -> str:
        return self.code
