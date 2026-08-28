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

from datetime import date
from decimal import Decimal

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
    parameter = resolve_parameter(VAT_REGIMES_KEY, on)
    if parameter.value_type != ValueType.TABLE:
        raise NotAVatParameterError(
            f"{VAT_REGIMES_KEY!r} is registered as {parameter.value_type}; the "
            f"regime vocabulary is a table of codes"
        )
    value = parameter.value
    codes = value.get("codes") if isinstance(value, dict) else value
    if not isinstance(codes, list):
        raise NotAVatParameterError(
            f"{VAT_REGIMES_KEY!r} holds {type(codes).__name__}, not a list of codes"
        )
    return tuple(str(code) for code in codes)


def assert_regime(regime_code: str, on: date) -> None:
    """Refuse a regime the nomenclature does not list.

    **Not called by the document layer today**, and the reason is written down
    rather than left to be discovered: the vocabulary is not loaded (`OD-22`), so
    calling it would refuse every document ever entered -- a guard that blocks
    everything gets worked around, and a worked-around guard guards nothing. It
    is wired the moment the nomenclature lands, and the document layer meanwhile
    enforces only that a regime was stated at all.
    """
    valid = vat_regimes(on)
    if regime_code not in valid:
        raise VatRegimeUnknownError(
            f"{regime_code!r} is not a VAT regime in force on {on}; the "
            f"nomenclature lists {list(valid)}"
        )


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
