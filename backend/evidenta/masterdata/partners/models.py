"""Partner and CompanyPartner -- amendment section C.1, levels two and three.

Three levels, and the split is not bureaucracy:

* the **registry** is global and public -- what the state says about an entity
* the **partner** is the tenant's master record -- in a holding, METRO Moldova is
  entered once, not once per company
* the **company partner** is configuration -- receivable and payable accounts,
  payment terms, credit limit, blocks

Collapse the second and third and a holding keeps three copies of the same
supplier that drift apart. Collapse the first and second and every tenant retypes
the same IDNO, differently.
"""

from __future__ import annotations

import uuid

from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateRangeField, RangeBoundary, RangeOperators
from django.db import models
from django.db.models import F, Func

from evidenta.platform.tenancy.models import Company, Tenant


class ValidityRange(Func):
    """``daterange(valid_from, valid_to, '[)')`` as an expression.

    Half-open, like every other validity window in the system: a registration
    that ends on the day the next one starts is a clean succession, not a
    conflict.
    """

    function = "daterange"
    output_field = DateRangeField()

    def __init__(self) -> None:
        super().__init__(F("valid_from"), F("valid_to"), RangeBoundary())


class PartnerKind(models.TextChoices):
    """What the relationship is, not what the entity is.

    The same legal entity is frequently both: a company that buys and sells to
    the same counterparty needs one partner record with both roles, not two
    records that will disagree about the address.
    """

    LEGAL_ENTITY = "legal_entity"
    INDIVIDUAL = "individual"


class Partner(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")

    # The link to the public register, when there is one. Nullable on purpose:
    # an individual has no IDNO, and a foreign supplier is not in a Moldovan
    # register at all. Requiring it would make the register a gate rather than a
    # help.
    # A lazy reference, not an import. The foreign key is schema composition, but
    # importing another module's models to declare it is the coupling D6 exists
    # to stop -- and the exemption for schema composition covers only the layers
    # declared in infra/modules/dependencies.toml, which today is platform alone.
    #
    # Django resolves the string through the app registry, so partners does not
    # depend on counterparties at import time at all.
    registry_entry = models.ForeignKey(
        "counterparties.CounterpartyRegistry",
        on_delete=models.PROTECT,
        db_column="registry_entry_id",
        null=True,
        blank=True,
    )

    idno = models.TextField(null=True, blank=True)
    idnp = models.TextField(null=True, blank=True)

    #: What appears on a document, in a register and in an export (`C39`,
    #: ADR-034). `NOT NULL`, and the only name any of those three may read.
    legal_name = models.TextField()

    #: An abbreviation -- *SRL Alfa* for *Societatea cu Raspundere Limitata
    #: "Alfa"*. Not a name in another language, and deliberately not merged with
    #: `internal_name`: collapsing the two would have saved a column and produced
    #: a meaning nobody can reconstruct in two years (ADR-034).
    short_name = models.TextField(null=True, blank=True)

    #: The user's own name for this partner, in whatever alphabet they work in.
    #: Shown in lists, matched by search, accepted by importers -- and **never**
    #: printed on a document (ADR-034, `C39`). It exists so the answer to `OD-40`,
    #: whichever it turns out to be, cannot require a Russian-speaking
    #: accountant to retype their directory.
    internal_name = models.TextField(null=True, blank=True)

    kind = models.TextField(choices=PartnerKind.choices, default=PartnerKind.LEGAL_ENTITY)

    #: What this partner is normally invoiced in. Null means "the company's own
    #: currency", which is the ordinary case and is not the same fact as "MDL":
    #: a company keeping its books in another currency would be told the wrong
    #: thing by a stored default.
    default_currency = models.CharField(max_length=3, null=True, blank=True)

    #: The tenant-level payment term. `CompanyPartner.payment_terms_days`
    #: overrides it, because two companies of one holding can agree different
    #: terms with the same counterparty -- the general case sits here so it is
    #: entered once.
    default_payment_terms_days = models.SmallIntegerField(null=True, blank=True)

    is_customer = models.BooleanField(default=False)
    is_supplier = models.BooleanField(default=False)

    addresses = models.JSONField(null=True, blank=True)
    contacts = models.JSONField(null=True, blank=True)
    bank_accounts = models.JSONField(null=True, blank=True)
    tags = models.JSONField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "partner"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(kind__in=PartnerKind.values), name="partner_kind_valid"
            ),
            # One partner per IDNO within a tenant. Without it a holding ends up
            # with the same supplier twice and the balances split between them --
            # which surfaces as a reconciliation that will not close.
            models.UniqueConstraint(
                fields=["tenant", "idno"],
                condition=models.Q(idno__isnull=False),
                name="partner_idno_unique",
            ),
            # A partner that is neither customer nor supplier is a record nothing
            # can be posted against.
            models.CheckConstraint(
                condition=models.Q(is_customer=True) | models.Q(is_supplier=True),
                name="partner_has_a_role",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "legal_name"], name="partner_name_idx"),
            models.Index(fields=["tenant", "is_active"], name="partner_active_idx"),
            models.Index(fields=["tenant", "internal_name"], name="partner_internal_name_idx"),
        ]

    def __str__(self) -> str:
        return self.legal_name


class PartnerVatRegistration(models.Model):
    """VAT registration is state with an effective date, not a boolean.

    The same shape `CompanyVatRegistration` already has, and for the same reason:
    a counterparty registers and can be struck off during the year, and a
    document dated before the strike-off was correct when it was issued.
    Recalculating that period must use the status valid then (`R18`), which a
    flag on the partner cannot express.

    It is also why `Partner` carries no `vat_code` column: the code belongs to
    the registration, not to the entity. A struck-off partner that registers
    again receives a new one, and a single column would quietly overwrite the old
    -- which is the code the invoices already issued still carry.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    partner = models.ForeignKey(
        Partner,
        on_delete=models.PROTECT,
        db_column="partner_id",
        related_name="vat_registrations",
    )

    vat_code = models.TextField()
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    #: Where the fact came from: the public register, a copy of the certificate,
    #: what the counterparty stated. A status with no provenance cannot be
    #: defended when a deduction based on it is challenged.
    source = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "partner_vat_registration"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(valid_to__isnull=True)
                | models.Q(valid_to__gt=models.F("valid_from")),
                name="partner_vat_registration_period_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(vat_code=""),
                name="partner_vat_registration_has_a_code",
            ),
            # Two registrations covering one day is two answers to "was this
            # counterparty a VAT payer then", and the resolver would pick one by
            # accident. Refused where the race cannot get past it.
            ExclusionConstraint(
                name="partner_vat_registration_no_overlap",
                expressions=[
                    ("partner", RangeOperators.EQUAL),
                    (ValidityRange(), RangeOperators.OVERLAPS),
                ],
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "partner"], name="partner_vat_reg_idx"),
            models.Index(fields=["vat_code"], name="partner_vat_code_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.vat_code} from {self.valid_from}"


class CompanyPartner(models.Model):
    """How one company deals with one partner.

    The accounts here are what the Posting Engine resolves against (Spec B 3.3),
    which is why they live per company: two companies of the same holding can
    keep the same supplier on different accounts, and the ledger has to follow
    the company, not the group.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")
    partner = models.ForeignKey(Partner, on_delete=models.PROTECT, db_column="partner_id")

    # Accounts as identifiers rather than foreign keys: the chart of accounts is
    # F1.1 and lives in another module, and accounting must not be imported from
    # here (D2 in reverse). Resolution validates them at posting time.
    receivable_account_code = models.TextField(null=True, blank=True)
    payable_account_code = models.TextField(null=True, blank=True)

    payment_terms_days = models.SmallIntegerField(null=True, blank=True)
    credit_limit = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    price_list_id = models.UUIDField(null=True, blank=True)
    sales_agent_id = models.UUIDField(null=True, blank=True)

    is_blocked = models.BooleanField(default=False)
    block_reason = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "company_partner"
        constraints = [
            models.UniqueConstraint(fields=["company", "partner"], name="company_partner_unique"),
            models.CheckConstraint(
                condition=models.Q(payment_terms_days__isnull=True)
                | models.Q(payment_terms_days__gte=0),
                name="company_partner_terms_valid",
            ),
            # A block nobody can explain is a block nobody can safely lift.
            models.CheckConstraint(
                condition=models.Q(is_blocked=False) | models.Q(block_reason__isnull=False),
                name="company_partner_block_has_reason",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "is_blocked"], name="company_partner_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.company_id}:{self.partner_id}"
