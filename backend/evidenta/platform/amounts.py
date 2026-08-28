"""The numeric scales every stored amount, quantity, price and rate uses.

One place, because the brief for the document layer asks for exactly that:
*"Sumele: Decimal, precizie fixă, definită într-un singur loc."* Two places is
how a line total stored at four decimals meets a journal line stored at two and
the difference surfaces as bani nobody can attribute.

It sits in `platform` rather than in `accounting.currency`, where the first two
constants were born, for a mechanical reason: the document core is a `platform`
module and `platform` imports nothing (the dependency graph, `DG`). A constant
the document tables cannot read is not a single place, it is a comment.
`accounting.currency.money` re-exports the two it published, so nothing that
already imports them changes.

**What is fixed here and what is not.** Storage scale is a storage decision and
Spec B section 1.3 already made it. The *rounding rule* that reduces an exact
intermediate result to one of these scales is versioned fiscal logic (R16, R17),
lives in `fiscal_logic_version`, and is still open -- DNB-08, ADR-037. Nothing in
this module rounds, and nothing importing it may read a scale as permission to.
"""

from __future__ import annotations

#: Digits available to every stored `numeric`. Generous on purpose: the scale is
#: the decision that matters, and a shared precision means an amount cannot
#: overflow on its way from a document line to a journal line.
AMOUNT_DIGITS = 20

#: Amounts in the transaction currency -- Spec B section 1.3.
CURRENCY_SCALE = 4

#: Exchange rates -- Spec B section 7.2, MDL per unit of foreign currency
#: (ADR-039, DN-04).
RATE_DIGITS = 18
RATE_SCALE = 8

#: Quantities on a document line. Six, matching the ceiling
#: `unit_of_measure.decimal_places` already enforces and the scale
#: `unit_conversion` already stores its ratio at -- so a quantity converted
#: between two units is not silently truncated by the column it lands in.
QUANTITY_SCALE = 6

#: Unit prices. Deliberately finer than `CURRENCY_SCALE`: ADR-037 section 3.2
#: records that on a real invoice the unit price is the one value that routinely
#: carries more than two decimals, and a price rounded at entry makes the line
#: total unreconstructable from what the document shows.
UNIT_PRICE_SCALE = 6

#: Rates and discounts expressed as a percentage -- `20.0000`, not `0.20`.
#: Stored as written on the document, because that is what a control reads back.
PERCENT_DIGITS = 9
PERCENT_SCALE = 4
