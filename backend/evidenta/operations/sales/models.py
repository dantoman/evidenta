"""What a sales-side document carries beyond the shared header.

Three types, three tables, each one-to-one with a row in `document`. The header
holds everything they share -- number, dates, counterparty, currency, state,
cancellation -- and these hold only what is theirs. That split is the design the
document core was built around: numbering, state and history have one
implementation, and a type that needs one extra field does not get a second copy
of them.

**Nothing here is an accounting fact.** No account, no correspondence, no
dimension, no rate. A sales document knows it is a delivery or an advance; what
that means in the ledger is decided by the Posting Engine against rules that do
not exist yet, and a column here that anticipated them would be that decision
taken in the wrong place.
"""

from __future__ import annotations

from django.db import models

from evidenta.platform.documents.models import Document
from evidenta.platform.tenancy.models import Company, Tenant


class SaleNature(models.TextChoices):
    """Delivery or advance -- one type of document, not two.

    The distinction is real: an advance is money received before anything is
    delivered, and it is followed by a delivery that settles it. But it is an
    *attribute of the same document*, not a different document: the header, the
    positions, the numbering and the lifecycle are identical, and two types would
    have meant two of everything to keep a single boolean apart.
    """

    DELIVERY = "delivery"
    ADVANCE = "advance"


class RevenueKind(models.TextChoices):
    """What is being sold -- and therefore which revenue account (ADR-073 §3).

    A closed vocabulary in code, on the pattern ADR-065 §7.1 fixed for the cost
    destination: the value selects **which role** the handler asks for, which is
    posting form (`R28`), not configuration. It does not condition which account a
    role binds to.

    Three values, and only the first posts today. Goods and finished products
    recognise revenue the same way, but the entry has a second half -- the stock
    coming off the books -- and that is F4. A handler posting only the first half
    would produce a month whose margin equals its turnover: balanced, plausible,
    false.
    """

    SERVICES = "services"
    GOODS = "goods"
    PRODUCTS = "products"


class SalesDocument(models.Model):
    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        db_column="document_id",
        primary_key=True,
        related_name="sales",
    )
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")

    nature = models.TextField(choices=SaleNature.choices, default=SaleNature.DELIVERY)

    #: Which revenue role the posting asks for. No default: the three are not
    #: interchangeable, and a document that arrived without anyone choosing would
    #: post to services because that is what a default would say.
    revenue_kind = models.TextField(choices=RevenueKind.choices)

    #: Country or abroad, for the receivable. **Carried, never derived** --
    #: `Partner` has no residence field, and a default of "resident" would post
    #: receivables from non-residents to the domestic account: balanced, `R11`
    #: green, and wrong in the balance sheet at every reporting date. The same
    #: shape ADR-057 fixed for settlement differences.
    partner_resident = models.BooleanField()

    class Meta:
        db_table = "sales_document"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(nature__in=SaleNature.values),
                name="sales_document_nature_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(revenue_kind__in=RevenueKind.values),
                name="sales_document_revenue_kind_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "company", "nature"], name="sales_document_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.document_id} ({self.nature})"


class ProformaDocument(models.Model):
    """An offer. It commits the issuer to a price, not the buyer to anything.

    No accounting effect, by definition rather than by omission: nothing has been
    delivered and nothing has been received. What it does have is an expiry --
    a price offered without one is offered forever.
    """

    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        db_column="document_id",
        primary_key=True,
        related_name="proforma",
    )
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")

    valid_until = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "proforma_document"
        indexes = [
            models.Index(fields=["tenant", "company", "valid_until"], name="proforma_idx"),
        ]

    def __str__(self) -> str:
        return str(self.document_id)


class CustomerOrder(models.Model):
    """What the customer asked for. Operational; no accounting effect.

    It becomes a sale when it is fulfilled, and the conversion carries the
    positions across with the link back on each one -- so what was ordered and
    what was invoiced can be compared without anybody re-keying either.
    """

    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        db_column="document_id",
        primary_key=True,
        related_name="customer_order",
    )
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")

    requested_delivery_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "customer_order"
        indexes = [
            models.Index(
                fields=["tenant", "company", "requested_delivery_date"],
                name="customer_order_idx",
            ),
        ]

    def __str__(self) -> str:
        return str(self.document_id)
