"""The trial balance -- one row per account, from the ledger and nothing else.

Aggregated in the database, not in the client (C19). A total computed over a
paginated or virtualised set is wrong by construction, and in an accounting
report a wrong total is a serious defect rather than a cosmetic one.

**The opening balance is a sum over everything before the window**, not a stored
figure. There is no balance table at F1 and there should not be one yet: a
denormalised balance is a second answer to a question the ledger already answers,
and the two drift the first time a posting arrives out of order. When volume
makes the scan too slow, the fix is a materialised read model with the ledger
still the source (R7) -- not a column somebody remembers to update.

The window is half-open on neither side: both ends are inclusive, because an
accountant asks for "March" as 1 to 31 March and a report that quietly excluded
the last day would be wrong in the direction nobody checks.

Signs: debit-positive throughout. `opening` and `closing` are signed, and which
column they belong in is decided when they are rendered, from the sign -- not
from the account's normal balance. An account with a balance on the unusual side
is a fact worth seeing, and folding it into the expected column would hide it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce

from evidenta.accounting.coa.services.accounts import names_for
from evidenta.accounting.ledger.models import JournalLine

ZERO = Value(Decimal("0"), output_field=DecimalField(max_digits=20, decimal_places=4))


@dataclass(frozen=True, slots=True)
class TrialBalanceRow:
    account_id: uuid.UUID
    account_code: str
    name_ro: str
    opening: Decimal
    debit: Decimal
    credit: Decimal
    closing: Decimal


@dataclass(frozen=True, slots=True)
class TrialBalance:
    start_date: date
    end_date: date
    rows: tuple[TrialBalanceRow, ...]

    @property
    def total_debit(self) -> Decimal:
        return sum((row.debit for row in self.rows), Decimal("0"))

    @property
    def total_credit(self) -> Decimal:
        return sum((row.credit for row in self.rows), Decimal("0"))

    @property
    def balanced(self) -> bool:
        """Σ debit = Σ credit over the window.

        It holds per entry already (R11, checked in the database), so this can
        only be false if a line was written outside the engine -- which is what
        makes it worth displaying rather than assuming.
        """
        return self.total_debit == self.total_credit


def trial_balance(company_id: uuid.UUID, start_date: date, end_date: date) -> TrialBalance:
    """Every account with movement in the window, or a balance before it."""
    before = Q(accounting_date__lt=start_date)
    inside = Q(accounting_date__gte=start_date, accounting_date__lte=end_date)

    # One query, grouped by account. `filter=` on each aggregate is what keeps it
    # one: three separate queries would have to be reconciled by hand afterwards,
    # and the reconciliation is the part that goes wrong.
    aggregated = (
        JournalLine.objects.filter(company_id=company_id, accounting_date__lte=end_date)
        .values("account_id")
        .annotate(
            opening_debit=Coalesce(Sum("debit", filter=before), ZERO),
            opening_credit=Coalesce(Sum("credit", filter=before), ZERO),
            debit=Coalesce(Sum("debit", filter=inside), ZERO),
            credit=Coalesce(Sum("credit", filter=inside), ZERO),
        )
    )

    totals = {row["account_id"]: row for row in aggregated}
    if not totals:
        return TrialBalance(start_date=start_date, end_date=end_date, rows=())

    # The chart is read separately and joined here rather than in SQL: a journal
    # line carries no foreign key to the account (R21), so there is nothing for
    # the database to join on -- the link is by id, deliberately, and it points
    # the other way. Asked of `coa` through its service, never through its models
    # (D6).
    named = names_for(company_id, list(totals))

    rows = []
    for account_id, sums in totals.items():
        naming = named.get(account_id)
        if naming is None:
            # A line pointing at an account this context cannot see. Not skipped
            # silently: it is shown with the id in place of a name, because a
            # missing row would make the balance not balance and nothing would
            # say why.
            code, name = str(account_id), ""
        else:
            code, name = naming

        opening = sums["opening_debit"] - sums["opening_credit"]
        rows.append(
            TrialBalanceRow(
                account_id=account_id,
                account_code=code,
                name_ro=name,
                opening=opening,
                debit=sums["debit"],
                credit=sums["credit"],
                closing=opening + sums["debit"] - sums["credit"],
            )
        )

    rows.sort(key=lambda row: row.account_code)
    return TrialBalance(start_date=start_date, end_date=end_date, rows=tuple(rows))
