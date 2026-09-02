"""Building a purchase position -- and, since step 6, pricing its VAT.

**A near-copy of the sales helper, deliberately not an import of it.** Two
operational modules do not reach into each other (`D6`) -- and the shape of a
document line is not what they would be sharing anyway: what must not have two
implementations is the *arithmetic*, and that lives in
`accounting.currency.services.amounts.line_amounts`, which both call, and the
*nomenclature*, which both read through `fiscal`. This module assembles a
`LineInput`; it decides nothing.

**One rule the sales side has and this one does not.** A supplier's invoice
carries whatever VAT the supplier charged, whether or not *we* are a VAT payer:
a company that is not registered still receives invoices with VAT on them, and
records them as they are. So the regime here describes the paper, and no status
of ours restricts it. Where our status matters is at posting -- whether the VAT
is deductible or is part of the cost -- and that is `recording`'s question.

The catalogue version is absent on purpose. A purchase of something in our own
item catalogue is a purchase *for stock*, and the entry that puts stock on the
balance sheet has a second half this system does not have yet (F4).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from evidenta.accounting.currency.services.amounts import line_amounts
from evidenta.fiscal.parameters.services.resolution import FiscalResolutionError
from evidenta.fiscal.parameters.services.vat import RegimeRate, regime_rate
from evidenta.platform.api.errors import ApiError
from evidenta.platform.documents.services.lifecycle import get_document
from evidenta.platform.documents.services.lines import LineInput, replace_lines

#: The regime code a line without VAT carries: the supplier charged none.
NO_VAT_REGIME = "fara_tva"

#: See `sales.services.lines.SERVICE_QUANTITY_SCALE`: no unit, so the API's bound.
SERVICE_QUANTITY_SCALE = 6


class VatRegimeUnknownError(ApiError):
    code = "purchases.vat_regime_unknown"
    status = 422


class VatUnavailableError(ApiError):
    """The regime exists and its rate cannot be resolved -- typically `draft` (`OD-22`)."""

    code = "purchases.vat_unavailable"
    status = 409


@dataclass(frozen=True, slots=True)
class Position:
    """What a screen states about one line; everything else is derived."""

    description: str
    quantity: Decimal
    unit_price: Decimal
    vat_regime_code: str


def service_line(
    *,
    description: str,
    quantity: Decimal,
    unit_price: Decimal,
    on: date,
    vat_regime_code: str = NO_VAT_REGIME,
) -> LineInput:
    """A position for a service received, priced under the regime the paper states.

    ``on`` is the document's date rather than a clock, so re-entering a March
    invoice in June rounds the way March did and reaches March's rate (`R17`,
    ADR-044). One calculation for every regime, the rate being zero for the line
    without VAT.
    """
    resolved = _resolved(vat_regime_code, on)
    amounts = line_amounts(
        quantity=quantity,
        quantity_scale=SERVICE_QUANTITY_SCALE,
        unit_price=unit_price,
        vat_rate=resolved.rate,
        on=on,
    )
    return LineInput(
        description=description,
        quantity=quantity,
        unit_price=unit_price,
        net_amount=amounts.net,
        vat_regime_code=vat_regime_code,
        vat_rate_key=resolved.rate_key,
        vat_rate=resolved.rate,
        vat_amount=amounts.vat,
        total_amount=amounts.total,
    )


def write_lines(document_id: uuid.UUID, positions: Sequence[Position]) -> None:
    """Replace the document's positions with ``positions``, priced on the document's date."""
    document = get_document(document_id)
    replace_lines(
        document_id,
        [
            service_line(
                description=position.description,
                quantity=position.quantity,
                unit_price=position.unit_price,
                on=document.document_date,
                vat_regime_code=position.vat_regime_code,
            )
            for position in positions
        ],
    )


def _resolved(vat_regime_code: str, on: date) -> RegimeRate:
    if vat_regime_code == NO_VAT_REGIME:
        return RegimeRate(regime_code=NO_VAT_REGIME, rate_key=None, rate=Decimal(0))
    try:
        return regime_rate(vat_regime_code, on)
    except FiscalResolutionError as exc:
        if exc.code == "fiscal.vat_regime_unknown":
            raise VatRegimeUnknownError(str(exc)) from exc
        # `str(exc)` already carries the fiscal code and its own sentence; the
        # frame around it says only what was being priced.
        raise VatUnavailableError(
            f"the rate for {vat_regime_code!r} on {on} cannot be resolved -- {exc}",
            fiscal_code=exc.code,
        ) from exc
