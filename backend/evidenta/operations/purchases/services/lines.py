"""Building a purchase position.

**A near-copy of the sales helper, deliberately not an import of it.** Two
operational modules do not reach into each other (`D6`) -- and the shape of a
document line is not what they would be sharing anyway: what must not have two
implementations is the *rounding rule*, and that lives in
`accounting.currency.money.rounding_for`, which both call. This function assembles
a `LineInput`; it decides nothing.

The catalogue version is absent on purpose. A purchase of something in our own
item catalogue is a purchase *for stock*, and the entry that puts stock on the
balance sheet has a second half this system does not have yet (F4).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from evidenta.accounting.currency.money import rounding_for
from evidenta.platform.documents.services.lines import LineInput

#: Two decimals on a money amount -- the posted scale (ADR-059).
CURRENCY_SCALE = 2

#: The regime code a line without VAT carries. Step 6 brings the others.
NO_VAT_REGIME = "fara_tva"


def service_line(
    *,
    description: str,
    quantity: Decimal,
    unit_price: Decimal,
    on: date,
) -> LineInput:
    """A position for a service received, without VAT -- what step 5 records.

    ``on`` is the document's date rather than a clock, so re-entering a March
    invoice in June rounds the way March did (`R17`, ADR-044).
    """
    rounding = rounding_for(on)
    net = rounding.quantize(quantity * unit_price, CURRENCY_SCALE)
    return LineInput(
        description=description,
        quantity=quantity,
        unit_price=unit_price,
        net_amount=net,
        vat_regime_code=NO_VAT_REGIME,
        vat_rate=Decimal(0),
        vat_amount=Decimal(0),
        total_amount=net,
    )
