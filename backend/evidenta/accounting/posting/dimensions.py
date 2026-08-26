"""Mandatory analytical dimensions, refused by the engine -- F1.1.3, ADR-029.

Spec B section 1.7 puts the rule on the **account**, not on the line:
``company_account.required_dimensions`` names which of the fifteen a posting to
that account may not omit. Spec B section 1.5 then names this among the four
things the engine checks before a manual note is posted -- balance, accounts,
open period, mandatory dimensions.

**Why this is not one of the six invariants.** ADR-036 section 5.2 lists what is
true of *every* posting; this is true of every posting *to a particular account*,
and the difference shows in where the answer comes from. The six are decided from
the proposal itself plus the calendar and the chart; this one is decided by a
column the tenant configures. So it is a separate check, run after `verify`, and
it refuses with its own code.

**It is the mechanism ADR-029 defended.** The `jsonb` variant rejected there could
hold the same values; what it could not do is let an account require one, because
nothing could be indexed or constrained. A dimension that cannot be made
mandatory is a dimension that is missing on the rows that matter, discovered when
a partner ledger does not add up to the account.

**A second read of the chart, and the cost is accepted.** `invariants._check_accounts`
has already loaded the postable accounts to answer invariant 4; this loads them
again to read one more column. Widening the invariant module's return value to
hand them over would change a contract delivered a task ago, for a query on a
table with hundreds of rows per company. If bulk posting ever makes it matter,
the fix is one call site, not a redesign.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from evidenta.accounting.coa.services.accounts import postable_accounts
from evidenta.accounting.posting.invariants import (
    AccountNotPostableError,
    PostingRefusedError,
)


class MissingRequiredDimensionError(PostingRefusedError):
    """A line omits a dimension its account requires.

    Refused rather than posted with a NULL, and the reason is that the NULL is
    invisible afterwards. The entry balances, the trial balance is right, and the
    only report that would show the gap is the one nobody runs -- the partner
    ledger of an account whose partner was never filled in.
    """

    code = "posting.missing_required_dimension"


@dataclass(frozen=True, slots=True)
class LineDimensions:
    """What one proposed line names, in the vocabulary of ADR-029.

    Keyed by dimension name (``partner``, ``dim_1``), never by column name. The
    column is ``journal_line``'s business, and a check that spoke in columns would
    have to be edited whenever the two conventions were reconciled.

    Deliberately not the whole line. This check needs the account and the set of
    dimensions that carry a value; giving it the full line would tie it to a
    handler contract that is not written yet (F1.4.4).
    """

    account_id: uuid.UUID
    present: Mapping[str, uuid.UUID | None]

    def named(self) -> set[str]:
        """The dimensions actually carrying a value.

        A key present with ``None`` is the same as an absent key: the column would
        hold NULL either way, and treating an explicit ``None`` as satisfying a
        requirement would make the requirement satisfiable by mentioning it.
        """
        return {key for key, value in self.present.items() if value is not None}


def assert_dimensions_present(
    company_id: uuid.UUID, on_date: date, lines: Sequence[LineDimensions]
) -> None:
    """Refuse the posting if any line omits a dimension its account requires.

    Judged at the posting's date, like invariant 4 and for the same reason: an
    entry has one date, and asking the chart a different question per line would
    let one entry be checked against two charts.
    """
    required = {
        account.id: frozenset(account.required_dimensions)
        for account in postable_accounts(company_id, on_date)
    }

    for number, line in enumerate(lines, start=1):
        wanted = required.get(line.account_id)
        if wanted is None:
            # `verify` refuses this before the check ever runs. Reachable only by
            # calling this directly, and silence would then be an account with
            # unknown requirements treated as an account with none.
            raise AccountNotPostableError(
                f"line {number} names account {line.account_id}, which cannot "
                f"receive a posting dated {on_date.isoformat()}"
            )
        missing = sorted(wanted - line.named())
        if missing:
            raise MissingRequiredDimensionError(
                f"line {number} on account {line.account_id} omits "
                f"{', '.join(missing)}, which that account requires on every "
                f"posting; a NULL there is invisible in every total the entry "
                f"appears in"
            )
