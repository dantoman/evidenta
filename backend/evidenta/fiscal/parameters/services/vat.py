"""Reading a VAT rate and the regime vocabulary out of the nomenclature.

Thin on purpose. It composes no rate, applies no rule and contains no number: it
resolves a **key** against `fiscal_parameter` by an effective date and hands back
what the act says, with the type checked so a threshold cannot be read as a
percentage.

**No rate appears in this repository.** `R15` makes rates data with provenance --
the act, the Monitorul Oficial issue, the publication and effective dates -- and
`OD-22` is the open task of loading them from citable sources. Until a rate is
loaded, every call here refuses, and that refusal is the correct behaviour: a
missing rate is not a rate of zero, and a document produced with an invented one
is wrong in a way nobody notices until an inspection.

**The regime vocabulary is data too.** Which VAT treatments exist -- taxable at
the standard rate, reduced, zero-rated on export, exempt with or without
deduction, reverse charge -- comes from the Cod fiscal and changes by act. It is
therefore a parameter, not an enum in code, and this module reads it rather than
declaring it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from evidenta.fiscal.parameters.models import FiscalParameter, ValueType
from evidenta.fiscal.parameters.services.resolution import (
    FiscalResolutionError,
    resolve_parameter,
)

#: The namespace VAT parameters live under. A guard rather than a builder: the
#: caller passes a full key (`item.vat_rate_key` carries one), and this refuses a
#: key from another namespace so a payroll ceiling cannot be read as a rate
#: because two keys happened to be confused upstream.
VAT_NAMESPACE = "vat."

#: The key the list of valid regime codes is registered under, when it is.
VAT_REGIMES_KEY = "vat.regimes"


class NotAVatParameterError(FiscalResolutionError):
    def __init__(self, message: str) -> None:
        super().__init__("fiscal.not_a_vat_parameter", message)


class VatRegimeUnknownError(FiscalResolutionError):
    def __init__(self, message: str) -> None:
        super().__init__("fiscal.vat_regime_unknown", message)


def vat_rate(rate_key: str, on: date) -> Decimal:
    """The rate in force on ``on``, as a percentage -- ``20``, not ``0.20``.

    ``on`` is required and there is no default. Which rate applies is decided by
    the date of the economic fact, never by the date of the calculation
    (ADR-044): recalculating March in June has to return March's rate, or the
    fiscal regression corpus `C14` asks for would depend on the day it is run.

    Raises when nothing is registered. That is the current state and it is the
    honest one.
    """
    if not rate_key.startswith(VAT_NAMESPACE):
        raise NotAVatParameterError(
            f"{rate_key!r} is not a VAT parameter key; VAT parameters live under "
            f"{VAT_NAMESPACE!r}, and reading one from another namespace is how a "
            f"threshold ends up applied as a rate"
        )
    parameter = resolve_parameter(rate_key, on)
    if parameter.value_type != ValueType.PERCENTAGE:
        raise NotAVatParameterError(
            f"{rate_key!r} is registered as {parameter.value_type}, not a percentage"
        )
    return _as_decimal(parameter)


def vat_regimes(on: date) -> tuple[str, ...]:
    """The regime codes valid on a date, as the nomenclature lists them.

    Returns a tuple so a caller cannot edit the vocabulary it was handed. Raises
    when the list is not loaded -- `OD-22` -- rather than returning an empty one:
    an empty vocabulary would make every regime look invalid, which reads as a
    data-entry error rather than as a missing nomenclature.
    """
    codes, _ = _regimes_table(on)
    return codes


def assert_regime(regime_code: str, on: date) -> None:
    """Refuse a regime the nomenclature does not list.

    Called by the document layer through `regime_rate` since step 6 (ADR-089):
    a line that states a regime other than *no VAT* is priced from the
    nomenclature, and a regime the nomenclature does not list cannot be priced.
    While the vocabulary is `draft` (`OD-22`) that refusal is the honest state --
    a company that is registered for VAT cannot issue a VAT invoice until the
    rates it would print are activated from a citable act.
    """
    valid = vat_regimes(on)
    if regime_code not in valid:
        raise VatRegimeUnknownError(
            f"{regime_code!r} is not a VAT regime in force on {on}; the "
            f"nomenclature lists {list(valid)}"
        )


@dataclass(frozen=True, slots=True)
class RegimeRate:
    """What a regime resolves to on a date: the rate, and the key it came from.

    ``rate_key`` is ``None`` for a regime that carries no rate -- the exempt
    categories -- and the rate is then zero. Kept beside the rate rather than
    dropped, because a document line stores both (`R18`): recalculating the line
    later must reach the same parameter row, not merely the same number.
    """

    regime_code: str
    rate_key: str | None
    rate: Decimal


def regime_rate(regime_code: str, on: date) -> RegimeRate:
    """The rate a regime applies on ``on``, resolved from the nomenclature.

    Two lookups, both data: the ``vat.regimes`` table says which regimes exist
    and which **parameter key** each taxable one resolves through; the key then
    resolves to the percentage in force on the date. Nothing here knows that the
    standard rate is twenty: it knows that ``taxable_standard`` reads
    ``vat.standard``, and that is form, not a value.

    A regime the table lists without a key carries no rate -- zero, no key. That
    is all the absence says: whether an exempt supply gives a right of deduction
    (art. 103 against art. 104) is not read from here.
    """
    codes, rates = _regimes_table(on)
    if regime_code not in codes:
        raise VatRegimeUnknownError(
            f"{regime_code!r} is not a VAT regime in force on {on}; the "
            f"nomenclature lists {list(codes)}"
        )
    rate_key = rates.get(regime_code)
    if rate_key is None:
        return RegimeRate(regime_code=regime_code, rate_key=None, rate=Decimal(0))
    return RegimeRate(regime_code=regime_code, rate_key=rate_key, rate=vat_rate(rate_key, on))


def _regimes_table(on: date) -> tuple[tuple[str, ...], dict[str, str]]:
    """The vocabulary as stored: the codes, and the rate key of each taxable one."""
    parameter = resolve_parameter(VAT_REGIMES_KEY, on)
    if parameter.value_type != ValueType.TABLE:
        raise NotAVatParameterError(
            f"{VAT_REGIMES_KEY!r} is registered as {parameter.value_type}; the "
            f"regime vocabulary is a table of codes"
        )
    value: Any = parameter.value
    codes = value.get("codes") if isinstance(value, dict) else value
    if not isinstance(codes, list):
        raise NotAVatParameterError(
            f"{VAT_REGIMES_KEY!r} holds {type(codes).__name__}, not a list of codes"
        )
    rates = value.get("rates", {}) if isinstance(value, dict) else {}
    if not isinstance(rates, dict):
        raise NotAVatParameterError(
            f"{VAT_REGIMES_KEY!r} holds {type(rates).__name__} under 'rates', not a "
            f"map from regime code to rate key"
        )
    for code, key in rates.items():
        if code not in codes:
            raise NotAVatParameterError(
                f"{VAT_REGIMES_KEY!r} names a rate for {code!r}, which is not a listed regime"
            )
        if not isinstance(key, str) or not key.startswith(VAT_NAMESPACE):
            raise NotAVatParameterError(
                f"{VAT_REGIMES_KEY!r} resolves {code!r} through {key!r}, which is not a "
                f"VAT parameter key"
            )
    return tuple(str(code) for code in codes), {str(c): str(k) for c, k in rates.items()}


def _as_decimal(parameter: FiscalParameter) -> Decimal:
    """The stored value as an exact `Decimal`.

    `float` is refused rather than converted. A rate that arrived as a float
    makes the same invoice total differently depending on the order the lines
    were added, and the difference surfaces as bani nobody can attribute.
    """
    value = parameter.value
    if isinstance(value, dict):
        value = value.get("value")
    if isinstance(value, float):
        raise NotAVatParameterError(
            f"{parameter.parameter_key!r} is stored as a float. A rate reaches a "
            f"document as an exact decimal or not at all."
        )
    if not isinstance(value, str | int):
        raise NotAVatParameterError(
            f"{parameter.parameter_key!r} holds {type(value).__name__}, which is not a rate"
        )
    return Decimal(str(value))
