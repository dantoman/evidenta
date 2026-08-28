"""The register of form ranges the tax service issued -- `art. 118²` Cod fiscal.

**The entity does not choose its series.** That is the fact the whole module is
built on, and it is the opposite of the Romanian regime, where the entity defines
its own series and resets them yearly -- a difference that produces invalid
documents if the wrong model is copied. In Moldova the tax service assures a
unitary numbering system: an entity that prints its own forms receives a series
and a range of numbers for the whole period of its activity, ordered through SIA
"Comanda on-line a formularelor tipizate".

So this is not a number generator. It is a register of **allocations**, and the
system consumes from them.

**Numbers are not materialised.** A range can be large, and a row per number
would be a table proportional to what was allocated rather than to what happened.
The allocation carries a cursor; a number leaves the range exactly once, and that
departure is a row. "Allocated" is therefore *derived* -- in range, at or above
the cursor -- while every other state is written down, which is what the law
requires of a cancellation: an evidenced state, not an absence.

**The electronic regime is not here.** In e-Factura the series and number are
assigned by the tax service's system (`Exx` plus nine digits, Ordinul SFS
185/2023), so an electronic invoice consumes nothing from a range -- it *receives*
its identifier from the exchange. Two parallel regimes, and only the paper one
has anything to allocate.

**Which forms are under the regime is data, not code.** The nomenclature keeps
shrinking -- the delivery note and the waybill left it through HG 229/2024 -- so a
document can stop being a strict-accountability form by a government decision,
and nothing should need a deployment. It lives in `fiscal.parameters` as a
versioned table with its own source act, like every other fiscal parameter
(`R15`); this module stores the code it was given and never decides the list.
"""

from __future__ import annotations

import uuid

from django.db import models

from evidenta.platform.tenancy.models import Company, Tenant


class FormNumberState(models.TextChoices):
    """How a number left the range. There is no ``allocated`` member on purpose.

    A number at or above its allocation's cursor is allocated and unused; that is
    a fact about the cursor, not a row. Every way a number can *leave* is written
    down, because the law requires the register to account for cancelled and
    spoiled forms rather than to fall silent about them.
    """

    CONSUMED = "consumed"
    CANCELLED = "cancelled"
    DAMAGED = "damaged"
    RETURNED = "returned"


class StrictFormAllocation(models.Model):
    """One series and range the tax service issued to one company.

    ``next_number`` is the cursor, and it only moves forward. A number handed out
    is never handed out again, whatever happened to the document afterwards --
    correcting a posted document is a reversal, and a reversal is a document of
    its own.

    ``responsible_user_id`` is required by the register itself: the evidence is
    kept per form type *and per responsible person*, so an allocation with nobody
    attached cannot produce the report the regulation asks for.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")

    #: The nomenclature code. No foreign key: the list of forms under the regime
    #: is a fiscal parameter, and `D6` keeps modules apart -- the code is stored,
    #: the lookup is a service call.
    form_type_code = models.TextField()

    #: As issued. `Exx` shapes belong to the electronic regime and never appear
    #: here; a paper series is whatever the order says it is.
    series = models.TextField()
    first_number = models.BigIntegerField()
    last_number = models.BigIntegerField()

    #: The next number to hand out. Starts at ``first_number`` and only advances.
    next_number = models.BigIntegerField()

    #: When the tax service issued the range, and under which order or receipt.
    issued_on = models.DateField()
    source_reference = models.TextField()

    responsible_user_id = models.UUIDField()

    #: Withdrawn rather than deleted: the numbers already consumed from it still
    #: name it, and a deleted allocation would leave them unexplained.
    is_active = models.BooleanField(default=True)
    note = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "strict_form_allocation"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(first_number__lte=models.F("last_number")),
                name="strict_form_allocation_range_ordered",
            ),
            # The cursor lives inside the range, and one past the end means
            # exhausted. Without the upper bound an exhausted allocation would
            # keep counting into numbers nobody issued.
            models.CheckConstraint(
                condition=models.Q(next_number__gte=models.F("first_number"))
                & models.Q(next_number__lte=models.F("last_number") + 1),
                name="strict_form_allocation_cursor_in_range",
            ),
            models.CheckConstraint(
                condition=models.Q(first_number__gt=0),
                name="strict_form_allocation_positive",
            ),
            # One range per series per form type per company. A second row with
            # the same start is a duplicate order, and consuming from both would
            # issue one number twice.
            models.UniqueConstraint(
                fields=["company", "form_type_code", "series", "first_number"],
                name="strict_form_allocation_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "company", "form_type_code"],
                name="strict_form_alloc_type_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.series} {self.first_number}-{self.last_number}"


class StrictFormNumber(models.Model):
    """One number that left its range, and how.

    Written once. A number leaves in exactly one way: it is consumed by a
    document, or it is cancelled, spoiled or returned unused. There is no
    transition between those -- a consumed number stays consumed even if the
    document it carries is later reversed, because the reversal is its own
    document with its own number.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")
    allocation = models.ForeignKey(
        StrictFormAllocation,
        on_delete=models.PROTECT,
        db_column="allocation_id",
        related_name="numbers",
    )

    number = models.BigIntegerField()
    state = models.TextField(choices=FormNumberState.choices)

    #: What consumed it. Null for every state but ``consumed`` -- and required
    #: for that one, because a number reported as used with nothing to show for
    #: it is the gap an inspection asks about.
    document_id = models.UUIDField(null=True, blank=True)

    occurred_at = models.DateTimeField()
    recorded_by_user_id = models.UUIDField()
    #: Free text in Romanian. Why a form was spoiled is not a vocabulary anybody
    #: has asked for, and a code list here would be invented rather than found.
    note = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "strict_form_number"
        constraints = [
            models.UniqueConstraint(
                fields=["allocation", "number"], name="strict_form_number_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(state__in=FormNumberState.values),
                name="strict_form_number_state_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(state=FormNumberState.CONSUMED)
                | models.Q(document_id__isnull=False),
                name="strict_form_number_consumed_names_document",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "company", "state"], name="strict_form_number_state_idx"
            ),
            models.Index(fields=["document_id"], name="strict_form_number_doc_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.number} ({self.state})"
