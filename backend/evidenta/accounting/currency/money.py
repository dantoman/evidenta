"""The amount model -- Spec B section 7.1.

A journal line carries four elements, and storing all four is a **legal
requirement**, not a design preference:

    Law 287/2017, art. 7(2): "Contabilitatea faptelor economice efectuate in
    valuta straina se tine atit in moneda nationala, cit si in valuta straina,
    in conformitate cu standardele de contabilitate."

The technical reason sits on top of that rather than replacing it: rates change
and a posted entry is immutable (R10), so the functional-currency amount has to
stay exactly what it was, not what a recomputation would produce today. Being a
legal requirement, this model is not a candidate for a later performance pass.

**Nothing here rounds.** `Decimal` throughout, exact arithmetic, and the one
operation that must round -- deriving the functional amount -- refuses to do it
without a rounding rule resolved from the fiscal registry for the period being
posted. That is Spec B section 7.4 point 3, and it is the whole reason this
module has no `round_money()` in it: a rounding helper in a utilities module is
exactly the shape in which a fiscal rule ends up unmarked in code, and DNB-08 --
which of half-up, half-even, or something the SFS validator imposes -- is open.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
from typing import Protocol

from evidenta.fiscal.parameters.services.scales import amount_scale
from evidenta.fiscal.registry.services.resolution import resolve_logic
from evidenta.platform.amounts import CURRENCY_SCALE, RATE_SCALE

#: Re-exported, not defined here. The scales moved to `platform.amounts` when the
#: document layer arrived: a document line and a journal line have to be stored
#: at the same scale, and `platform` cannot import `accounting`. Keeping the
#: names here means nothing that already imports them from this module changes,
#: and there is still exactly one place the numbers live.
#:
#: `CURRENCY_SCALE` is a storage decision, already made (Spec B section 1.3). It
#: is not the rounding precision of the functional amount, which is DNB-08 point
#: (a) and open.
__all__ = [
    "CURRENCY_SCALE",
    "RATE_SCALE",
    "ConvertedAmount",
    "CurrencyMismatchError",
    "DecimalRounding",
    "Money",
    "Rounding",
    "UnknownImplementationError",
    "convert",
    "rounding_for",
]

#: The `logic_key` under which the money rounding rule is registered. No version
#: is registered yet, deliberately -- see `Rounding` below.
ROUNDING_LOGIC_KEY = "accounting.money_rounding"


class CurrencyMismatchError(ValueError):
    """Two amounts in different currencies met in an operation that needs one.

    Not a subclass of anything catchable by accident: adding MDL to EUR has no
    right answer, and producing one by picking a rate would be a conversion
    nobody asked for and nobody can trace.
    """


@dataclass(frozen=True, slots=True)
class Money:
    """An exact amount in one currency.

    Frozen because an amount that can be mutated in place is an amount whose
    history is a matter of trust. Every operation returns a new value.

    `amount` is a `Decimal` and stays one. `float` is refused at construction
    rather than converted: `float` makes the same trial balance produce different
    results depending on aggregation order, and the failure appears as a few bani
    that nobody can attribute to anything.
    """

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            raise TypeError(
                f"amount must be Decimal, got {type(self.amount).__name__}. "
                f"Converting silently is how a float reaches a ledger."
            )
        if len(self.currency) != 3 or not self.currency.isupper():
            raise ValueError(
                f"currency must be a three-letter ISO 4217 code, got {self.currency!r}"
            )

    def __add__(self, other: Money) -> Money:
        self._same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._same_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.amount, self.currency)

    def _same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                f"cannot combine {self.currency} and {other.currency} without an "
                f"explicit conversion"
            )

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"


class Rounding(Protocol):
    """What a registered rounding rule has to provide.

    A protocol rather than a function, because the rule is **versioned fiscal
    logic** (`R16`): it is selected from `fiscal_logic_version` by the effective
    date of the period being calculated, so recalculating a 2026 period in 2030
    uses the 2026 rule.

    ``scale`` is an argument rather than a property of the implementation, and
    that split is the point: **the direction at a tie is versioned code, the
    number of decimals is versioned data.** They move independently -- an
    instruction can change the precision on a form without touching how a tie
    resolves -- and folding them together would make a change to either one a
    deployment.
    """

    def quantize(self, value: Decimal, scale: int) -> Decimal:
        """Reduce an exact intermediate result to postable precision."""
        ...


@dataclass(frozen=True, slots=True)
class DecimalRounding:
    """One tie-breaking direction, applied at whatever scale it is handed.

    Both directions exist in the repository; **neither is chosen here.** Which
    one runs is a row in `fiscal_logic_version`, selected by the effective date --
    so the answer lives in data, and a period recalculated years later reaches
    the direction that was in force then.
    """

    mode: str

    def quantize(self, value: Decimal, scale: int) -> Decimal:
        if scale < 0:
            raise ValueError(f"a scale is a count of decimals, not {scale}")
        return value.quantize(Decimal(1).scaleb(-scale), rounding=self.mode)


#: Registered rounding implementations, by `implementation_ref`.
#:
#: **A registry row names a key in this table; it never names an importable
#: path.** The difference is the whole security property. `fiscal_logic_version`
#: is written through privileged path P-4, and a row whose `implementation_ref`
#: were fed to an import would turn one privileged INSERT into arbitrary code
#: execution inside the application role -- and the dependency guard, which reads
#: the AST, cannot see a dynamic import at all.
#:
#: So the registry **selects** among implementations that exist in this
#: repository. It does not load them from anywhere.
#:
#: The two directions a tie can resolve in. **Having both here is not choosing
#: between them** -- the registry row does that, by effective date. What was
#: refused before, and is still refused, is a single hard-coded rule with no way
#: to say which period it applies to.
#:
#: ADR-037 section 3.3 called the tie direction a plaster for a symptom: the
#: divergence between the sum of the lines and a total recomputed on the total
#: base. That symptom is gone by construction -- the line is authoritative and the
#: document total is the sum of the lines, so there are never two competing
#: calculations. What remains is a convention, and a convention belongs in data.
IMPLEMENTATIONS: dict[str, Rounding] = {
    "half_up": DecimalRounding(ROUND_HALF_UP),
    "half_even": DecimalRounding(ROUND_HALF_EVEN),
}


class UnknownImplementationError(LookupError):
    """A registry row names a rule this build does not contain."""


def rounding_for(effective_date: date) -> Rounding:
    """The rounding rule in force for the period being posted -- R17, R18.

    Raises through `resolve_logic` when nothing is registered. That is a refusal,
    not a gap: a build with no registered direction has no rule for the period
    being calculated, and rounding anyway would produce a number nobody can
    defend three years later.
    """
    version = resolve_logic(ROUNDING_LOGIC_KEY, effective_date)
    try:
        return IMPLEMENTATIONS[version.implementation_ref]
    except KeyError:
        raise UnknownImplementationError(
            f"fiscal_logic_version {version.version!r} names "
            f"{version.implementation_ref!r}, which this build does not contain. "
            f"A registry row selects an implementation; it never imports one."
        ) from None


@dataclass(frozen=True, slots=True)
class ConvertedAmount:
    """The four elements of Spec B section 7.1, produced together.

    Together rather than separately because separately is how they drift: an
    amount and a rate recorded in two operations can end up describing different
    moments, and the entry is immutable once posted, so the disagreement is
    permanent.
    """

    amount_currency: Decimal
    currency: str
    exchange_rate: Decimal
    functional_amount: Decimal
    functional_currency: str

    @property
    def original(self) -> Money:
        return Money(self.amount_currency, self.currency)

    @property
    def functional(self) -> Money:
        return Money(self.functional_amount, self.functional_currency)


def convert(
    original: Money,
    *,
    functional_currency: str,
    exchange_rate: Decimal,
    effective_date: date,
) -> ConvertedAmount:
    """Derive the functional-currency amount -- Spec B section 7.1.

    `functional = round(amount_currency * exchange_rate)`, with the rounding rule
    resolved for `effective_date`. The multiplication is exact and happens once;
    Spec B section 7.4 point 2 requires intermediate work at higher precision
    than posting, and rounding applied a single time, at the point the journal
    line is produced.

    An amount already in the functional currency still passes through, with a
    rate of exactly 1 -- Spec B section 1.3 stores 1 rather than NULL, so the
    derivation rule has no special case and `CHECK (exchange_rate > 0)` needs no
    exception.
    """
    if not isinstance(exchange_rate, Decimal):
        raise TypeError("exchange_rate must be Decimal, never float")
    if exchange_rate <= 0:
        raise ValueError("exchange_rate must be positive; a zero rate erases the amount")
    if original.currency == functional_currency and exchange_rate != Decimal(1):
        raise ValueError(
            f"an amount already in {functional_currency} converts at exactly 1, not {exchange_rate}"
        )

    rule = rounding_for(effective_date)
    scale = amount_scale(effective_date)
    return ConvertedAmount(
        amount_currency=original.amount,
        currency=original.currency,
        exchange_rate=exchange_rate,
        functional_amount=rule.quantize(original.amount * exchange_rate, scale),
        functional_currency=functional_currency,
    )
