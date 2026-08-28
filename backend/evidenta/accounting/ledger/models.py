"""The ledger -- F1.2, Spec B sections 1.2, 1.3, 1.6, 1.7.

Two tables with deliberately different natures, and the difference is the whole
design:

``journal_entry``   moderate volume, real foreign keys, immutable once posted
``journal_line``    the largest table in the system: append-only, partition-ready,
                    no incoming foreign keys (R21), ``bigint`` key (C6)

**Every column of ``journal_line`` that will ever be needed is here now.** Not
tidiness -- ADR-039 section 2 and ADR-029 both say the same thing for different
reasons: adding a column to an append-only table of hundreds of millions of rows
is a migration nobody wants to run, so the currency fields, the three dates and
the fifteen dimension columns exist from the first row even though F1 implements
none of the features that read them.

**No module writes here** (R9). Rows arrive from the posting engine, which reads
an `accounting_event`. The service in this module is what the engine will call;
it is not a public surface for anything else.
"""

from __future__ import annotations

import uuid

from django.db import models

from evidenta.accounting.coa.dimensions import DIMENSION_KEYS, GENERIC_SLOTS, SLOT_COUNT
from evidenta.platform.amounts import PERCENT_DIGITS, PERCENT_SCALE
from evidenta.platform.tenancy.models import Company, Tenant


class EntryType(models.TextChoices):
    """Why the entry exists. Not a label -- it gates two constraints.

    A `reversal` must name the entry it cancels (R14); a `reversal` or
    `adjustment` may name the period it corrects, and nothing else may
    (ADR-006).
    """

    STANDARD = "standard"
    REVERSAL = "reversal"
    OPENING = "opening"
    CLOSING = "closing"
    ADJUSTMENT = "adjustment"


class EntryStatus(models.TextChoices):
    DRAFT = "draft"
    POSTED = "posted"


class JournalEntry(models.Model):
    """One accounting entry. Immutable once posted (R10).

    Three barriers guard that immutability, and Spec B section 1.2 asks for all
    three because each covers what the others miss:

    1. the service refuses to touch a posted entry
    2. a trigger refuses ``UPDATE``/``DELETE`` on one, in the database, so the
       importer and any data migration meet the same refusal
    3. the application role holds no ``DELETE`` on either table

    ``period`` and ``accounting_event`` are **real foreign keys**. This table is
    not in ``infra/schema/append_only.toml``, so the argument that keeps keys off
    ``journal_line`` does not apply here -- and an entry that could name a period
    or an event that does not exist would break the lineage chain R13 requires.

    Both are named as strings rather than imported. Django needs the model to
    express the key, and the import would be the coupling `D6` exists to stop --
    the same choice `items.Item` makes for its unit of measure.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")

    entry_number = models.TextField()
    accounting_date = models.DateField()

    period = models.ForeignKey(
        "periods.Period", on_delete=models.PROTECT, db_column="period_id", related_name="entries"
    )
    entry_type = models.TextField(choices=EntryType.choices, default=EntryType.STANDARD)

    #: Even a manual journal entry has one (Spec B section 1.5). Two paths into
    #: the ledger would mean lineage, idempotency and effect enumeration
    #: implemented twice, and the second implementation is always the one that
    #: breaks.
    accounting_event = models.ForeignKey(
        "accounting_events.AccountingEvent",
        on_delete=models.PROTECT,
        db_column="accounting_event_id",
        related_name="entries",
    )

    #: The second link of a reversal (R14). Without it a drill-down shows two
    #: entries with opposite amounts and nothing saying one cancels the other.
    reverses_entry = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        db_column="reverses_entry_id",
        null=True,
        blank=True,
        related_name="reversals",
    )

    #: Where the correction *belongs*, when that differs from where it is posted
    #: (ADR-006). `accounting_date` says where it lands; this says which reporting
    #: period was affected -- and without it the rectifying declaration cannot be
    #: generated, because nothing knows what to rectify.
    corrects_period = models.ForeignKey(
        "periods.Period",
        on_delete=models.PROTECT,
        db_column="corrects_period_id",
        null=True,
        blank=True,
        related_name="corrections",
    )

    status = models.TextField(choices=EntryStatus.choices, default=EntryStatus.DRAFT)
    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by_user_id = models.UUIDField(null=True, blank=True)

    description = models.TextField()

    #: Maintained by a trigger on `journal_line`, checked at commit by a deferred
    #: constraint trigger (Spec B section 1.6). PostgreSQL has no CHECK over an
    #: aggregate of another table, and R11 asks for the database to be the one
    #: that refuses -- so the sum is materialised here rather than trusted.
    #:
    #: **There is deliberately no `CHECK (total_debit = total_credit)`**, though
    #: Spec B section 1.2 lists one. Section 1.6 of the same document says why it
    #: cannot exist: lines are inserted one at a time, so the entry is unbalanced
    #: between the first and the last *by construction*. An immediate CHECK fires
    #: on the totals trigger's first update and makes a correct entry impossible
    #: to write -- measured, not reasoned: it failed on the first line of the
    #: first test. The deferred constraint trigger is the mechanism; the CHECK
    #: would be a second copy of it that cannot work.
    total_debit = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    total_credit = models.DecimalField(max_digits=20, decimal_places=4, default=0)

    request_id = models.TextField()

    # --- what the posting stood on (ADR-048) ---------------------------------
    #
    # Three versions, valid at the accounting date, stamped by the engine in the
    # same transaction as the lines. Nullable in the schema because the column
    # arrived after the first entries (C5: additive), and because a reversal
    # copies the original's rather than resolving anew; the writer requires them.

    #: The treatment that produced the entry -- `HandlerVersion.implementation_ref`,
    #: which carries its version (`sales.delivery.v1`). Re-derivable from the
    #: registry by date only as long as the registry is never edited, which is
    #: exactly the assumption a stamp exists not to make.
    rule_ref = models.TextField(null=True, blank=True)

    #: The chart version the accounts were read against. **Not re-derivable**:
    #: `company_chart.template` is the company's current version, and the day
    #: propagation moves it (`OD-03`), every earlier entry would be read against a
    #: chart it never used. Lazy reference, the way `period` is named (`D6`).
    chart_template = models.ForeignKey(
        "coa.CoaTemplate",
        on_delete=models.PROTECT,
        db_column="chart_template_id",
        null=True,
        blank=True,
        related_name="+",
    )

    #: The date the fiscal set was resolved for. In this system a fiscal set has
    #: no identity of its own -- parameters and logic are versioned row by row on
    #: `valid_from`/`valid_to`, and the rows a posting used are its
    #: `entry_parameter_stamp`s (ADR-047). The date is the key every one of those
    #: resolutions selected by, so it is the one value that names the set.
    fiscal_effective_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "journal_entry"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "entry_number"], name="journal_entry_number_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(entry_type__in=EntryType.values),
                name="journal_entry_type_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=EntryStatus.values),
                name="journal_entry_status_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(status=EntryStatus.POSTED) | models.Q(posted_at__isnull=False),
                name="journal_entry_posted_has_timestamp",
            ),
            models.CheckConstraint(
                condition=~models.Q(entry_type=EntryType.REVERSAL)
                | models.Q(reverses_entry__isnull=False),
                name="journal_entry_reversal_names_original",
            ),
            models.CheckConstraint(
                condition=models.Q(corrects_period__isnull=True)
                | models.Q(entry_type__in=[EntryType.REVERSAL, EntryType.ADJUSTMENT]),
                name="journal_entry_corrects_only_when_correcting",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "company", "accounting_date"], name="journal_entry_date_idx"
            ),
            models.Index(fields=["company", "period"], name="journal_entry_period_idx"),
            models.Index(fields=["accounting_event"], name="journal_entry_event_idx"),
            models.Index(
                fields=["reverses_entry"],
                name="journal_entry_reverses_idx",
                condition=models.Q(reverses_entry__isnull=False),
            ),
            # The query the rectifying declaration is generated from.
            models.Index(
                fields=["company", "corrects_period"],
                name="journal_entry_corrects_idx",
                condition=models.Q(corrects_period__isnull=False),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.entry_number} ({self.accounting_date})"


class JournalLine(models.Model):
    """One line. The largest table in the system, and shaped for it.

    **No foreign key points at this table** (R21) and none ever may: a table with
    ten incoming keys is not repartitioned, it is redesigned. The link back is an
    index on ``journal_entry_id``, which Spec B section 9.1 names explicitly as an
    index and *not* a key.

    **Outgoing keys, on the other hand, are almost all absent too, and for a
    different reason.** ``account_id``, ``partner_id`` and the rest carry no
    ``REFERENCES``: each one would make every INSERT do another lookup, and bulk
    posting and the 1C import are exactly the volume cases. Validation happens
    when the posting rule resolves, where the accounts and dimensions are loaded
    anyway. The accepted consequence is that a line can name a deleted account --
    which is why accounts are never deleted (Spec B section 2.4), enforced by the
    application role holding no DELETE on ``company_account``.

    The one exception is ``journal_entry_id``, which Spec B section 1.3 permits.
    One lookup per line is not the ten the cost argument is about, and an orphan
    line in an append-only ledger cannot be repaired -- there is no UPDATE to fix
    it with.
    """

    #: `bigint`, not uuid (C6). Lines are counted in hundreds of millions; a uuid
    #: costs 8 bytes more per row and, worse, randomises insert order on the index.
    id = models.BigAutoField(primary_key=True)

    #: Plain columns, no keys -- the convention `audit_event` already set for an
    #: append-only table, and for the same reason twice over: two more lookups on
    #: every one of hundreds of millions of inserts, on rows that cannot be
    #: orphaned anyway because a tenant is never deleted.
    tenant_id = models.UUIDField()
    company_id = models.UUIDField()

    #: The partition column (ADR-032, R22). `NOT NULL` from the first row, before
    #: there is any data to migrate -- which is the whole point of deciding it now.
    accounting_date = models.DateField()

    #: The other two dates of ADR-039 section 9. `document_date` is what the fiscal
    #: reports ask for; `rate_date` is when the exchange rate was taken, which under
    #: Codul fiscal art. 97 para. (6) is neither of the other two. Without it the
    #: posting cannot be reconstructed, only recomputed with today's answer.
    document_date = models.DateField()
    rate_date = models.DateField()

    journal_entry = models.ForeignKey(
        JournalEntry, on_delete=models.PROTECT, db_column="journal_entry_id", related_name="lines"
    )
    line_number = models.SmallIntegerField()

    #: The company's account. No foreign key -- see the class docstring.
    account_id = models.UUIDField()

    #: Two columns, not one signed amount. A trial balance needs debit turnover and
    #: credit turnover separately, and a signed column makes "a credit line of 100"
    #: and "a debit line of -100" indistinguishable -- both occur, and they mean
    #: different things. ADR-039 section 3 corrected a proposal that collapsed them.
    debit = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    credit = models.DecimalField(max_digits=20, decimal_places=4, default=0)

    #: The transaction's own currency and amount, always present -- `MDL` and the
    #: same number for a domestic line. Storing `1` rather than NULL for the rate
    #: is what lets `CHECK (exchange_rate > 0)` have no special case, and what lets
    #: `functional = amount_currency * exchange_rate` have no branch.
    currency = models.CharField(max_length=3)
    amount_currency = models.DecimalField(max_digits=20, decimal_places=4)
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=8, default=1)

    quantity = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    uom_id = models.UUIDField(null=True, blank=True)

    description = models.TextField(null=True, blank=True)

    # --- the fifteen analytical columns (ADR-029, Spec B section 1.7) --------
    #
    # Written out rather than generated from `coa.dimensions`. A loop over the
    # vocabulary would keep the list in one place and would also make the schema
    # of the largest table in the system depend on a tuple being imported
    # correctly -- and migrations that are generated differently on two machines
    # are the one failure this table cannot survive.
    #
    # The tie to the vocabulary is kept by a test instead: it asserts that the
    # column set here is exactly `DIMENSION_KEYS`, so adding a name there without
    # a column, or a column here without a name, fails.
    #
    # Ten named, from the closed list. The phase in each comment is when the
    # feature that fills it arrives; the column is here now regardless.
    partner_id = models.UUIDField(null=True, blank=True)  # F1
    item_id = models.UUIDField(null=True, blank=True)  # F4
    employee_id = models.UUIDField(null=True, blank=True)  # F2
    contract_id = models.UUIDField(null=True, blank=True)  # F5
    warehouse_id = models.UUIDField(null=True, blank=True)  # F4
    project_id = models.UUIDField(null=True, blank=True)  # direction
    department_id = models.UUIDField(null=True, blank=True)  # F5
    cost_center_id = models.UUIDField(null=True, blank=True)  # F5
    asset_id = models.UUIDField(null=True, blank=True)  # F2
    production_order_id = models.UUIDField(null=True, blank=True)  # direction

    # Five generic slots, meaning configured per company in `CompanyDimension`.
    # The cap is deliberate and visible: the alternative without one was the
    # variant that could not enforce a required dimension at all.
    dim_1_id = models.UUIDField(null=True, blank=True)
    dim_2_id = models.UUIDField(null=True, blank=True)
    dim_3_id = models.UUIDField(null=True, blank=True)
    dim_4_id = models.UUIDField(null=True, blank=True)
    dim_5_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "journal_line"
        constraints = [
            models.UniqueConstraint(
                fields=["journal_entry", "line_number"], name="journal_line_number_unique"
            ),
            # Exactly one side non-zero. Both zero is noise; both non-zero is a
            # modelling error wearing a valid row's clothes.
            models.CheckConstraint(
                condition=models.Q(debit=0, credit__gt=0) | models.Q(debit__gt=0, credit=0),
                name="journal_line_one_side_only",
            ),
            models.CheckConstraint(
                condition=models.Q(debit__gte=0) & models.Q(credit__gte=0),
                name="journal_line_amounts_not_negative",
            ),
            # Spec B section 1.3 writes this as "currency = functional OR rate > 0".
            # The functional currency lives on the company, which a CHECK cannot
            # reach, and the disjunction collapses to the second half anyway: the
            # functional-currency line stores rate 1, which is > 0.
            models.CheckConstraint(
                condition=models.Q(exchange_rate__gt=0), name="journal_line_rate_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__isnull=True) | models.Q(uom_id__isnull=False),
                name="journal_line_quantity_has_unit",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant_id", "company_id", "accounting_date"],
                name="journal_line_scope_idx",
            ),
            models.Index(
                fields=["company_id", "account_id", "accounting_date"],
                name="journal_line_account_idx",
            ),
            # The index that produces the partner ledger. Partial, because most
            # lines carry no partner and an index over mostly-NULL is mostly waste.
            models.Index(
                fields=["company_id", "partner_id", "accounting_date"],
                name="journal_line_partner_idx",
                condition=models.Q(partner_id__isnull=False),
            ),
            # Entry to lines -- an index, never a key (Spec B section 9.1).
            models.Index(fields=["journal_entry"], name="journal_line_entry_idx"),
            # ADR-039 section 9: reports are built on one date or the other.
            models.Index(fields=["company_id", "document_date"], name="journal_line_document_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.journal_entry_id}/{self.line_number}"


def formula_slot_constraints() -> list[models.CheckConstraint]:
    """The four typed slots of a formula, as the database enforces them -- ADR-048.

    The same three rules as the account's declaration (`coa.models.
    dimension_slot_constraints`) plus one the account has no need of: a slot is a
    **pair**, and the dimension and the value are both present or both absent. A
    value without its type is a uuid nobody can place; a type without a value is
    a claim of analysis with nothing behind it.
    """
    checks: list[models.CheckConstraint] = []
    for n in range(1, SLOT_COUNT + 1):
        dimension = f"slot_{n}_dimension"
        value = f"slot_{n}_value_id"
        checks.append(
            models.CheckConstraint(
                condition=models.Q(**{f"{dimension}__isnull": True, f"{value}__isnull": True})
                | models.Q(**{f"{dimension}__isnull": False, f"{value}__isnull": False}),
                name=f"journal_formula_slot_{n}_paired",
            )
        )
        checks.append(
            models.CheckConstraint(
                condition=models.Q(**{f"{dimension}__isnull": True})
                | models.Q(**{f"{dimension}__in": list(DIMENSION_KEYS)}),
                name=f"journal_formula_slot_{n}_known",
            )
        )
        if n > 1:
            checks.append(
                models.CheckConstraint(
                    condition=models.Q(**{f"{dimension}__isnull": True})
                    | models.Q(**{f"slot_{n - 1}_dimension__isnull": False}),
                    name=f"journal_formula_slot_{n}_contiguous",
                )
            )
    for i in range(1, SLOT_COUNT + 1):
        for j in range(i + 1, SLOT_COUNT + 1):
            checks.append(
                models.CheckConstraint(
                    condition=~models.Q(**{f"slot_{i}_dimension": models.F(f"slot_{j}_dimension")}),
                    name=f"journal_formula_slot_{i}_{j}_distinct",
                )
            )
    return checks


class JournalFormula(models.Model):
    """One correspondence -- debit account, credit account, one amount -- ADR-048.

    **The unit the engine emits and the unit an accountant reads.** A handler
    produces *n* formulas per document line, never a fixed number: reverse-charge
    VAT needs two with opposite signs on one line, standard cost needs a
    deviation, a plain delivery needs one. Each formula expands into exactly two
    ``journal_line`` rows, one per side, so every formula balances by
    construction and `R11` holds per formula before it holds per entry.

    **Why it is stored, and not only expanded.** ``journal_line`` is one-sided,
    and a three-line entry cannot say which credit a given debit corresponds to.
    The account ledger (*fișa contului*) is read by correspondence -- "în
    corespondență cu contul" -- and the merge key below is where identical
    correspondences of one entry fold into one row. Neither exists on the line.

    **Typed slots, by position.** ``slot_n_dimension`` names the axis and
    ``slot_n_value_id`` the value, four times. Typed on the row rather than
    positional against the account's declaration, so a formula stays readable
    after the declaration changes: the row says *what* sits in slot 2, not only
    that something does. The slots hold the union of what the two accounts
    declared and the line of each side receives its own share -- so what the
    formula stores is exactly what the ledger kept, and the merge key is exact.

    **No JSONB, no attribute-value table.** The merge key and the aggregate key
    both contain the dimension tuple, and both need a composite index and a real
    unique constraint -- not a hash computed in the application, which is unique
    only until the second writer computes it differently.

    Append-only and partition-ready like ``journal_line`` (`R21`, `R22`,
    ``infra/schema/append_only.toml``): no key points at it, ``accounting_date``
    is ``NOT NULL`` from the first row, ``bigint`` key (C6). The one outgoing key
    is to the entry, for the reason ``journal_line`` has one: an orphan in an
    append-only table cannot be repaired.
    """

    id = models.BigAutoField(primary_key=True)

    tenant_id = models.UUIDField()
    company_id = models.UUIDField()

    #: The partition column (ADR-032, R22), the entry's date.
    accounting_date = models.DateField()

    journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.PROTECT,
        db_column="journal_entry_id",
        related_name="formulas",
    )
    formula_number = models.SmallIntegerField()

    #: Two accounts, both of the company's chart, no keys (see `JournalLine`).
    debit_account_id = models.UUIDField()
    credit_account_id = models.UUIDField()

    #: In the functional currency -- what lands as `debit` on one line and
    #: `credit` on the other. Strictly positive: the direction is the pair of
    #: accounts, never a sign.
    amount = models.DecimalField(max_digits=20, decimal_places=4)

    #: The transaction's own currency, amount, rate and rate date, carried to
    #: both lines (ADR-039 section 3). For a domestic formula: the functional
    #: currency, the same number, 1, and the entry's date.
    currency = models.CharField(max_length=3)
    amount_currency = models.DecimalField(max_digits=20, decimal_places=4)
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=8, default=1)
    rate_date = models.DateField()

    #: The source document's date, carried to both lines (ADR-039 section 9).
    document_date = models.DateField()

    #: The VAT rate as an **attribute**, not a dimension (ADR-048): a rate is a
    #: parameter of the calculation the formula records, not an axis of analysis
    #: -- it has no ledger of its own to be indexed for. The key it was resolved
    #: under is kept beside it (`R18`); a rate may arrive without one (an import),
    #: a key never without its rate.
    vat_rate = models.DecimalField(
        max_digits=PERCENT_DIGITS, decimal_places=PERCENT_SCALE, null=True, blank=True
    )
    vat_rate_key = models.TextField(null=True, blank=True)

    quantity = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    uom_id = models.UUIDField(null=True, blank=True)

    description = models.TextField(null=True, blank=True)

    # --- the four typed slots (ADR-048) --------------------------------------
    #
    # Named `slot_n_*`, never `dim_n_*`: `dim_1` .. `dim_5` are the five
    # *generic* dimensions of ADR-029, and a formula slot may hold any of the
    # fifteen, generic ones included. One name for two things is how a value
    # ends up in the wrong column.
    slot_1_dimension = models.TextField(null=True, blank=True)
    slot_1_value_id = models.UUIDField(null=True, blank=True)
    slot_2_dimension = models.TextField(null=True, blank=True)
    slot_2_value_id = models.UUIDField(null=True, blank=True)
    slot_3_dimension = models.TextField(null=True, blank=True)
    slot_3_value_id = models.UUIDField(null=True, blank=True)
    slot_4_dimension = models.TextField(null=True, blank=True)
    slot_4_value_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "journal_formula"
        constraints = [
            models.UniqueConstraint(
                fields=["journal_entry", "formula_number"], name="journal_formula_number_unique"
            ),
            # The merge key. Two formulas of one entry that agree on everything
            # below are one formula with a larger amount, and the engine folds
            # them before writing. The constraint is what makes that a property
            # of the register rather than a habit of one writer -- and
            # `nulls_distinct=False` is what makes it a constraint at all, since
            # most of these columns are NULL on most rows.
            models.UniqueConstraint(
                fields=[
                    "journal_entry",
                    "debit_account_id",
                    "credit_account_id",
                    "currency",
                    "exchange_rate",
                    "rate_date",
                    "document_date",
                    "vat_rate",
                    "vat_rate_key",
                    "uom_id",
                    "slot_1_dimension",
                    "slot_1_value_id",
                    "slot_2_dimension",
                    "slot_2_value_id",
                    "slot_3_dimension",
                    "slot_3_value_id",
                    "slot_4_dimension",
                    "slot_4_value_id",
                ],
                nulls_distinct=False,
                name="journal_formula_merge_key",
            ),
            models.CheckConstraint(
                condition=models.Q(formula_number__gt=0), name="journal_formula_number_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="journal_formula_amount_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(amount_currency__gt=0),
                name="journal_formula_amount_currency_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(exchange_rate__gt=0), name="journal_formula_rate_positive"
            ),
            # Debit and credit on one account, with one set of slots, is a
            # movement of nothing. Expressing a transfer between two values of
            # the same account needs two formulas through a transit account, or
            # per-side slots, which this row does not have -- see ADR-048.
            models.CheckConstraint(
                condition=~models.Q(debit_account_id=models.F("credit_account_id")),
                name="journal_formula_two_accounts",
            ),
            models.CheckConstraint(
                condition=models.Q(vat_rate__isnull=True) | models.Q(vat_rate__gte=0),
                name="journal_formula_vat_rate_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(vat_rate_key__isnull=True) | models.Q(vat_rate__isnull=False),
                name="journal_formula_vat_key_has_rate",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__isnull=True) | models.Q(uom_id__isnull=False),
                name="journal_formula_quantity_has_unit",
            ),
            *formula_slot_constraints(),
        ]
        indexes = [
            models.Index(
                fields=["tenant_id", "company_id", "accounting_date"],
                name="journal_formula_scope_idx",
            ),
            # The account ledger, read by correspondence: every formula that
            # touches an account on either side, in date order.
            models.Index(
                fields=["company_id", "debit_account_id", "accounting_date"],
                name="journal_formula_debit_idx",
            ),
            models.Index(
                fields=["company_id", "credit_account_id", "accounting_date"],
                name="journal_formula_credit_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.journal_entry_id}/{self.formula_number}"


class EntryParameterStamp(models.Model):
    """Which fiscal parameter version a posting used, and how firm it was *then*.

    ``fiscal_parameter_confidence_event`` (ADR-046) records every state
    ``source_confidence`` has been in and from when. That answers "how firm was
    this parameter in March". It cannot answer "what did the March posting
    actually stand on", and the two are not the same question: confirmation does
    not change the value, so nothing about the parameter marks the calculations
    made while it was still an inference. Once the tax service publishes, a
    reader querying today's state is told nothing was ever provisional -- while
    the March posting was, in fact, made on a deduction.

    So the calculation stamps its own basis, at the moment it calculates. Not a
    reference to be dereferenced later -- the confidence is **copied**, because
    a reference resolves to whatever the world says now, which is exactly the
    thing being lost.

    Three things make it verifiable rather than merely asserted:

    ``parameter_id`` names the version. Every version of a parameter is its own
    row, so the id *is* the version -- no separate version column that could
    disagree with it.

    ``resolved_at`` names the instant. With it,
    ``fiscal.confidence_at(parameter_id, resolved_at)`` reproduces the stamped
    confidence from history. A stamp that cannot be re-derived is a claim; one
    that can is evidence, and an inspection is where that difference is charged.

    ``parameter_key`` is copied deliberately, denormalised on purpose. The stamp
    has to stay readable when the parameter it names has been superseded,
    renamed, or is being read by somebody without access to the fiscal module.

    **No foreign key to the parameter** -- `D6`: modules talk through services and
    events, never through model imports. The id is stored, the join is a service
    call, and `accounting` keeps not knowing `fiscal`'s table names.

    Append-only, by trigger: what a posting stood on is as immutable as the
    posting (`R10`). It hangs off ``journal_entry``, which is *not* in
    ``append_only.toml``, so the foreign key is allowed -- ``journal_line`` is the
    one that must stay free of incoming references (`R21`).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")

    journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.PROTECT,
        db_column="journal_entry_id",
        related_name="parameter_stamps",
    )

    #: The version used. No FK by `D6`; the id identifies the row in `fiscal`.
    parameter_id = models.UUIDField()
    #: Copied so the stamp reads without reaching into another module.
    parameter_key = models.TextField()

    #: The date the resolution was made *for* -- `R17`: the effective date of the
    #: period being calculated, never "today".
    effective_date = models.DateField()

    #: What ``source_confidence`` was at ``resolved_at``. Copied, not referenced.
    confidence = models.TextField()
    #: The instant, so the confidence above can be re-derived from history.
    resolved_at = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "entry_parameter_stamp"
        constraints = [
            # One stamp per parameter per entry. A second resolution of the same
            # parameter inside one posting that disagreed with the first would be
            # a defect, and this is where it surfaces rather than being averaged.
            models.UniqueConstraint(
                fields=["journal_entry", "parameter_id"], name="entry_parameter_stamp_unique"
            ),
        ]
        indexes = [
            # The question this table exists to answer: the tax service published,
            # what did we post on an inference and must now re-examine?
            models.Index(
                fields=["tenant", "company", "confidence"],
                name="entry_param_confidence_idx",
            ),
            # And the reverse direction: this parameter version turned out wrong,
            # what stands on it?
            models.Index(fields=["parameter_id"], name="entry_param_parameter_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.parameter_key}@{self.effective_date} ({self.confidence})"


class CompanyDimension(models.Model):
    """What a generic slot means for one company -- ADR-029.

    The five slots exist as columns on every line whether a company uses them or
    not. This is where `dim_3` becomes "Proiect" for a particular client, so a
    report can carry a label instead of a slot number.

    Not a cost added by the decision: the interface needs this table anyway, for
    the label and for the list of permitted values. That is why the objection
    "reports become unreadable without metadata" did not survive.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")

    slot = models.TextField()
    name = models.TextField()
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "company_dimension"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "slot"], name="company_dimension_slot_unique"
            ),
            # Two slots with one name make every report ambiguous in the one place
            # a reader cannot check -- the label.
            models.UniqueConstraint(
                fields=["company", "name"], name="company_dimension_name_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(slot__in=list(GENERIC_SLOTS)),
                name="company_dimension_slot_known",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.slot}={self.name}"
