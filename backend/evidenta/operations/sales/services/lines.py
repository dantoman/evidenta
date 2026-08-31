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

from evidenta.accounting.currency.money import rounding_for
from evidenta.fiscal.parameters.services.vat import vat_rate
from evidenta.masterdata.items.services.catalogue import entry_for
from evidenta.platform.api.errors import ApiError
from evidenta.platform.documents.services.lines import LineInput

#: Two decimals on a money amount -- the posted scale (ADR-059). Named here so the
#: derivation below cannot quietly disagree with what the ledger stores.
CURRENCY_SCALE = 2

#: The regime code a line without VAT carries. Step 6 brings the others.
NO_VAT_REGIME = "fara_tva"


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


def service_line(
    *,
    description: str,
    quantity: Decimal,
    unit_price: Decimal,
    on: date,
) -> LineInput:
    """A position for a service, without VAT -- what step 5 issues.

    **The amounts are derived here and not by the caller**, and this is the only
    place in this module that derives any. The document core deliberately stores
    what it is told (whether a document's VAT is the sum of its lines or the rate
    on the total is ADR-037 §3.1, open), so somebody has to do the arithmetic, and
    a screen doing it would be a second implementation of the rounding rule.

    What is derived is a product and a rounding, nothing else: no rate is applied,
    because there is none. `rounding_for` resolves the versioned direction by the
    document's date (`R17`), so re-entering a March document in June rounds the way
    March did.

    No item: this is the line a service invoice carries, and the catalogue's
    version is `line_from_catalogue`. An invoice for something that is in the
    catalogue should use that one -- it is where the VAT rate key comes from.
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
