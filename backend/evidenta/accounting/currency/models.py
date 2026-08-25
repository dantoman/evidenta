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
