"""The role vocabulary, and the mapping that is not part of it.

**The vocabulary is code; the mapping is data.** A handler may only ask for a
role this file knows, so a typo is refused at startup rather than discovered at
posting -- that is why the registry insists the catalogue be declared rather than
loaded. But *which account* a role means is an account code, and `R15` is
explicit that account mappings are versioned data with a normative source, never
literals in code.

So the shipped file carries the mapping, the vocabulary is derived from it, and
the two cannot drift apart -- there is one list, not two that agree until
somebody edits one of them.

The mapping itself is the Plan general de conturi, which imposes all four levels:
class, synthetic, subaccount. An entity's own analytics begin at level five. So
there is one correct answer per role, not a configurable default -- and a tenant
whose binding says otherwise is a question, not a preference.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data" / "roles_snc_2020.csv"


@dataclass(frozen=True, slots=True)
class RoleDefault:
    """One role, the subaccount it means, and from when."""

    role: str
    account_code: str
    valid_from: date
    source: str
    #: Dimensions the bound account has to carry -- ADR-048 section 3.1, and
    #: ADR-065 section 8.4 for the case that made it necessary: `employee` on
    #: 5311 and the two personnel-cost accounts. Declared with the role because
    #: the role is what knows its postings will set the value; an account bound
    #: without the slot drops the value silently at placement, and the entry
    #: balances all the same.
    dimension_slots: tuple[str, ...] = ()


def _load() -> tuple[RoleDefault, ...]:
    with DATA.open(encoding="utf-8") as handle:
        return tuple(
            RoleDefault(
                role=row["role"],
                account_code=row["account_code"],
                valid_from=date.fromisoformat(row["valid_from"]),
                source=row["source"],
                dimension_slots=tuple(
                    slot for slot in (row.get("dimension_slots") or "").split(";") if slot
                ),
            )
            for row in csv.DictReader(handle)
        )


DEFAULTS: tuple[RoleDefault, ...] = _load()

#: The vocabulary the registry validates against. Derived, not retyped.
ROLES: frozenset[str] = frozenset(default.role for default in DEFAULTS)
