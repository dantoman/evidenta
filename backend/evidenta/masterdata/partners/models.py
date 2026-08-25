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

from django.db import models

from evidenta.platform.tenancy.models import Company, Tenant


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
    legal_name = models.TextField()
    short_name = models.TextField(null=True, blank=True)
    kind = models.TextField(choices=PartnerKind.choices, default=PartnerKind.LEGAL_ENTITY)

    vat_code = models.TextField(null=True, blank=True)

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
        ]

    def __str__(self) -> str:
        return self.legal_name


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
