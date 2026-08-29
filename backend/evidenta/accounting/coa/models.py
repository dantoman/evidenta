"""The SNC chart of accounts -- F1.1, Spec B section 2.

Two levels, and the split is the whole design: a **global template**, versioned
and carrying the act it transcribes, instantiated into a **per-company chart**
that the company may extend with its own subaccounts.

**This module holds no accounts.** Not one code, not one name. The content of the
general chart of accounts is `OD-23` and needs the order that approves it, cited
-- not a list written from memory. The same discipline as `fiscal.parameters`,
which has held no rate since F0.8, and for the same reason: a number nobody can
source is a number nobody can defend at an inspection.

**Nothing here is ever deleted.** A journal line references an account without a
foreign key (R21, Spec B section 1.3) and the ledger is append-only, so an account
that disappeared would make its own history unreadable. Closing an account is
``valid_to``; forbidding new postings to it is ``is_blocked``. The application
role has no DELETE privilege on either table -- see ``infra/migrations/0033_coa``.

What is deliberately **not** here: propagation of a new template version to
companies that instantiated the previous one. That is `DNB-03` = `OD-03`, open,
and four options that differ in what happens to a company's own subaccounts. The
schema carries what every option needs -- ``valid_from``/``valid_to`` on the
company account, so a reclassification can be dated rather than overwritten
(section 2.5, point 2) -- and the policy stays unwritten.
"""

from __future__ import annotations

import uuid

from django.contrib.postgres.fields import ArrayField
from django.db import models

from evidenta.accounting.coa.dimensions import DIMENSION_KEYS, SLOT_COUNT
from evidenta.platform.tenancy.models import Company, Tenant


class AccountClass(models.TextChoices):
    """Where the account sits in the statements.

    Five values, from Spec B section 2.2. They decide which statement the balance
    lands in, so a wrong one is not a label error -- it moves money between the
    balance sheet and the income statement.
    """

    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    INCOME = "income"
    EXPENSE = "expense"


class NormalBalance(models.TextChoices):
    DEBIT = "debit"
    CREDIT = "credit"


class TemplateStatus(models.TextChoices):
    DRAFT = "draft"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"


class AccountOrigin(models.TextChoices):
    """Who created the account, which decides what may be done to it.

    A system account comes from the template and is maintained centrally; a
    company account is the client's own subaccount. Renaming differs, propagation
    differs -- and both are refused or allowed on this column, not on a guess
    derived from the code.
    """

    SYSTEM = "system"
    COMPANY = "company"


def dimension_slot_constraints(table: str) -> list[models.CheckConstraint]:
    """The shape of the four typed slots, as the database enforces it -- ADR-048.

    One function for the two account tables, so the template and the company row
    cannot drift into two definitions of "a declared slot". Three rules:

    * **known** -- a slot names one of the fifteen dimensions of ADR-029, or
      nothing. A name outside the vocabulary would be a slot no column of
      ``journal_line`` can receive
    * **contiguous** -- slot *n* is filled before slot *n+1*. Positions mean
      something (the formula stores its values by position), and a hole would
      make "the second slot" ambiguous between two accounts
    * **distinct** -- one dimension, one position. Two slots of ``partner``
      would give one value two homes and a report two columns for one axis

    With NULL on either side ``slot_i = slot_j`` is NULL, and a CHECK that
    evaluates to NULL passes -- so the distinctness rule bites only when both
    positions are filled, which is the only case it is about.

    The fourth rule -- a required dimension is a carried one -- is
    ``<@`` over an array built from these columns, which ``Q`` cannot write. It
    lives in ``infra/migrations/0056_dimension_slots.up.sql``.
    """
    checks: list[models.CheckConstraint] = []
    for n in range(1, SLOT_COUNT + 1):
        column = f"slot_{n}_dimension"
        checks.append(
            models.CheckConstraint(
                condition=models.Q(**{f"{column}__isnull": True})
                | models.Q(**{f"{column}__in": list(DIMENSION_KEYS)}),
                name=f"{table}_slot_{n}_known",
            )
        )
        if n > 1:
            checks.append(
                models.CheckConstraint(
                    condition=models.Q(**{f"{column}__isnull": True})
                    | models.Q(**{f"slot_{n - 1}_dimension__isnull": False}),
                    name=f"{table}_slot_{n}_contiguous",
                )
            )
    for i in range(1, SLOT_COUNT + 1):
        for j in range(i + 1, SLOT_COUNT + 1):
            checks.append(
                models.CheckConstraint(
                    condition=~models.Q(**{f"slot_{i}_dimension": models.F(f"slot_{j}_dimension")}),
                    name=f"{table}_slot_{i}_{j}_distinct",
                )
            )
    return checks


class DeclaresDimensionSlots:
    """The accessor both account rows share. Structure, not business logic (C2)."""

    slot_1_dimension: str | None
    slot_2_dimension: str | None
    slot_3_dimension: str | None
    slot_4_dimension: str | None

    def declared_slots(self) -> tuple[str, ...]:
        """The dimensions this account carries, in slot order, holes excluded.

        Contiguity is a CHECK, so "holes excluded" changes nothing on a row the
        database accepted -- it is here so an unsaved instance reads the same way.
        """
        return tuple(
            slot
            for slot in (
                self.slot_1_dimension,
                self.slot_2_dimension,
                self.slot_3_dimension,
                self.slot_4_dimension,
            )
            if slot is not None
        )


class CoaTemplate(models.Model):
    """One version of the chart of accounts, as published.

    Global: the same law for everyone, so no tenant column -- declared in
    ``infra/rls/exceptions.toml`` and read-only for the application role.

    Provenance is mandatory in the same sense it is on a fiscal parameter (R15).
    A chart version without the order that approved it cannot be defended when a
    2026 statement is re-derived in 2030, and "these were the accounts" is not an
    answer without "under which act".
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    code = models.TextField()
    version = models.TextField()

    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    #: The normative act, its Monitorul Oficial reference and publication date --
    #: the three things a recalculation has to be able to name. Free text rather
    #: than a foreign key into `fiscal.parameters`: the chart of accounts is an
    #: accounting normative act, not a fiscal parameter, and borrowing that
    #: table's provenance row would put it under a resolver that answers a
    #: different question. The registry that both can share arrived with ADR-049
    #: (``act`` below).
    source_act = models.TextField()
    source_reference = models.TextField(null=True, blank=True)
    published_at = models.DateField(null=True, blank=True)

    #: The same act, as a row in the shared registry (ADR-049, OD-65) -- where
    #: its *two* publications live, one of them shared with OMF 118/2013. The
    #: free-text columns above stay (C5) and keep printing the citation; this is
    #: what a query joins on. Not a fiscal parameter row: the registry is in
    #: `platform`, which is the point of putting it there.
    act = models.ForeignKey(
        "legislation.NormativeAct",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="chart_templates",
        db_column="act_id",
    )

    status = models.TextField(choices=TemplateStatus.choices, default=TemplateStatus.DRAFT)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "coa_template"
        constraints = [
            models.UniqueConstraint(fields=["code", "version"], name="coa_template_version_unique"),
            models.CheckConstraint(
                condition=models.Q(status__in=TemplateStatus.values),
                name="coa_template_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(valid_to__isnull=True)
                | models.Q(valid_to__gt=models.F("valid_from")),
                name="coa_template_period_valid",
            ),
        ]
        # Non-overlap over published versions is an exclusion constraint and
        # lives in the SQL migration -- Django cannot express it against a
        # daterange without the same amount of raw SQL, and the policies are
        # there anyway (C30).

    def __str__(self) -> str:
        return f"{self.code}/{self.version}"


class CoaTemplateAccount(DeclaresDimensionSlots, models.Model):
    """One account of one template version.

    ``parent_code`` is a code, not a key. Inside a template the hierarchy is
    expressed the way the published act expresses it, and instantiation resolves
    it to ``CompanyAccount.parent`` once per company. A self-referencing key here
    would mean the loader has to insert in dependency order, which the act does
    not guarantee.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(CoaTemplate, on_delete=models.PROTECT, db_column="template_id")

    account_code = models.TextField()
    parent_code = models.TextField(null=True, blank=True)

    #: One value, in Romanian -- ADR-016, C33. Bookkeeping is kept in Romanian by
    #: law (287/2017 art. 7 para. 1), so an account name in another language would
    #: be a non-compliant artefact in a register rather than a display preference.
    #: A Russian label, if it is ever wanted, is an interface resource keyed on
    #: the account code, never a stored value.
    name_ro = models.TextField()

    account_class = models.TextField(choices=AccountClass.choices)
    normal_balance = models.TextField(choices=NormalBalance.choices)

    is_system = models.BooleanField(default=True)
    allows_subaccounts = models.BooleanField()

    currency_tracking = models.BooleanField(default=False)
    quantity_tracking = models.BooleanField(default=False)

    required_dimensions = ArrayField(models.TextField(), default=list)

    #: The typed dimension slots the account carries, by position -- ADR-048.
    #: Written out rather than generated, for the reason `journal_line` gives for
    #: its fifteen: the schema of an account must not depend on a tuple being
    #: imported in the right order. `dimensions.SLOT_FIELDS` names them and a
    #: test ties the two together. What `required_dimensions` makes mandatory
    #: must be one of these -- `coa_template_account_required_within_slots`.
    slot_1_dimension = models.TextField(null=True, blank=True)
    slot_2_dimension = models.TextField(null=True, blank=True)
    slot_3_dimension = models.TextField(null=True, blank=True)
    slot_4_dimension = models.TextField(null=True, blank=True)

    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "coa_template_account"
        constraints = [
            models.UniqueConstraint(
                fields=["template", "account_code"], name="coa_template_account_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(account_class__in=AccountClass.values),
                name="coa_template_account_class_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(normal_balance__in=NormalBalance.values),
                name="coa_template_account_balance_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(valid_to__isnull=True)
                | models.Q(valid_to__gt=models.F("valid_from")),
                name="coa_template_account_period_valid",
            ),
            # The vocabulary is closed (ADR-029) and lives in one place. A
            # dimension name written freely would produce a requirement the
            # posting engine can never satisfy, because no column carries it.
            models.CheckConstraint(
                condition=models.Q(required_dimensions__contained_by=list(DIMENSION_KEYS)),
                name="coa_template_account_dimensions_known",
            ),
            *dimension_slot_constraints("coa_template_account"),
        ]
        indexes = [
            models.Index(fields=["template", "parent_code"], name="coa_template_parent_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.account_code} {self.name_ro}"


class CompanyChart(models.Model):
    """Which template version a company instantiated, and when.

    One per company. ``template`` already identifies the version -- ``coa_template``
    is unique on ``(code, version)`` -- so the version string is not copied here.
    Spec B section 2.3 lists a ``template_version`` column beside it; storing both
    gives one question two answers, and the one that drifts is always the copy.
    The reconciliation is written down rather than made silently: see the session
    entry in ``docs/PROGRESS.md``.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")

    template = models.ForeignKey(CoaTemplate, on_delete=models.PROTECT, db_column="template_id")

    instantiated_at = models.DateTimeField(auto_now_add=True)

    #: When propagation last ran. Null until it ever does -- and it never does
    #: yet: the policy is `OD-03`, open. The column exists because every one of
    #: the four options needs it, and none of them changes its meaning.
    last_propagation_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "company_chart"
        constraints = [
            models.UniqueConstraint(fields=["company"], name="company_chart_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.company_id}:{self.template_id}"


class CompanyAccount(DeclaresDimensionSlots, models.Model):
    """An account in one company's chart -- from the template, or its own.

    The class, the normal balance and the tracking flags are **copied** from the
    template rather than read through it. That is not denormalisation for speed:
    section 2.5 point 2 requires a reclassification to be datable, so the
    company's own row has to be able to say what the account was on a date in the
    past. A join to the current template would answer with today's classification
    and quietly restate closed periods.

    ADR-036 section 13.1 (`Propus`) asks for "template version plus an override
    layer, not a derived copy". Taken literally it cannot be built here, and the
    reason is the ledger rather than a preference: ``journal_line.account_id``
    needs an identifier that is stable for the life of the company. Under a pure
    override layer a system account would be identified by the *global* template
    row until the first time the company renamed or blocked it, and by a company
    row afterwards -- so the identity of an account would change under an
    append-only table that already holds references to it.

    What that ADR is actually after survives: ``template_account`` keeps the link
    back, so propagation reaches every derived row through one index rather than
    by matching codes, and it stays an update over identified rows -- not a data
    migration.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")

    account_code = models.TextField()
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, db_column="parent_id", null=True, blank=True
    )

    origin = models.TextField(choices=AccountOrigin.choices)
    template_account = models.ForeignKey(
        CoaTemplateAccount,
        on_delete=models.PROTECT,
        db_column="template_account_id",
        null=True,
        blank=True,
    )

    name_ro = models.TextField()

    account_class = models.TextField(choices=AccountClass.choices)
    normal_balance = models.TextField(choices=NormalBalance.choices)

    #: Not in Spec B section 2.3, and section 2.4 cannot be enforced without it:
    #: a subaccount may only be created "under an account that allows
    #: subaccounts", and for a company-created account there is no template row to
    #: ask. Copied from the template for system accounts, false by default for the
    #: company's own -- nesting deeper is a decision the caller makes explicitly.
    allows_subaccounts = models.BooleanField(default=False)

    currency_tracking = models.BooleanField(default=False)
    quantity_tracking = models.BooleanField(default=False)

    required_dimensions = ArrayField(models.TextField(), default=list)

    #: The typed dimension slots, copied from the template at instantiation and
    #: extendable by the company (ADR-036 section 6.3, layer 2) -- ADR-048. The
    #: engine places a formula's dimension values on the line of whichever side
    #: declares them here, so an undeclared axis is simply not carried by this
    #: account. `company_account_required_within_slots` keeps
    #: `required_dimensions` inside this set.
    slot_1_dimension = models.TextField(null=True, blank=True)
    slot_2_dimension = models.TextField(null=True, blank=True)
    slot_3_dimension = models.TextField(null=True, blank=True)
    slot_4_dimension = models.TextField(null=True, blank=True)

    #: Blocked for posting, still visible in reports. Distinct from ``valid_to``:
    #: an account closed on a date was never usable after it, while a blocked one
    #: is a decision that can be taken back.
    is_blocked = models.BooleanField(default=False)

    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "company_account"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "account_code"], name="company_account_code_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(origin__in=AccountOrigin.values),
                name="company_account_origin_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(account_class__in=AccountClass.values),
                name="company_account_class_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(normal_balance__in=NormalBalance.values),
                name="company_account_balance_valid",
            ),
            # A system account with no template row cannot be propagated to, and
            # nothing would say which template account it came from.
            models.CheckConstraint(
                condition=~models.Q(origin=AccountOrigin.SYSTEM)
                | models.Q(template_account__isnull=False),
                name="company_account_system_has_template",
            ),
            models.CheckConstraint(
                condition=models.Q(valid_to__isnull=True)
                | models.Q(valid_to__gt=models.F("valid_from")),
                name="company_account_period_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(required_dimensions__contained_by=list(DIMENSION_KEYS)),
                name="company_account_dimensions_known",
            ),
            *dimension_slot_constraints("company_account"),
        ]
        indexes = [
            models.Index(fields=["company", "valid_from", "valid_to"], name="company_account_idx"),
            models.Index(fields=["company", "is_blocked"], name="company_account_blocked_idx"),
            # What propagation will need, whichever of the four options `OD-03`
            # settles on: every company row derived from one template account, in
            # one indexed read instead of a scan of every company's chart.
            models.Index(fields=["template_account"], name="company_account_template_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.account_code} {self.name_ro}"
