"""Units of measure and conversions -- F0.7.

Small, and load-bearing for two phases away. Inventory valuation and quantity
tracking on journal lines both need a quantity to mean something, and a quantity
without a unit means nothing at all.
"""

from __future__ import annotations

import uuid

from django.db import models

from evidenta.platform.tenancy.models import Tenant


class UnitOfMeasure(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")

    code = models.TextField()
    name = models.TextField()

    # Decimal places allowed for quantities in this unit. Pieces do not come in
    # halves; kilograms do. Enforcing it here stops a stock movement of 0.5
    # pieces from being valued as if it were real.
    decimal_places = models.SmallIntegerField(default=0)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "unit_of_measure"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="unit_of_measure_code_unique"),
            models.CheckConstraint(
                condition=models.Q(decimal_places__gte=0) & models.Q(decimal_places__lte=6),
                name="unit_of_measure_decimals_valid",
            ),
        ]

    def __str__(self) -> str:
        return self.code


class UnitConversion(models.Model):
    """How many of ``from_unit`` make one ``to_unit``.

    Stored as a ratio rather than a single factor because the factor is often not
    exact: a box of 12 is exact, 1 kg of a liquid in litres is not, and rounding
    the second into a decimal at definition time loses the precision every later
    quantity inherits.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")

    from_unit = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.PROTECT,
        db_column="from_unit_id",
        related_name="conversions_from",
    )
    to_unit = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.PROTECT,
        db_column="to_unit_id",
        related_name="conversions_to",
    )

    numerator = models.DecimalField(max_digits=20, decimal_places=6)
    denominator = models.DecimalField(max_digits=20, decimal_places=6)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "unit_conversion"
        constraints = [
            models.UniqueConstraint(fields=["from_unit", "to_unit"], name="unit_conversion_unique"),
            models.CheckConstraint(
                condition=models.Q(numerator__gt=0) & models.Q(denominator__gt=0),
                name="unit_conversion_positive",
            ),
            # A unit converting to itself is either a no-op or a mistake, and the
            # mistake is the one that produces a conversion loop.
            models.CheckConstraint(
                condition=~models.Q(from_unit=models.F("to_unit")),
                name="unit_conversion_not_self",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.from_unit_id}->{self.to_unit_id}"
