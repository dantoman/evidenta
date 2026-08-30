"""Opening balances -- F1.7.2, Spec B section 8, ADR-039 section 11.

A batch is a **staging area**, not a ledger. Rows arrive here from a person
typing a trial balance or from the 1C importer, they are checked against each
other, and then one posting carries the whole set into the ledger through the
engine -- ``opening.balance.posted`` (ADR-039 section 11). Nothing here is
accounting data; what makes it accounting data is the entry it produces.

**Seven tables, and six of them are the six sets Spec B section 8.1 names.**

    opening_balance_gl                   the trial balance: account, debit, credit
    opening_balance_receivable           per partner, with the document and its due date
    opening_balance_payable              the same, on the other side
    opening_balance_inventory            item, warehouse, lot, quantity, cost
    opening_balance_asset                entry cost and accumulated depreciation
    opening_balance_payroll_cumulative   year-to-date amounts per employee (`OD-04`)

**The analytical sets are decompositions of GL rows, never additions to them.**
Spec B section 8.2 says a batch is refused when "soldul analitic ... nu se
potriveste cu soldul contului sintetic corespunzator din setul GL" -- so the GL
row is the control total and the analytical rows are what actually posts, each
carrying the dimension the synthetic row cannot. Posting both would double every
receivable in the company.

**The payroll set does not post, and that is the shape of `OD-04` rather than an
omission.** Cumulative income and contribution amounts since 1 January are not
balances: they feed the IPC calculation when payroll is activated mid-year. What
they are made of -- which types, which contributions, which sign convention --
is an open decision, so ``code`` here is uninterpreted text with no CHECK behind
it. The table holds the shape; the vocabulary arrives with the decision.

**No account code appears in this module** (R15, `OD-22`/`OD-23`). Every account
is named by id, including the technical opening account on the batch, and the
chart is asked whether that id may receive a posting on ``as_of_date``.

**The line tables carry ``tenant_id`` and ``company_id`` as plain columns**, the
same choice ``journal_line`` makes and for the same reason: a 1C import writes
tens of thousands of rows here in one go, and each foreign key is another lookup
per row. The batch carries the real keys; the lines denormalise the context so
the policy can be evaluated without a join.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import models

from evidenta.platform.tenancy.models import Company, Tenant


class BatchSource(models.TextChoices):
    """Where the numbers came from -- Spec B section 8.1.

    Kept even though nothing branches on it today: at reconciliation time the
    first question about a wrong opening balance is whether a person typed it or
    a converter produced it, and a column added later cannot answer it for the
    batches already posted.
    """

    MANUAL = "manual"
    ONEC_IMPORT = "onec_import"
    OTHER_SYSTEM = "other_system"


class BatchStatus(models.TextChoices):
    """Spec B section 8.1. Four, and the fourth is why a batch is never deleted.

    ``draft``      lines may be added, changed and removed
    ``validated``  the checks of section 8.2 passed; the lines are frozen
    ``posted``     one journal entry exists, and the batch names it
    ``rejected``   abandoned, kept. A wrong opening balance that vanishes takes
                   with it the answer to "what did we try to load, and why did
                   somebody stop it"
    """

    DRAFT = "draft"
    VALIDATED = "validated"
    POSTED = "posted"
    REJECTED = "rejected"


class OpeningBalanceBatch(models.Model):
    """One company's opening balances, as of one date.

    ``as_of_date`` is the irreversible part (ADR-039 section 11). Once a batch of
    this company is ``posted``, every later batch must carry the same date -- a
    trigger refuses anything else, in the database, because the 1C importer and
    any data migration bypass the service. That leaves the correction path Spec B
    section 8.3 names open (a reversal and a new batch at the same date) and
    closes the one it forbids (moving the start of the books after entries exist
    behind it).

    ``counterpart_account_id`` is the technical opening account of Spec B section
    8.3. Named by the caller, never derived: which account a company uses for it
    is a chart question, and the chart's content is `OD-23`.

    ``journal_entry`` is a lazy reference rather than an import (`D6`). It is a
    real foreign key because ``journal_entry`` is not one of the append-only
    tables of R21, and a batch naming an entry that does not exist would break
    the one link that makes a posted batch auditable.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")

    as_of_date = models.DateField()
    source = models.TextField(choices=BatchSource.choices)
    status = models.TextField(choices=BatchStatus.choices, default=BatchStatus.DRAFT)

    #: The technical opening account every line is posted against. Its balance
    #: after the entry is the completeness test of Spec B section 8.3.
    counterpart_account_id = models.UUIDField()

    created_by_user_id = models.UUIDField()

    validated_at = models.DateTimeField(null=True, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    #: Free text, in Romanian, written by whoever abandoned the batch. Not a code:
    #: nothing branches on it, and a vocabulary of rejection reasons is a decision
    #: nobody has asked for.
    rejected_reason = models.TextField(null=True, blank=True)

    journal_entry = models.ForeignKey(
        "ledger.JournalEntry",
        on_delete=models.PROTECT,
        db_column="journal_entry_id",
        null=True,
        blank=True,
        related_name="opening_batches",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "opening_balance_batch"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(source__in=BatchSource.values),
                name="opening_balance_batch_source_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=BatchStatus.values),
                name="opening_balance_batch_status_valid",
            ),
            # A posted batch that names no entry is a batch nobody can audit; an
            # entry recorded on a batch that never posted is a link to something
            # that did not happen. Both directions, one constraint.
            models.CheckConstraint(
                condition=~models.Q(status=BatchStatus.POSTED)
                | (models.Q(posted_at__isnull=False) & models.Q(journal_entry__isnull=False)),
                name="opening_balance_batch_posted_names_entry",
            ),
            models.CheckConstraint(
                condition=models.Q(journal_entry__isnull=True)
                | models.Q(status=BatchStatus.POSTED),
                name="opening_balance_batch_entry_only_when_posted",
            ),
            models.CheckConstraint(
                condition=~models.Q(status__in=[BatchStatus.VALIDATED, BatchStatus.POSTED])
                | models.Q(validated_at__isnull=False),
                name="opening_balance_batch_validated_has_timestamp",
            ),
            models.CheckConstraint(
                condition=~models.Q(status=BatchStatus.REJECTED)
                | models.Q(rejected_at__isnull=False),
                name="opening_balance_batch_rejected_has_timestamp",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "as_of_date"], name="opening_batch_company_date"),
            models.Index(fields=["company", "status"], name="opening_batch_company_status"),
        ]

    def __str__(self) -> str:
        return f"{self.as_of_date} ({self.status})"


class BatchLine(models.Model):
    """What every one of the six sets carries, and nothing else.

    Abstract on purpose. Six concrete tables rather than one table with a ``kind``
    column, because the sets do not share a shape: a receivable has a due date, an
    inventory row has a quantity and a warehouse, an asset row has two accounts
    and two amounts. One table would be five sixths NULL, and the constraints that
    make each set checkable could not be written at all.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    #: Plain columns, no keys -- see the module docstring. The batch is the row
    #: that carries the real foreign keys.
    tenant_id = models.UUIDField()
    company_id = models.UUIDField()

    batch = models.ForeignKey(
        OpeningBalanceBatch,
        on_delete=models.PROTECT,
        db_column="batch_id",
        related_name="%(class)s_rows",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BalanceLine(BatchLine):
    """A set whose rows are a debit or a credit on an account.

    Four of the six sets are of this kind: GL, receivables, payables and
    inventory. ``debit`` and ``credit`` are separate and exactly one of them is
    strictly positive -- the same shape ``journal_line`` has, so that a row here
    maps to a line there without a sign convention in between (ADR-039 section 3).

    ``currency`` and ``amount_currency`` are the transaction currency of a balance
    the account tracks in foreign currency (Spec B section 8.1, "valuta si suma in
    valuta unde contul o cere"). They are stored and **not converted**: which way a
    conversion rounds is `DNB-08`, open, so a batch in a currency other than the
    company's functional one is refused rather than silently turned into lei.
    """

    account_id = models.UUIDField()

    debit = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    credit = models.DecimalField(max_digits=20, decimal_places=4, default=0)

    currency = models.CharField(max_length=3, null=True, blank=True)
    amount_currency = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)

    class Meta:
        abstract = True

    @property
    def net(self) -> Decimal:
        """Debit minus credit -- the signed balance, for comparing sets.

        Structure, not business logic (C2): the service decides what a
        mismatched net *means*, this only names the subtraction so the four sets
        are compared the same way.
        """
        return Decimal(self.debit) - Decimal(self.credit)


def _one_side_only(name: str) -> models.CheckConstraint:
    """Exactly one side, strictly positive -- ``journal_line``'s rule, upstream.

    A zero row would survive validation, produce a zero journal line, and be
    refused by ``journal_line_one_side_only`` at the very end of the import, with
    an integrity error instead of a code. Refusing it where it is typed costs one
    constraint.
    """
    return models.CheckConstraint(
        condition=models.Q(debit=0, credit__gt=0) | models.Q(debit__gt=0, credit=0),
        name=name,
    )


def _currency_pairs(name: str) -> models.CheckConstraint:
    """A currency without an amount says nothing; an amount without a currency
    says something false."""
    return models.CheckConstraint(
        condition=models.Q(currency__isnull=True, amount_currency__isnull=True)
        | models.Q(currency__isnull=False, amount_currency__isnull=False),
        name=name,
    )


class OpeningBalanceGl(BalanceLine):
    """The trial balance at ``as_of_date`` -- one row per account.

    This set is the control total for every other one. An account that also
    appears in an analytical set must match it exactly (Spec B section 8.2); an
    account that appears nowhere else posts as it stands.
    """

    class Meta:
        db_table = "opening_balance_gl"
        constraints = [
            # One row per account, so "the GL balance of this account" has one
            # answer. Two rows would make the control total a sum nobody agreed on.
            models.UniqueConstraint(
                fields=["batch", "account_id"], name="opening_balance_gl_account_unique"
            ),
            _one_side_only("opening_balance_gl_one_side_only"),
            _currency_pairs("opening_balance_gl_currency_pairs"),
        ]
        indexes = [
            models.Index(fields=["company_id", "batch"], name="opening_gl_company_batch"),
        ]

    def __str__(self) -> str:
        return f"{self.account_id}: {self.debit}/{self.credit}"


class PartnerBalanceLine(BalanceLine):
    """A partner balance with the document behind it -- Spec B section 8.1.

    ``document_type`` and ``document_number`` are free text: they name a document
    of the *previous* system, which this product does not model and must not
    pretend to. What matters is that the accountant reconciling a partner's
    account months later can see which invoice a balance came from.

    Both sides are allowed on either set. A customer who paid in advance carries a
    credit balance on the receivable account, and a supplier advance is the mirror
    -- refusing them would refuse the ordinary case.
    """

    partner_id = models.UUIDField()

    document_type = models.TextField(null=True, blank=True)
    document_number = models.TextField(null=True, blank=True)
    document_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)

    class Meta:
        abstract = True


class OpeningBalanceReceivable(PartnerBalanceLine):
    class Meta:
        db_table = "opening_balance_receivable"
        constraints = [
            _one_side_only("opening_balance_receivable_one_side_only"),
            _currency_pairs("opening_balance_receivable_currency_pairs"),
        ]
        indexes = [
            models.Index(fields=["batch", "account_id"], name="opening_receivable_account"),
            models.Index(fields=["company_id", "partner_id"], name="opening_receivable_partner"),
        ]

    def __str__(self) -> str:
        return f"{self.partner_id}: {self.debit}/{self.credit}"


class OpeningBalancePayable(PartnerBalanceLine):
    class Meta:
        db_table = "opening_balance_payable"
        constraints = [
            _one_side_only("opening_balance_payable_one_side_only"),
            _currency_pairs("opening_balance_payable_currency_pairs"),
        ]
        indexes = [
            models.Index(fields=["batch", "account_id"], name="opening_payable_account"),
            models.Index(fields=["company_id", "partner_id"], name="opening_payable_partner"),
        ]

    def __str__(self) -> str:
        return f"{self.partner_id}: {self.debit}/{self.credit}"


class OpeningBalanceInventory(BalanceLine):
    """Stock on hand: item, warehouse, lot, quantity, unit cost, total cost.

    **The three numbers are stored and none is recomputed from the other two.**
    ADR-038 section 7.3 states the rule for imports -- "suma din sursa e
    autoritativa si nu se recalculeaza" -- and it applies here for a second
    reason: ``quantity x unit_cost`` needs a rounding convention, which is
    `DNB-08`, open. ``total_cost`` is what posts; the other two travel with it so
    the inventory module has an opening quantity when it arrives (F4).

    ``quantity`` and ``uom_id`` are both mandatory. A journal line may carry a
    quantity only with a unit (``journal_line_quantity_has_unit``), and a stock
    balance without a quantity is not a stock balance.
    """

    item_id = models.UUIDField()
    warehouse_id = models.UUIDField(null=True, blank=True)
    #: Present only when the item is tracked by lot. Free text: the lot code of
    #: the previous system, which this product does not model yet.
    lot = models.TextField(null=True, blank=True)

    quantity = models.DecimalField(max_digits=20, decimal_places=6)
    uom_id = models.UUIDField()
    unit_cost = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)

    class Meta:
        db_table = "opening_balance_inventory"
        constraints = [
            _one_side_only("opening_balance_inventory_one_side_only"),
            _currency_pairs("opening_balance_inventory_currency_pairs"),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="opening_balance_inventory_has_quantity"
            ),
        ]
        indexes = [
            models.Index(fields=["batch", "account_id"], name="opening_inventory_account"),
            models.Index(fields=["company_id", "item_id"], name="opening_inventory_item"),
        ]

    def __str__(self) -> str:
        return f"{self.item_id}: {self.quantity}"


class OpeningBalanceAsset(BatchLine):
    """One fixed asset, with its cost and the depreciation already taken.

    **Two accounts and two amounts, because that is what a fixed asset is in a
    ledger**: the entry cost sits as a debit on one account and the accumulated
    depreciation as a credit on another. A single "net book value" row would post
    correctly and lose the two numbers every depreciation calculation from F2
    onwards needs.

    ``accumulated_depreciation`` may be zero -- an asset bought last month has
    none -- and a zero leg produces no journal line rather than a zero one, which
    the ledger refuses anyway.

    ``in_service_date`` and ``remaining_months`` do not post. They travel with the
    batch so that the asset module, when it exists, has the schedule rather than a
    balance it must guess a schedule from.
    """

    #: The asset's identity in the source system. No foreign key and no table
    #: behind it: the asset module is F2, and inventing one here would be an
    #: empty app for a future phase (ADR-028).
    asset_id = models.UUIDField()

    cost_account_id = models.UUIDField()
    depreciation_account_id = models.UUIDField()

    entry_cost = models.DecimalField(max_digits=20, decimal_places=4)
    accumulated_depreciation = models.DecimalField(max_digits=20, decimal_places=4, default=0)

    in_service_date = models.DateField()
    remaining_months = models.SmallIntegerField(null=True, blank=True)

    class Meta:
        db_table = "opening_balance_asset"
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "asset_id"], name="opening_balance_asset_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(entry_cost__gt=0), name="opening_balance_asset_cost_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(accumulated_depreciation__gte=0),
                name="opening_balance_asset_depreciation_not_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(remaining_months__isnull=True)
                | models.Q(remaining_months__gte=0),
                name="opening_balance_asset_remaining_not_negative",
            ),
            # Cost and depreciation on one account would net to a book value and
            # lose both numbers -- which is the whole reason there are two.
            models.CheckConstraint(
                condition=~models.Q(cost_account_id=models.F("depreciation_account_id")),
                name="opening_balance_asset_two_accounts",
            ),
        ]
        indexes = [
            models.Index(fields=["batch", "cost_account_id"], name="opening_asset_cost_account"),
            models.Index(fields=["company_id", "asset_id"], name="opening_asset_identity"),
        ]

    def __str__(self) -> str:
        return f"{self.asset_id}: {self.entry_cost} - {self.accumulated_depreciation}"


class OpeningBalancePayrollCumulative(BatchLine):
    """Year-to-date payroll amounts per employee -- `OD-04`, closed by ADR-061.

    Spec B section 8.1: "cumulative anuale per tip de venit si contributie, de la
    1 ianuarie". The table carried the shape and refused the content while the
    decision was open; ADR-061 (2026-08-30) answered it, and the two halves of
    the answer landed in opposite places on purpose.

    **The vocabulary stays out of the schema.** ``code`` is still uninterpreted
    text with no CHECK: the three names ADR-061 fixes -- ``income_tax.taxable_income``,
    ``income_tax.exemptions_granted``, ``income_tax.withheld`` -- come from the
    cumulative method itself (HG 697/2014 pct. 38), and the list grows when the
    adopted IALS21 is obtained. Growth is additive, so a CHECK here would buy a
    migration per column and prevent nothing.

    **The sign is in the schema, and that asymmetry is the decision.** A
    cumulative is a magnitude, not a movement: "exemptions granted to date" is a
    sum of exemptions, not a reduction of anything. Carrying the meaning in
    ``code`` *and* in the sign would be two encodings of one fact, and two
    encodings of one fact diverge. Unconstrained, one tenant could load
    exemptions positive and the next negative, the set would hold both
    conventions, and **nothing would report it** -- which is why this half was
    the irreversible one and why it is a CHECK rather than a convention.

    **This set never posts.** Cumulatives are not balances: they are the base the
    IPC calculation continues from when payroll is activated mid-year. They are
    validated for shape, stored with the batch, and read by `payroll` when that
    module exists.
    """

    employee_id = models.UUIDField()

    #: The source system's name for an income type or a contribution. Still
    #: uninterpreted by the schema; the vocabulary is ADR-061's -- see the class
    #: docstring for why it is not a CHECK.
    code = models.TextField()

    #: Never negative (ADR-061). The meaning is `code`'s job, not the sign's.
    amount = models.DecimalField(max_digits=20, decimal_places=4)

    #: "de la 1 ianuarie" -- carried rather than assumed, because an exercise need
    #: not start in January (ADR-039 section 6) and the cumulative window of a
    #: payroll year is not the same question as the exercise anyway.
    from_date = models.DateField()

    class Meta:
        db_table = "opening_balance_payroll_cumulative"
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "employee_id", "code"],
                name="opening_balance_payroll_unique",
            ),
            # ADR-061. Zero is allowed and meaningful: an employee with an
            # exemption category but no exemption granted yet carries 0, which is
            # a different statement from carrying no row at all.
            models.CheckConstraint(
                condition=models.Q(amount__gte=0),
                name="opening_balance_payroll_amount_not_negative",
            ),
        ]
        indexes = [
            models.Index(fields=["company_id", "employee_id"], name="opening_payroll_employee"),
        ]

    def __str__(self) -> str:
        return f"{self.employee_id}/{self.code}: {self.amount}"
