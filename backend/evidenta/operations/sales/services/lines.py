"""Building a document position from the catalogue.

The catalogue supplies the **identity** of a position: what it is called on a
document, in which unit, and under which VAT rate key. The amounts are produced
by `accounting.currency.services.amounts.line_amounts`, which applies the rule
the owner decided: **VAT is calculated and rounded on each line, and the document
total is the sum of the lines.** Where the rounding happens is therefore settled;
what remains data is how many decimals (a fiscal parameter) and which direction a
tie resolves in (a row in the logic registry).

`line_from_amounts` stays for the callers that already hold the three figures --
an import, a conversion, a storno -- and it is the reason the document core
stores amounts rather than deriving them: a document that arrived from elsewhere
carries the amounts its issuer calculated, not the ones we would have.

**The name that goes on the line is the legal one.** `item.name`, never
`item.internal_name` -- `C39` and ADR-034. The internal name exists for lists,
search and imports, and a document that printed it would be exactly the artefact
`OD-40` is open about.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from evidenta.fiscal.parameters.services.vat import vat_rate
from evidenta.masterdata.items.services.catalogue import entry_for
from evidenta.platform.api.errors import ApiError
from evidenta.platform.documents.services.lines import LineInput


class ItemHasNoVatRateError(ApiError):
    """The catalogue entry names no VAT rate key.

    Refused rather than defaulted to the standard rate. Which treatment applies
    to an item is a fiscal fact about that item, and a default here would put the
    standard rate on a medicine, an export or an exempt service without anybody
    choosing it.
    """

    code = "sales.item_has_no_vat_rate"
    status = 422


def line_from_catalogue(
    item_id: uuid.UUID,
    *,
    on: date,
    quantity: Decimal,
    unit_price: Decimal,
    net_amount: Decimal,
    vat_amount: Decimal,
    total_amount: Decimal,
    vat_regime_code: str,
    discount_percent: Decimal | None = None,
    discount_amount: Decimal = Decimal(0),
    description: str | None = None,
) -> LineInput:
    """A position for ``item_id``, priced by the caller, described by the catalogue.

    ``on`` is the date the rate is resolved for -- the document's date, passed in
    rather than read from a clock, so re-entering a March document in June
    reaches March's rate (ADR-044).

    ``description`` overrides the catalogue name for the rare line that needs to
    say something else. It still may not be the internal name: what a caller
    passes is what prints.
    """
    item = entry_for(item_id)
    if not item.vat_rate_key:
        raise ItemHasNoVatRateError(
            f"item {item.sku} names no VAT rate key. A default here would put the "
            f"standard rate on an exempt or zero-rated item without anybody choosing it."
        )

    return LineInput(
        item_id=item.id,
        description=description or item.legal_name,
        quantity=quantity,
        unit_id=item.base_unit_id,
        unit_code=item.base_unit_code,
        unit_price=unit_price,
        discount_percent=discount_percent,
        discount_amount=discount_amount,
        net_amount=net_amount,
        vat_regime_code=vat_regime_code,
        vat_rate_key=item.vat_rate_key,
        vat_rate=vat_rate(item.vat_rate_key, on),
        vat_amount=vat_amount,
        total_amount=total_amount,
    )
