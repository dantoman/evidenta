"""The precision of a quantity is the unit's -- ADR-055, closes OD-70.

Pieces have no decimals, kilograms have three, litres three, hours two. A single
platform value would be wrong for most units, and a per-tenant value would put a
property of the thing measured on the company measuring it. So it is a column on
`unit_of_measure`, mandatory and without a default, and this is the door the
document layer reads it through (D6): the calculation in
`accounting.currency.services.amounts.line_amounts` takes it as an argument and
refuses a finer quantity rather than rounding it.

Not a fiscal parameter. No act sets it, no instruction changes it, it has no
`valid_from`. The invoice form is silent on it (V1, 2026-08-29), and a silence is
not a prescription.
"""

from __future__ import annotations

import uuid

from evidenta.masterdata.uom.models import UnitOfMeasure
from evidenta.platform.api.errors import ApiError


class UnitNotFoundError(ApiError):
    code = "uom.not_found"
    status = 404


def quantity_scale_of(unit_id: uuid.UUID) -> int:
    """Decimals a quantity in this unit may carry. Read under tenant context."""
    row = UnitOfMeasure.objects.filter(pk=unit_id).values_list("decimal_places", flat=True).first()
    if row is None:
        raise UnitNotFoundError(f"unit of measure {unit_id} is not visible in this context")
    return int(row)
