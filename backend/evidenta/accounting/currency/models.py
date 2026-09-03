"""Exchange rates -- Spec B section 7.2.

Global, like fiscal parameters and for the same reason: the official rate on a
given day is the same rate for everyone. A tenant able to write it could change
what an invoice was worth, for every other tenant in the installation.

Writing goes through privileged path P-3 (Spec A section 6.2). Reading is open,
because a posted entry keeps the rate it was made at (R10) and the client has to
be able to see which rate that was.
"""

from __future__ import annotations

import uuid

from django.db import models


class RateType(models.TextChoices):
    """Where the rate came from, which is not decoration.

    The official rate and a contractual one can differ on the same day for the
    same currency, and both can be correct for different documents. Without the
    type in the key, loading one would overwrite the other.
    """

    BNM_OFFICIAL = "bnm_official"
    MANUAL = "manual"
    CONTRACTUAL = "contractual"


class ExchangeRate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    currency = models.CharField(max_length=3)
    rate_date = models.DateField()
    rate = models.DecimalField(max_digits=18, decimal_places=8)
    rate_type = models.TextField(choices=RateType.choices)

    source = models.TextField(null=True, blank=True)
    fetched_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "exchange_rate"
        constraints = [
            models.UniqueConstraint(
                fields=["currency", "rate_date", "rate_type"], name="exchange_rate_unique"
            ),
            # A zero or negative rate does not convert an amount, it erases or
            # inverts it -- and it would do so inside an immutable entry.
            models.CheckConstraint(condition=models.Q(rate__gt=0), name="exchange_rate_positive"),
            models.CheckConstraint(
                condition=models.Q(rate_type__in=RateType.values),
                name="exchange_rate_type_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["currency", "rate_date"], name="exchange_rate_lookup_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.currency} {self.rate_date} {self.rate_type}"


class Revaluation(models.Model):
    """One revaluation of the monetary items in foreign currency -- `A10`.

    The **source document** of `accounting.revaluation_calculated` (`R13`): the
    entry names the event, the event names this row, and this row lists the
    balances the entry stands on. Without it the chain from a line on 6226 would
    end at an event whose payload is the only record of what was revalued.

    One per company and date. A second run for the same date returns this row;
    the entry is reversed through the ordinary reversal (`R14`) when it must not
    stand, and while it does not stand the rate it wrote no longer carries
    forward -- `services.revaluation.carrying_rate_of` reads the ledger for that,
    the row itself is never edited.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id", related_name="+"
    )
    company = models.ForeignKey(
        "tenancy.Company", on_delete=models.PROTECT, db_column="company_id", related_name="+"
    )

    #: The reporting date: the balances open at the end of it, at its rate.
    as_of = models.DateField()

    #: Lazy references, the way `JournalEntry` names its period and its event
    #: (`D6`): the key is schema composition, the import would be coupling.
    accounting_event = models.ForeignKey(
        "accounting_events.AccountingEvent",
        on_delete=models.PROTECT,
        db_column="accounting_event_id",
        related_name="+",
    )
    #: Null when the revaluation found nothing to post: it ran, and that is a fact
    #: worth pointing at, but there is no entry.
    journal_entry = models.ForeignKey(
        "ledger.JournalEntry",
        on_delete=models.PROTECT,
        db_column="journal_entry_id",
        null=True,
        blank=True,
        related_name="+",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "revaluation"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "as_of"], name="revaluation_company_date_unique"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "company", "as_of"], name="revaluation_idx"),
        ]

    def __str__(self) -> str:
        return f"revaluation {self.as_of}"


class RevaluationItem(models.Model):
    """One balance the revaluation restated, with both rates.

    ``rate_after`` is what the balance is carried at from this date on (SNC
    "Diferenţe de curs valutar şi de sumă" pct. 15): the next settlement and the
    next revaluation measure their difference from it, not from the invoice.
    ``difference`` is what the entry posted for it, signed as ``new - old`` in
    the functional currency, so the row can be read without the entry.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id", related_name="+"
    )
    company = models.ForeignKey(
        "tenancy.Company", on_delete=models.PROTECT, db_column="company_id", related_name="+"
    )
    revaluation = models.ForeignKey(
        Revaluation, on_delete=models.PROTECT, db_column="revaluation_id", related_name="items"
    )
    #: The open document. A key to the document core, which is `platform` and
    #: therefore fair game for a key (`D6`).
    document = models.ForeignKey(
        "documents.Document", on_delete=models.PROTECT, db_column="document_id", related_name="+"
    )
    side = models.TextField()
    partner_id = models.UUIDField()
    currency = models.CharField(max_length=3)
    amount_currency = models.DecimalField(max_digits=20, decimal_places=4)
    rate_before = models.DecimalField(max_digits=18, decimal_places=8)
    rate_after = models.DecimalField(max_digits=18, decimal_places=8)
    difference = models.DecimalField(max_digits=20, decimal_places=4)

    class Meta:
        db_table = "revaluation_item"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(side__in=("receivable", "payable")),
                name="revaluation_item_side_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(amount_currency__gt=0),
                name="revaluation_item_amount_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(rate_before__gt=0) & models.Q(rate_after__gt=0),
                name="revaluation_item_rates_positive",
            ),
            models.UniqueConstraint(
                fields=["revaluation", "document"], name="revaluation_item_document_unique"
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "company", "document"], name="revaluation_item_document_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.side} {self.amount_currency} {self.currency}"
