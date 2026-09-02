"""Building a document position -- and, since step 6, pricing its VAT.

The catalogue supplies the **identity** of a position: what it is called on a
document, in which unit, and under which VAT rate key. The amounts are produced
by `accounting.currency.services.amounts.line_amounts`, which applies the rule
the owner decided: **VAT is calculated and rounded on each line, and the document
total is the sum of the lines.** Where the rounding happens is therefore settled;
what remains data is how many decimals (a fiscal parameter), which direction a
tie resolves in (a row in the logic registry), and -- since ADR-089 -- which rate
a regime carries (`vat.regimes` names the key, the key names the percentage).

**The regime is stated, never defaulted.** A line says under which VAT treatment
it is issued, and the two facts that decide whether that statement is admissible
are read here, not on the screen: the company's registration on the document's
date (ADR-088), and the nomenclature in force on it. A company that is not a VAT
payer on that day may issue only lines without VAT; one that is a payer states a
regime for every line, because *no VAT* is a status, not a treatment.

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
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from evidenta.accounting.currency.services.amounts import line_amounts
from evidenta.fiscal.parameters.services.resolution import FiscalResolutionError
from evidenta.fiscal.parameters.services.vat import RegimeRate, regime_rate, vat_rate
from evidenta.masterdata.items.services.catalogue import entry_for
from evidenta.platform.api.errors import ApiError
from evidenta.platform.documents.services.lifecycle import get_document
from evidenta.platform.documents.services.lines import LineInput, replace_lines
from evidenta.platform.tenancy.services.tax_status import tax_status_at

#: The regime code a line without VAT carries: the issuer is not a VAT payer on
#: the document's date. A **status**, not a treatment -- it is not in the
#: nomenclature and resolves to no rate, and a registered company may not use it.
NO_VAT_REGIME = "fara_tva"

#: A position for a service has no unit of measure, so no unit declares its
#: precision (ADR-055). What bounds it is what the API accepts for a quantity,
#: and that bound is passed to the calculator as the line's scale rather than
#: left implicit in a serializer.
SERVICE_QUANTITY_SCALE = 6


class ItemHasNoVatRateError(ApiError):
    """The catalogue entry names no VAT rate key.

    Refused rather than defaulted to the standard rate. Which treatment applies
    to an item is a fiscal fact about that item, and a default here would put the
    standard rate on a medicine, an export or an exempt service without anybody
    choosing it.
    """

    code = "sales.item_has_no_vat_rate"
    status = 422


class VatRegimeUnknownError(ApiError):
    """The regime is not one the nomenclature lists on the document's date."""

    code = "sales.vat_regime_unknown"
    status = 422


class VatUnavailableError(ApiError):
    """The regime exists and its rate cannot be resolved -- typically `draft` (`OD-22`).

    A refusal, never a rate of zero: the message names the fiscal code and the
    key, so what is missing is an activation, not a feature.
    """

    code = "sales.vat_unavailable"
    status = 409


class VatRegimeRequiresRegistrationError(ApiError):
    """A VAT treatment on a document of a company that is not a VAT payer on its date."""

    code = "sales.vat_regime_requires_registration"
    status = 422


class RegisteredCompanyStatesRegimeError(ApiError):
    """A registered company issued a line under *no VAT*, which is a status it does not have."""

    code = "sales.vat_regime_required"
    status = 422


@dataclass(frozen=True, slots=True)
class Position:
    """What a screen states about one line; everything else is derived."""

    description: str
    quantity: Decimal
    unit_price: Decimal
    vat_regime_code: str


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
    vat_regime_code: str = NO_VAT_REGIME,
) -> LineInput:
    """A position for a service, priced under one VAT regime.

    **The amounts are derived here and not by the caller**, and this is the only
    place in this module that derives any. The document core stores what it is
    told, so somebody has to do the arithmetic, and a screen doing it would be a
    second implementation of the rounding rule. `line_amounts` is that rule --
    net rounded once, VAT rounded once on the rounded net, total their exact sum
    -- and it is called for the line without VAT too, with a rate of zero, so
    there is one calculation and not one per regime.

    ``vat_regime_code`` selects the rate through the nomenclature (`regime_rate`);
    the code without VAT resolves to nothing and asks the nomenclature nothing,
    because it is not a regime. Whether the company may use one or the other is
    `write_lines`'s question, not this function's: this one prices what it is
    told, for a caller that has already decided.

    No item: this is the line a service invoice carries, and the catalogue's
    version is `line_from_catalogue`.
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
    """Replace the document's positions with ``positions``, each priced for its regime.

    The admissibility rule lives here, once, for both the create and the replace
    route: the company's VAT status **on the document's date** (ADR-088) decides
    what a line may state. Not registered -- only lines without VAT; a treatment
    stated anyway is refused, because an invoice with VAT from a company that is
    not a payer is a document the law does not allow it to issue. Registered --
    every line states a regime; *no VAT* is refused, because for a payer it is
    not a treatment but a claim about status, and the status says otherwise.

    Read from the document rather than passed in, so the two routes cannot be
    given two different dates for one document.

    **The status is checked before any line is priced.** Pricing needs the
    nomenclature, and while that is `draft` its refusal names a parameter -- a
    correct sentence about the wrong thing for a company that is simply not a
    payer. The company's own status is the more informative refusal, so it comes
    first; the nomenclature answers only for a company that may state a regime.
    """
    document = get_document(document_id)
    on = document.document_date
    registered = bool(tax_status_at(document.company_id, on)["vat"]["registered"])

    for position in positions:
        stated = position.vat_regime_code
        if stated == NO_VAT_REGIME and registered:
            raise RegisteredCompanyStatesRegimeError(
                f"the company is registered for VAT on {on}; a line states the regime it "
                f"is issued under -- taxable or exempt -- and {NO_VAT_REGIME!r} is not one"
            )
        if stated != NO_VAT_REGIME and not registered:
            raise VatRegimeRequiresRegistrationError(
                f"the company is not registered for VAT on {on}, so it cannot issue a line "
                f"under {stated!r}; only {NO_VAT_REGIME!r} is admissible on that day"
            )

    replace_lines(
        document_id,
        [
            service_line(
                description=position.description,
                quantity=position.quantity,
                unit_price=position.unit_price,
                on=on,
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
