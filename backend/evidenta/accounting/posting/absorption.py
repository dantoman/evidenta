"""The absorption of indirect production costs -- versioned logic, not arithmetic.

SNC "Stocuri" pct. 30 writes the rule out: variable indirect costs enter the
cost of the products in full, whatever the use of capacity; constant ones enter
in proportion to *normal capacity* -- in full when the actual volume reaches
it, otherwise by the ratio of actual to normal, with the remainder taken as
current expenses. That is a formula an act fixes, and an act can change; so it
is selected by the effective date of the period being calculated (R17, R18)
through `fiscal_logic_version`, exactly as the rounding direction is
(`accounting.currency.money`). A build carries every rule it has ever applied;
a row says which one a period used.

What the base of step 2 (pct. 31) is -- wages, direct costs, machine-hours,
quantities, "for example" -- is **not** here: it is an open nomenclature the
entity fixes in its accounting policy (ADR-036 section 11, C5). This module
distributes over whatever base values the fact carries.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from evidenta.accounting.currency.money import Rounding
from evidenta.fiscal.registry.services.resolution import resolve_logic

ABSORPTION_LOGIC_KEY = "production.overhead_absorption"


@dataclass(frozen=True, slots=True)
class Absorbed:
    """What enters the cost of the products, and what stays as current expenses."""

    variable: Decimal
    constant: Decimal
    remainder: Decimal

    @property
    def into_cost(self) -> Decimal:
        return self.variable + self.constant


class Absorption:
    """One versioned reading of pct. 30."""

    ref: str

    def absorb(
        self,
        *,
        variable: Decimal,
        constant: Decimal,
        normal_capacity: Decimal,
        actual_volume: Decimal,
        rule: Rounding,
        scale: int,
    ) -> Absorbed:
        raise NotImplementedError


class NormalCapacityAbsorption(Absorption):
    """pct. 30, in the wording in force from 01.01.2020 (unchanged in substance
    from 2013): the constant part is included by the ratio ``actual / normal``,
    capped at one; the rest is current expenses."""

    ref = "normal_capacity_v1"

    def absorb(
        self,
        *,
        variable: Decimal,
        constant: Decimal,
        normal_capacity: Decimal,
        actual_volume: Decimal,
        rule: Rounding,
        scale: int,
    ) -> Absorbed:
        if normal_capacity <= 0:
            raise ValueError("normal capacity is a positive volume; zero is not a capacity")
        if actual_volume < 0 or variable < 0 or constant < 0:
            raise ValueError("volumes and costs are not negative")
        if actual_volume >= normal_capacity:
            included = constant
        else:
            # The ratio is applied to the amount and reduced once, at the scale
            # in force -- Spec B section 7.4 point 2, one rounding per value.
            included = rule.quantize(constant * actual_volume / normal_capacity, scale)
        return Absorbed(variable=variable, constant=included, remainder=constant - included)


IMPLEMENTATIONS: dict[str, Absorption] = {
    NormalCapacityAbsorption.ref: NormalCapacityAbsorption(),
}


class UnknownAbsorptionError(LookupError):
    """A registry row names a rule this build does not contain."""


def absorption_for(effective_date: date) -> Absorption:
    """The absorption rule in force for the period being calculated."""
    version = resolve_logic(ABSORPTION_LOGIC_KEY, effective_date)
    try:
        return IMPLEMENTATIONS[version.implementation_ref]
    except KeyError:
        raise UnknownAbsorptionError(
            f"{ABSORPTION_LOGIC_KEY} names {version.implementation_ref!r}, which this "
            f"build does not implement; the registry and the code have drifted apart"
        ) from None


def distribute(
    total: Decimal, weights: Sequence[Decimal], *, rule: Rounding, scale: int
) -> list[Decimal]:
    """Split ``total`` over ``weights`` at ``scale``, exactly.

    Each share is the proportional amount reduced once; the **last** share takes
    the residual so the shares sum to the total to the last decimal. That is an
    engineering choice, stated here rather than left to whichever product happened
    to come last: pct. 31 fixes the base, not the treatment of the bani that a
    proportional split leaves over, and a split that did not add up would break
    invariant 1 on the very entry that exists to allocate.
    """
    if not weights:
        raise ValueError("nothing to distribute over")
    if any(w < 0 for w in weights):
        raise ValueError("a base value is not negative")
    denominator = sum(weights, Decimal(0))
    if denominator <= 0:
        raise ValueError("the base sums to zero; nothing can be proportional to it")
    shares = [rule.quantize(total * w / denominator, scale) for w in weights[:-1]]
    shares.append(total - sum(shares, Decimal(0)))
    return shares
