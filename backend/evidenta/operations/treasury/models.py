"""What a treasury document carries beyond the shared header -- ADR-073 §5.

Three facts, and each one is an account:

* the **direction** -- money in or money out, which decides whether the treasury
  account is debited or credited;
* **where the money moved**, `cash` or `bank`, because the treasury account is the
  instrument's, not the document's;
* whether the counterparty is a **resident**, because the receivable it reduces
  (or the payable it settles) differs by that, exactly as on the invoice.

**The amount lives here**, not on lines: these documents carry no positions, so
there is nothing to sum. A receipt of 3.000 lei is one number.

**What is deliberately absent: which invoice this settles.** The posting does not
need it -- debit treasury, credit receivables, whichever receivable -- and the
link is settlement, with its own handler and its own session (`F2.A3`,
ADR-073 §5). A nullable column here would be a half-built link that reports
would start reading.
"""

from __future__ import annotations

from django.db import models

from evidenta.platform.amounts import AMOUNT_DIGITS, CURRENCY_SCALE
from evidenta.platform.documents.models import Document
from evidenta.platform.tenancy.models import Company, Tenant


class Direction(models.TextChoices):
    """Money in or money out. Two document types, one table, one column."""

    RECEIPT = "receipt"
    PAYMENT = "payment"


class TreasuryAccount(models.TextChoices):
    """Where the money actually moved -- ADR-073 §5.

    A closed vocabulary in code: the value selects **which role** the handler asks
    for, which is posting form (`R28`). Currency accounts exist in the catalogue
    (`CASA_VALUTA`, `CONT_CURENT_VALUTA`) and are not reachable from here: a
    receipt in another currency opens the exchange differences, which have their
    own handler and their own step.
    """

    CASH = "cash"
    BANK = "bank"


class TreasuryDocument(models.Model):
    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        db_column="document_id",
        primary_key=True,
        related_name="treasury",
    )
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")

    direction = models.TextField(choices=Direction.choices)
    treasury_account = models.TextField(choices=TreasuryAccount.choices)

    #: Positive, always. Direction is a column, not a sign -- a negative receipt
    #: and a payment would be the same row written two ways, and every report
    #: would have to know which convention it was reading.
    amount = models.DecimalField(max_digits=AMOUNT_DIGITS, decimal_places=CURRENCY_SCALE)

    #: Country or abroad, for the receivable reduced or the payable settled.
    #: Carried, never derived -- `Partner` has no residence column.
    partner_resident = models.BooleanField()

    class Meta:
        db_table = "treasury_document"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(direction__in=Direction.values),
                name="treasury_document_direction_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(treasury_account__in=TreasuryAccount.values),
                name="treasury_document_account_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="treasury_document_amount_positive",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "company", "direction"],
                name="treasury_document_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.direction} {self.amount}"
