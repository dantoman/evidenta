"""Producing the amounts of one document line -- the line is authoritative.

**The rule, decided by the owner and implemented here without an option.**

    VAT is calculated and rounded **on each line**. The document total is
    obtained by **adding the lines**, never by recalculating on a total base.

That single sentence removes the whole class of complaints ADR-037 section 3.1
describes: a document whose VAT is the rate applied to the total base and a
document whose VAT is the sum of its lines differ by a ban or two, and the
difference grows with the number of positions. In this model the difference
cannot exist, because there is only ever one calculation. `totals_of` in the
document core adds; it does not recompute.

**What is data and what is code**, kept apart on purpose:

* the **number of decimals** is a fiscal parameter, resolved by date
  (`fiscal.parameters.services.scales`) -- an instruction can change it without a
  deployment, and a past period keeps the precision it was calculated at (`R18`);
* the **direction at a tie** is versioned fiscal logic, selected from
  `fiscal_logic_version` by the same date -- both directions live in
  `currency.money.IMPLEMENTATIONS` and neither is chosen in code.

Nothing here reads a clock. ``on`` is the date of the economic fact and is
required, so recalculating March in June returns March's answer (ADR-044).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from evidenta.accounting.currency.money import rounding_for
from evidenta.fiscal.parameters.services.scales import (
    amount_scale,
    quantity_scale,
    unit_price_scale,
)
from evidenta.platform.api.errors import ApiError

#: A rate arrives as a percentage -- `20`, not `0.20` -- because that is how the
#: act writes it and how the document prints it. Converting at the boundary keeps
#: the stored value and the printed value the same number.
PERCENT = Decimal(100)


class AmountMalformedError(ApiError):
    """An input that cannot produce an amount, refused before it is stored."""

    code = "amounts.malformed"
    status = 422


@dataclass(frozen=True, slots=True)
class LineAmounts:
    """What a line comes to, and what it was derived from.

    `net` and `vat` are rounded; `total` is their exact sum. That asymmetry is
    the rule: rounding happens once per value, at the point the value is written
    down, and never again on something already rounded (Spec B section 7.4
    point 2).
    """

    net: Decimal
    vat: Decimal
    total: Decimal
    #: The discount actually applied, after a percentage was resolved into an
    #: amount. Stored because the document shows the percentage and a control
    #: recomputes the amount.
    discount: Decimal


def line_amounts(
    *,
    quantity: Decimal,
    unit_price: Decimal,
    vat_rate: Decimal,
    on: date,
    discount_percent: Decimal | None = None,
    discount_amount: Decimal | None = None,
) -> LineAmounts:
    """The three amounts of one line, rounded once each, at the prescribed scale.

    ``discount_percent`` and ``discount_amount`` are alternatives, not a pair to
    be reconciled: a document states one of them. Both given is a refusal rather
    than a precedence rule, because a precedence rule is a silent answer to
    "which did the person mean".
    """
    for name, value in (
        ("quantity", quantity),
        ("unit_price", unit_price),
        ("vat_rate", vat_rate),
    ):
        if not isinstance(value, Decimal):
            raise TypeError(f"{name} must be Decimal, got {type(value).__name__}")
    if vat_rate < 0:
        raise AmountMalformedError("a VAT rate is not negative; a sign belongs on the amount")
    if discount_percent is not None and discount_amount is not None:
        raise AmountMalformedError(
            "a line states a discount as a percentage or as an amount, not both; "
            "choosing between them here would answer a question the document asked"
        )

    scale = amount_scale(on)
    rule = rounding_for(on)

    price_scale = unit_price_scale(on)
    if _decimals(unit_price) > price_scale:
        raise AmountMalformedError(
            f"the unit price {unit_price} carries more than the {price_scale} "
            f"decimals in force on {on}; rounding it here would change a price "
            f"somebody agreed"
        )
    # The third axis (ADR-037 section 3.2): the quantity enters the product, so
    # its precision is part of what a posted line stands on and cannot move
    # afterwards. Refused, not rounded, for the same reason as the price.
    qty_scale = quantity_scale(on)
    if _decimals(quantity) > qty_scale:
        raise AmountMalformedError(
            f"the quantity {quantity} carries more than the {qty_scale} decimals "
            f"in force on {on}; rounding it here would change what was delivered"
        )

    gross = quantity * unit_price

    if discount_percent is not None:
        if not Decimal(0) <= discount_percent <= PERCENT:
            raise AmountMalformedError(f"a discount of {discount_percent}% is not a discount")
        discount = rule.quantize(gross * discount_percent / PERCENT, scale)
    else:
        discount = discount_amount if discount_amount is not None else Decimal(0)
        if not isinstance(discount, Decimal):
            raise TypeError("discount_amount must be Decimal, never float")

    net = rule.quantize(gross - discount, scale)
    # On the **rounded** net, which is what the document shows and therefore what
    # a control recomputes from. Applying the rate to the unrounded product would
    # make the printed line unreconstructable from the printed figures.
    vat = rule.quantize(net * vat_rate / PERCENT, scale)

    return LineAmounts(net=net, vat=vat, total=net + vat, discount=discount)


def _decimals(value: Decimal) -> int:
    """How many decimals a value actually carries, trailing zeros ignored.

    `Decimal("125.5000")` carries one, not four: the zeros are how it was typed,
    not how precise it is. Counting the exponent instead would refuse a price a
    form would have accepted.
    """
    exponent = value.normalize().as_tuple().exponent
    return -exponent if isinstance(exponent, int) and exponent < 0 else 0
