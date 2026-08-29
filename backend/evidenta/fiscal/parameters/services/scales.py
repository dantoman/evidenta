"""How many decimals an amount and a unit price carry -- versioned data, not code.

Two different things are called "precision" in this system and conflating them is
the mistake this module exists to prevent:

* **storage width** -- the scale the column holds, `platform.amounts`. A storage
  decision, already made (Spec B section 1.3), the same for every period. A
  `numeric(20,4)` column stores a two-decimal amount without complaint.
* **rounding precision** -- how many decimals a calculated amount is *reduced to*
  before it is written down. That is prescribed by the form an entity issues, it
  can change by act, and recalculating a past period has to use the precision in
  force then (`R18`). So it is a fiscal parameter (`R15`), resolved by date, with
  a source.

Storing the second as a constant would be a fiscal parameter compiled into code,
which `R15` calls a critical defect -- and it would not move when an instruction
does.

**No value is in this repository.** These resolvers refuse when nothing is
registered, and the refusal is correct: a precision nobody chose is not a
precision, and an amount rounded to a guessed number of decimals is wrong in a
way that survives into an immutable entry.
"""

from __future__ import annotations

from datetime import date

from evidenta.fiscal.parameters.models import ValueType
from evidenta.fiscal.parameters.services.resolution import (
    FiscalResolutionError,
    resolve_parameter,
)

#: Decimals a calculated amount is reduced to -- the line's value, its VAT, and
#: every total derived by adding them.
AMOUNT_SCALE_KEY = "accounting.amount_scale"

#: Decimals a unit price carries. Deliberately a separate parameter: ADR-037
#: section 3.2 records that the unit price is the one value on a real invoice
#: that routinely carries more decimals than the amounts, and a single parameter
#: would force the two to move together.
UNIT_PRICE_SCALE_KEY = "accounting.unit_price_scale"

# There is deliberately no quantity scale here. It lived in this module for a few
# hours on 2026-08-29 and was moved out by ADR-055: the precision of a quantity
# is not prescribed by any act (the invoice form is silent -- V1), does not change
# by law, has no `valid_from`, and differs by what is measured. It is an
# attribute of the unit of measure (`unit_of_measure.decimal_places`), the way a
# conversion ratio is. A fiscal parameter would be the wrong container even with
# the right scope.


def amount_scale(on: date) -> int:
    """Decimals for amounts, in force on ``on``."""
    return _scale(AMOUNT_SCALE_KEY, on)


def unit_price_scale(on: date) -> int:
    """Decimals for the unit price, in force on ``on``."""
    return _scale(UNIT_PRICE_SCALE_KEY, on)


def _scale(key: str, on: date) -> int:
    parameter = resolve_parameter(key, on)
    if parameter.value_type != ValueType.INTEGER:
        raise FiscalResolutionError(
            "fiscal.not_a_scale",
            f"{key!r} is registered as {parameter.value_type}; a count of decimals is an integer",
        )
    value = parameter.value
    if isinstance(value, dict):
        value = value.get("value")
    if isinstance(value, bool) or not isinstance(value, int):
        raise FiscalResolutionError(
            "fiscal.not_a_scale",
            f"{key!r} holds {value!r}, which is not a count of decimals",
        )
    if value < 0 or value > 6:
        raise FiscalResolutionError(
            "fiscal.not_a_scale",
            f"{key!r} is {value}; a form does not prescribe a negative number of "
            f"decimals, and nothing in this system stores more than six",
        )
    return value
