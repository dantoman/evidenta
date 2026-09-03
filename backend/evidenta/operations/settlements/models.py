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

from evidenta.platform.amounts import AMOUNT_DIGITS, CURRENCY_SCALE, RATE_DIGITS, RATE_SCALE
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

    #: What the movement gave, in the functional currency -- the movement's own
    #: figure, which is what `unallocated` counts down.
    amount = models.DecimalField(max_digits=AMOUNT_DIGITS, decimal_places=CURRENCY_SCALE)
    settlement_date = models.DateField()

    #: The three columns of a settlement across currencies (ADR-097, `OD-127`):
    #: the settled document's currency, how much of it this settled, and the
    #: official rate of the settlement day that turned one into the other. All
    #: three null on a settlement inside the functional currency, where the
    #: movement's amount is the whole story; all three set otherwise -- the CHECK
    #: refuses the halfway state. Open balances are counted in the document's
    #: currency through `COALESCE(amount_currency, amount)`.
    currency = models.CharField(max_length=3, null=True, blank=True)
    amount_currency = models.DecimalField(
        max_digits=AMOUNT_DIGITS, decimal_places=CURRENCY_SCALE, null=True, blank=True
    )
    settlement_rate = models.DecimalField(
        max_digits=RATE_DIGITS, decimal_places=RATE_SCALE, null=True, blank=True
    )

    #: The caller's `Idempotency-Key` (C9), kept on the row so a retry finds its
    #: first arrival instead of allocating again (R19). Two settlements of the
    #: same pair are legitimate (two partial payments); two arrivals of the same
    #: request are one settlement -- the key is what tells them apart. Nullable
    #: for the rows written before the column and for service callers that
    #: state none.
    idempotency_key = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "settlement"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "idempotency_key"],
                condition=models.Q(idempotency_key__isnull=False),
                name="settlement_idempotency_key_unique",
            ),
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
            models.CheckConstraint(
                condition=(
                    models.Q(currency__isnull=True)
                    & models.Q(amount_currency__isnull=True)
                    & models.Q(settlement_rate__isnull=True)
                )
                | (
                    models.Q(currency__isnull=False)
                    & models.Q(amount_currency__gt=0)
                    & models.Q(settlement_rate__gt=0)
                ),
                name="settlement_currency_complete",
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
