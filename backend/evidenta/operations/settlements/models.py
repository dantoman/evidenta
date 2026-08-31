"""Which document a movement answered -- ADR-087.

**One table, both sides.** `side` says whether this settles a receivable or a
payable, the way `treasury_document.direction` says which way money moved. Two
Django apps over one table would duplicate the migration, the policy, the
services and the tests to express a distinction that is a value.

**No accounting effect of its own.** The receipt already debited the treasury and
credited the receivable; allocating it to an invoice moves nothing. What the row
adds is the answer to *which one* -- and the balances that answer makes possible.

The two documents are ordinary foreign keys to the document core, which is
`platform` and therefore fair game (`D6` is about business modules sharing each
other's tables). Neither is nullable today: every settlement in the product is a
movement against an invoice. The invoice-against-advance case will need one of
them to point at another invoice, and that is a widening with its own decision
(ADR-087 §5), not a nullable column left open for it.
"""

from __future__ import annotations

import uuid

from django.db import models

from evidenta.platform.amounts import AMOUNT_DIGITS, CURRENCY_SCALE
from evidenta.platform.documents.models import Document
from evidenta.platform.tenancy.models import Company, Tenant


class Side(models.TextChoices):
    """Whose balance this clears. The accounting event names follow it."""

    RECEIVABLE = "receivable"
    PAYABLE = "payable"


class Settlement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")

    side = models.TextField(choices=Side.choices)

    #: Denormalised from the settled document, because the question people ask is
    #: "what does this partner still owe" -- and answering it by joining two
    #: document tables for every row is how a balances screen becomes slow before
    #: it has any rows.
    partner_id = models.UUIDField()

    #: The invoice being cleared.
    settled_document = models.ForeignKey(
        Document,
        on_delete=models.PROTECT,
        db_column="settled_document_id",
        related_name="settlements_received",
    )

    #: The movement doing the clearing.
    movement_document = models.ForeignKey(
        Document,
        on_delete=models.PROTECT,
        db_column="movement_document_id",
        related_name="settlements_given",
    )

    amount = models.DecimalField(max_digits=AMOUNT_DIGITS, decimal_places=CURRENCY_SCALE)
    settlement_date = models.DateField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "settlement"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(side__in=Side.values),
                name="settlement_side_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="settlement_amount_positive",
            ),
            # A document does not settle itself, and the check is here rather than
            # in the service because it is the kind of thing a later caller with
            # its own path would have to remember.
            models.CheckConstraint(
                condition=~models.Q(settled_document=models.F("movement_document")),
                name="settlement_two_documents",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "company", "settled_document"],
                name="settlement_settled_idx",
            ),
            models.Index(fields=["company", "partner_id"], name="settlement_partner_idx"),
            models.Index(
                fields=["tenant", "company", "movement_document"],
                name="settlement_movement_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.side} {self.amount}"
