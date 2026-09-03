"""A case enters the corpus by citing; the citation is data a guard can read.

`case(...)` is the only door into the corpus: it records the case in `CASES`
-- which sets it belongs to, which passages it cites -- and applies the
`fiscal_regression` marker with the same data, so `pytest -m fiscal_regression`
selects exactly the corpus. `test_corpus_integrity.py` then checks that every
citation names a passage transcribed in `docs/_input/cercetare/f1-10-corpus-citari.md`
(or a section of an accepted ADR), that every `regression_case_set` the fiscal
registry names is a set with cases in it, and that no test in this package got
in without citing.

Set names follow ``corpus/<key>/<version>`` -- the convention the two shipped
`regression_case_set` values already use (`platform_conventions.toml`,
`snc_stocuri.toml`). ``key`` is the `fiscal_logic_version.logic_key` when the
case pins a versioned rule, and the handler family otherwise.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypeVar

import pytest

F = TypeVar("F", bound=Callable[..., object])

#: Where the cited passages are transcribed, relative to the repository root.
TRANSCRIPTION = "docs/_input/cercetare/f1-10-corpus-citari.md"

# The sets. The first two are the values the fiscal registry names.
ABSORPTION = "corpus/production.overhead_absorption/1"
ROUNDING = "corpus/accounting.money_rounding/1"
SETTLEMENT = "corpus/settlement.differences/1"
REVALUATION = "corpus/revaluation.monetary_items/1"
MONTH_CLOSED = "corpus/period.month_closed/1"
YEAR_CLOSED = "corpus/period.year_closed/1"
MANUAL_NOTE = "corpus/manual.journal_entry/1"
OPENING = "corpus/opening.balances/1"
STORNO = "corpus/manual.reversal/1"


@dataclass(frozen=True, slots=True)
class Case:
    module: str
    name: str
    sets: tuple[str, ...]
    cites: tuple[str, ...]


#: Every case, in import order. Read by the integrity guard, never mutated by a test.
CASES: list[Case] = []


def case(*sets: str, cites: Sequence[str]) -> Callable[[F], F]:
    """Admit one test into the corpus: the sets it belongs to, the passages it cites."""
    if not sets:
        raise ValueError("a case names the set it belongs to: corpus/<key>/<version>")
    if not cites:
        raise ValueError("a case that cannot cite does not enter the corpus")

    def admit(function: F) -> F:
        CASES.append(Case(function.__module__, function.__name__, tuple(sets), tuple(cites)))
        marked: F = pytest.mark.fiscal_regression(sets=tuple(sets), cites=tuple(cites))(function)
        return marked

    return admit
