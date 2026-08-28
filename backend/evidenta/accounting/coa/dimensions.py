"""The closed vocabulary of analytical dimensions -- ADR-029, Spec B section 1.7.

The list lives here, in one place, for two consumers that must not drift apart:

* ``company_account.required_dimensions`` names which of them a posting to that
  account may not omit -- the rule is on the account, not on the line
* ``journal_line`` carries one column per entry, and is built at F1.2

It sits outside ``models.py`` on purpose. The ledger will need the same list, and
a module that imported another module's ``models`` to get at a tuple of strings
would be reported as ``D6`` -- correctly, because that is how a shared constant
turns into shared tables.

Adding a name here is a migration and an ADR. The cap of five generic slots is
deliberate and visible (ADR-029): they are columns on the largest table in the
system, and the alternative without a cap was the one without enforceable
mandatory dimensions.
"""

from __future__ import annotations

#: Named dimensions. The phase in the comment is when the *feature* arrives; the
#: column exists from F1.2 regardless, because adding one to an append-only table
#: later is not a cheap migration.
NAMED_DIMENSIONS = (
    "partner",  # F1
    "item",  # F4
    "employee",  # F2
    "contract",  # F5
    "warehouse",  # F4
    "project",  # direction
    "department",  # F5
    "cost_center",  # F5
    "asset",  # F2
    "production_order",  # direction
)

#: The five generic slots, whose meaning is configured per company in
#: ``company_dimension`` -- a table that arrives with ``journal_line`` at F1.2,
#: not here. What is fixed now is only the vocabulary a company account may
#: require.
GENERIC_SLOTS = ("dim_1", "dim_2", "dim_3", "dim_4", "dim_5")

DIMENSION_KEYS = NAMED_DIMENSIONS + GENERIC_SLOTS

#: How many **typed slots** an account declares and a posting formula carries --
#: ADR-048. Not the same thing as the five generic slots above: those are
#: *columns* of ``journal_line``, one per possible axis; these are *positions*,
#: and what sits in a position is one of the fifteen names, declared per account.
#:
#: Three is the working capacity -- what an account of the plan is expected to
#: use, the same figure 1C's subconto has settled on for twenty years. The fourth
#: is headroom: an account that needs a fourth axis does not reopen the largest
#: tables in the system. Past four, the limit is visible and countable, which is
#: the property ADR-029 chose over an uncounted one.
SLOT_COUNT = 4

#: The column each position lives in, on ``coa_template_account`` and
#: ``company_account`` alike. Generated so the two tables cannot disagree on the
#: names; written out on the models, where a loop would hide the schema.
SLOT_FIELDS = tuple(f"slot_{n}_dimension" for n in range(1, SLOT_COUNT + 1))
