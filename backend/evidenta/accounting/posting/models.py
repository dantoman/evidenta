"""Templates for typical operations -- F1.7.3, ADR-036 section 8, layer 4.

    "Clientul isi defineste sabloane de note contabile manuale: conturi,
    dimensiuni, formule simple de suma. **Domeniu: exclusiv note contabile
    manuale.** Nu pot fi folosite pentru postarea automata a documentelor."

Three tables and one rule, and the rule is what the tables are shaped around:
**a template is a shortcut to a manual note, never a second way to post.** It
stores what a person would otherwise type into the note form -- which accounts,
which side, which analytical values, and which amounts are the same every time --
and the note it produces goes through `manual.journal_entry` like any other.

The border that matters, stated as a property rather than as intent: *if a
template could produce a posting a hand-typed note cannot produce, this would be
a second engine.* Every column below is therefore a column the manual payload
already has, and nothing here can express anything the payload cannot. What is
deliberately absent is as load-bearing as what is present:

* **no date columns.** A manual line may carry its own `accounting_date`; a
  template line takes the note's. Narrower than the manual path, which is the
  safe direction -- invariant 3 wants one period per entry anyway
* **no currency columns.** Every line is in the company's functional currency,
  because a manual note in another one is refused today (`DNB-08`)
* **no arithmetic.** An amount is a fixed number or a number the person types.
  There is no multiplier, so no product, so no rounding -- and a rounding rule
  nobody decided is exactly what `DNB-08` is open about. A template that computed
  20% of a base would be answering it
* **no `event_type` of its own, and no way to name one.** ADR-036 section 8 is
  about layer 4, and layer 1 -- the form of the posting -- stays in code

**Why `posting` and not an app of its own.** A template that is not a manual note
is meaningless: it exists to be expanded into one, by the module that owns the
manual note. Splitting them would put a table in one app and the only code that
can read it in another, and the seam would be crossed on every call.

**No foreign key to `company_account`.** The ledger holds none either
(`journal_line.account_id` is a bare uuid), and the reason applies with more force
here: whether an account may receive a posting is a question with a *date* in it,
answered by the engine against the chart on the day of the posting (invariant 4).
A foreign key would be a second answer to the same question, given at definition
time, by the wrong module. So a template may name an account that is blocked,
closed, or another company's -- and the refusal arrives at posting, with the same
stable code a hand-typed note would get. There is a test for exactly that.

**Nothing is versioned.** Editing a template does not touch a note already posted:
the payload is expanded at the moment of use and the ledger is append-only, so
"which template produced this entry" cannot change under an entry. What that also
means, and it is a real gap rather than a subtlety: nothing records which template
produced a given note, because there is no manual-note table for it to live on
(F1.7.1 left `note_id` with the caller for the same reason). The provenance column
belongs on that table when it exists, not in the payload.
"""

from __future__ import annotations

import uuid

from django.db import models

from evidenta.accounting.coa.dimensions import DIMENSION_KEYS
from evidenta.platform.tenancy.models import Company, Tenant


class Side(models.TextChoices):
    """Which column of the journal line the amount lands in.

    Stored as a side plus a positive amount rather than as a `debit`/`credit`
    pair, so that "both sides filled in" is not a state the table can hold. The
    ledger's own `CHECK ((debit = 0) <> (credit = 0))` says the same thing one
    layer down; here it is said by there being one column instead of two.
    """

    DEBIT = "debit", "Debit"
    CREDIT = "credit", "Credit"


class OperationTemplate(models.Model):
    """One typical operation, as a company defines it.

    `entry_description` is the sentence the produced note carries. It is required:
    a manual note is the only entry with no document behind it, so `post_manual_entry`
    refuses one without a description -- and a template that could only ever
    produce a refused note is worse than no template.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")

    #: What the accountant picks it by. Linguistic collation, like every name
    #: (C34) -- this is a list a person reads, sorted the way Romanian sorts.
    name = models.TextField()

    #: The description the note is posted with, unless the caller overrides it.
    entry_description = models.TextField()

    #: Retired rather than deleted: the application role holds no DELETE on this
    #: table. A template that disappears takes with it the answer to "what did the
    #: shortcut everyone used last year actually do".
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "operation_template"
        constraints = [
            # Unique among the ones in use, not among all of them. A retired
            # template keeps its rows and releases its name, so a company can
            # replace "Incasare din casa" without inventing "Incasare din casa 2".
            models.UniqueConstraint(
                fields=["company", "name"],
                condition=models.Q(is_active=True),
                name="operation_template_name_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "company", "is_active"],
                name="operation_template_company",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class OperationTemplateLine(models.Model):
    """One journal line the template proposes.

    `fixed_amount` and `input_key` are exclusive and one of them is always set --
    the amount is either the same every time or typed by the person using the
    template. The service never writes both, because its own shape cannot express
    it; the CHECK below is for the paths that do not go through the service.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")
    template = models.ForeignKey(
        OperationTemplate,
        on_delete=models.CASCADE,
        db_column="template_id",
        related_name="lines",
    )

    #: The order the lines appear in the produced note, and therefore in the
    #: register. A person reading an entry reads the debit first because somebody
    #: wrote it first.
    line_number = models.IntegerField()

    #: Named by id, never by code (R15, `OD-22`/`OD-23`). No foreign key -- see
    #: the module docstring.
    account_id = models.UUIDField()

    side = models.TextField(choices=Side.choices)

    #: `numeric(20,4)`, the ledger's own scale. A fifth decimal cannot be stored
    #: without rounding, and which way it rounds is `DNB-08`.
    fixed_amount = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)

    #: The name of the value the person types. Byte-ordered (`COLLATE "C"`, C34):
    #: it is a key, not a word.
    input_key = models.TextField(null=True, blank=True)

    #: The line's own description, optional exactly as it is on a manual line.
    description = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "operation_template_line"
        constraints = [
            models.UniqueConstraint(
                fields=["template", "line_number"], name="operation_template_line_number_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(side__in=Side.values), name="operation_template_line_side_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(line_number__gt=0), name="operation_template_line_number_valid"
            ),
            # Exactly one source for the amount. Neither means a line with no
            # amount at all; both means two answers, and the one that loses is
            # decided by whoever writes the expansion next.
            models.CheckConstraint(
                condition=models.Q(fixed_amount__isnull=True, input_key__isnull=False)
                | models.Q(fixed_amount__isnull=False, input_key__isnull=True),
                name="operation_template_line_one_amount_source",
            ),
            # A zero line is refused by the engine (invariant 5) and a negative one
            # by the ledger's CHECK. Refusing both here means the template cannot
            # be *defined* to fail every time it is used.
            models.CheckConstraint(
                condition=models.Q(fixed_amount__isnull=True) | models.Q(fixed_amount__gt=0),
                name="operation_template_line_amount_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.line_number}. {self.side} {self.account_id}"


class OperationTemplateDimension(models.Model):
    """One analytical value a template line carries, fixed or asked for.

    Its own table rather than columns, and rather than `jsonb`. Columns would be
    thirty of them (fifteen values plus fifteen input names) on a table with a
    handful of rows per company; `jsonb` was rejected by ADR-029 for
    `journal_line`, and reaching for it here would put the same untyped map one
    step upstream of the ledger, which is where the values are actually chosen.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")
    line = models.ForeignKey(
        OperationTemplateLine,
        on_delete=models.CASCADE,
        db_column="line_id",
        related_name="dimensions",
    )

    #: A name from the closed vocabulary of ADR-029 -- `partner`, `dim_1` -- never
    #: a column name. The column belongs to `journal_line`, and a template that
    #: spoke in columns would need editing the day the two conventions are
    #: reconciled.
    dimension = models.TextField()

    #: The value, when it is the same on every use.
    fixed_value_id = models.UUIDField(null=True, blank=True)

    #: The name of the value the person picks, when it is not.
    input_key = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "operation_template_dimension"
        constraints = [
            models.UniqueConstraint(
                fields=["line", "dimension"], name="operation_template_dimension_unique"
            ),
            # The vocabulary is closed and lives in one place (ADR-029). A name
            # outside it would be dropped on expansion, leaving a line that looks
            # analysed without being it.
            models.CheckConstraint(
                condition=models.Q(dimension__in=list(DIMENSION_KEYS)),
                name="operation_template_dimension_known",
            ),
            models.CheckConstraint(
                condition=models.Q(fixed_value_id__isnull=True, input_key__isnull=False)
                | models.Q(fixed_value_id__isnull=False, input_key__isnull=True),
                name="operation_template_dimension_one_source",
            ),
        ]

    def __str__(self) -> str:
        return self.dimension
