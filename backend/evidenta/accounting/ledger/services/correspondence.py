"""Turnover by correspondence (*rulaje pe conturi corespondente*, the "șah") -- F1.8.

Every pair of accounts that moved against each other in the window, with the
amount: the chess-board report, one cell per (debit account, credit account).
It reads straight off ``journal_formula`` (ADR-048) -- the formula is the pair --
and needs no reconstruction from lines, which is the report ADR-048 §2.1 said
could not be built on lines alone.

**What it cannot see, it says.** A lines-only entry -- the manual note -- has no
formulas, so its turnover is in no cell. The report carries the window's total
debit turnover from the lines beside the total of the cells, and the difference
is the amount the chess-board does not explain. Reported, never spread.

Totals are the server's (C19): per debit account, per credit account, and the
grand total.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce

from evidenta.accounting.coa.services.accounts import names_for
from evidenta.accounting.ledger.models import JournalFormula, JournalLine

ZERO = Value(Decimal("0"), output_field=DecimalField(max_digits=20, decimal_places=4))


@dataclass(frozen=True, slots=True)
class Cell:
    debit_account_id: uuid.UUID
    debit_code: str
    credit_account_id: uuid.UUID
    credit_code: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class AccountTotal:
    account_id: uuid.UUID
    account_code: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class Correspondence:
    start_date: date
    end_date: date
    cells: tuple[Cell, ...]
    debit_totals: tuple[AccountTotal, ...]
    credit_totals: tuple[AccountTotal, ...]
    #: Σ of the cells.
    total: Decimal
    #: Σ debit of every line in the window -- what the register actually moved.
    lines_total: Decimal
    #: `lines_total - total`: turnover no formula explains.
    unassigned: Decimal


def correspondence(company_id: uuid.UUID, start_date: date, end_date: date) -> Correspondence:
    """Every (debit, credit) pair over ``[start_date, end_date]``, both ends inclusive."""
    cells = list(
        JournalFormula.objects.filter(
            company_id=company_id,
            accounting_date__gte=start_date,
            accounting_date__lte=end_date,
        )
        .values("debit_account_id", "credit_account_id")
        .annotate(amount=Coalesce(Sum("amount"), ZERO))
    )
    lines_total = JournalLine.objects.filter(
        company_id=company_id, accounting_date__gte=start_date, accounting_date__lte=end_date
    ).aggregate(debit=Coalesce(Sum("debit"), ZERO))["debit"]

    ids = {row["debit_account_id"] for row in cells} | {row["credit_account_id"] for row in cells}
    named = names_for(company_id, ids)

    def code(account_id: uuid.UUID) -> str:
        return named.get(account_id, (str(account_id), ""))[0]

    debit_totals: dict[uuid.UUID, Decimal] = {}
    credit_totals: dict[uuid.UUID, Decimal] = {}
    total = Decimal(0)
    for row in cells:
        debit_totals[row["debit_account_id"]] = (
            debit_totals.get(row["debit_account_id"], Decimal(0)) + row["amount"]
        )
        credit_totals[row["credit_account_id"]] = (
            credit_totals.get(row["credit_account_id"], Decimal(0)) + row["amount"]
        )
        total += row["amount"]

    def totals(items: dict[uuid.UUID, Decimal]) -> tuple[AccountTotal, ...]:
        return tuple(
            sorted(
                (
                    AccountTotal(account_id=key, account_code=code(key), amount=amount)
                    for key, amount in items.items()
                ),
                key=lambda item: item.account_code,
            )
        )

    return Correspondence(
        start_date=start_date,
        end_date=end_date,
        cells=tuple(
            sorted(
                (
                    Cell(
                        debit_account_id=row["debit_account_id"],
                        debit_code=code(row["debit_account_id"]),
                        credit_account_id=row["credit_account_id"],
                        credit_code=code(row["credit_account_id"]),
                        amount=row["amount"],
                    )
                    for row in cells
                ),
                key=lambda cell: (cell.debit_code, cell.credit_code),
            )
        ),
        debit_totals=totals(debit_totals),
        credit_totals=totals(credit_totals),
        total=total,
        lines_total=lines_total,
        unassigned=lines_total - total,
    )
