"""The general ledger (*Cartea Mare*) -- F1.8.

One account, month by month: the balance it opened with, what was debited to it
and against which accounts, what was credited and against which, and the balance
it closed with. That is the form the Moldovan *Cartea Mare* has always had -- the
turnover of an account written *în corespondență cu conturile* -- and it is the
reason the correspondence comes from ``journal_formula`` (ADR-048): a one-sided
line knows its own account, a formula knows both.

The month is the operational period (ADR-039 §5), so the buckets are the
company's ``period`` rows, reached through the entry -- not calendar months cut
from the dates. A fiscal year that runs April to March still closes its months
where the company's calendar says they close.

**Whole months, on both sides.** The window selects the periods it overlaps, and
every figure of a month -- the turnover from the lines, the correspondence from
the formulas -- is taken over the *whole* period, never over the part of it the
window happens to cover. The alternative, cutting lines by their own dates and
formulas by the entry's, lets a window edge fall inside one manual note whose
lines carry different days (``manual.ManualLine``), and then the month's total
and its explanation disagree by an amount nothing names. A Cartea Mare is a
monthly register; a window that starts mid-month reads the month it starts in.

**Totals are the server's** (C19), including the "unassigned" remainder: a
manual note writes lines and no formulas (ADR-048 §4), so its turnover appears
in the month's total and in no correspondent -- and the difference is reported
as such rather than silently spread. A reader who sees `unassigned` knows a
lines-only entry is in the month; one who did not would see a total that its
parts do not add up to.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce

from evidenta.accounting.coa.services.accounts import names_for
from evidenta.accounting.ledger.errors import LedgerAccountNotFoundError
from evidenta.accounting.ledger.models import JournalFormula, JournalLine

ZERO = Value(Decimal("0"), output_field=DecimalField(max_digits=20, decimal_places=4))


@dataclass(frozen=True, slots=True)
class Turnover:
    """Turnover against one correspondent account, one side, one month."""

    account_id: uuid.UUID
    account_code: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class LedgerMonth:
    period_id: uuid.UUID
    period_no: int
    start_date: date
    end_date: date
    #: Debit-positive, at the start of the month.
    opening: Decimal
    debit: Decimal
    credit: Decimal
    #: Debit-positive, at the end of the month.
    closing: Decimal
    #: Debited to this account, against each credited account.
    debit_by: tuple[Turnover, ...]
    #: Credited to this account, against each debited account.
    credit_by: tuple[Turnover, ...]
    #: Turnover that no formula explains -- lines-only entries (ADR-048 §4).
    debit_unassigned: Decimal
    credit_unassigned: Decimal


@dataclass(frozen=True, slots=True)
class GeneralLedger:
    account_id: uuid.UUID
    account_code: str
    name_ro: str
    start_date: date
    end_date: date
    opening: Decimal
    months: tuple[LedgerMonth, ...]
    total_debit: Decimal
    total_credit: Decimal
    closing: Decimal


def general_ledger(
    company_id: uuid.UUID, account_id: uuid.UUID, start_date: date, end_date: date
) -> GeneralLedger:
    """The account's months overlapping ``[start_date, end_date]``, both ends inclusive.

    A month appears when the account moved in it. Months with no movement are
    absent rather than shown as zero rows: the reader asks for the ledger of an
    account, not for the calendar. The answer's own ``start_date``/``end_date``
    are the first month's first day and the last month's last day.
    """
    naming = names_for(company_id, [account_id]).get(account_id)
    if naming is None:
        raise LedgerAccountNotFoundError(
            f"account {account_id} is not visible in this context for company {company_id}"
        )
    code, name = naming

    own = JournalLine.objects.filter(company_id=company_id, account_id=account_id)

    # The periods the window overlaps, through the entry (the FK is named lazily
    # on the model, so nothing here imports `periods`). Whole periods, both
    # sides -- see the module docstring.
    overlapping = {
        "journal_entry__period__start_date__lte": end_date,
        "journal_entry__period__end_date__gte": start_date,
    }
    months = list(
        own.filter(**overlapping)
        .values(
            "journal_entry__period_id",
            "journal_entry__period__period_no",
            "journal_entry__period__start_date",
            "journal_entry__period__end_date",
        )
        .annotate(debit=Coalesce(Sum("debit"), ZERO), credit=Coalesce(Sum("credit"), ZERO))
        .order_by("journal_entry__period__start_date")
    )
    first_day = months[0]["journal_entry__period__start_date"] if months else start_date
    last_day = months[-1]["journal_entry__period__end_date"] if months else end_date

    before = own.filter(accounting_date__lt=first_day).aggregate(
        debit=Coalesce(Sum("debit"), ZERO), credit=Coalesce(Sum("credit"), ZERO)
    )
    opening = before["debit"] - before["credit"]

    window = JournalFormula.objects.filter(company_id=company_id, **overlapping)
    debited = (
        window.filter(debit_account_id=account_id)
        .values("journal_entry__period_id", "credit_account_id")
        .annotate(amount=Coalesce(Sum("amount"), ZERO))
    )
    credited = (
        window.filter(credit_account_id=account_id)
        .values("journal_entry__period_id", "debit_account_id")
        .annotate(amount=Coalesce(Sum("amount"), ZERO))
    )

    debit_by: dict[uuid.UUID, list[tuple[uuid.UUID, Decimal]]] = {}
    credit_by: dict[uuid.UUID, list[tuple[uuid.UUID, Decimal]]] = {}
    counterparts: set[uuid.UUID] = set()
    for debit_row in debited:
        debit_by.setdefault(debit_row["journal_entry__period_id"], []).append(
            (debit_row["credit_account_id"], debit_row["amount"])
        )
        counterparts.add(debit_row["credit_account_id"])
    for credit_row in credited:
        credit_by.setdefault(credit_row["journal_entry__period_id"], []).append(
            (credit_row["debit_account_id"], credit_row["amount"])
        )
        counterparts.add(credit_row["debit_account_id"])
    named = names_for(company_id, counterparts)

    def turnovers(items: list[tuple[uuid.UUID, Decimal]]) -> tuple[Turnover, ...]:
        return tuple(
            sorted(
                (
                    Turnover(
                        account_id=counterpart,
                        account_code=named.get(counterpart, (str(counterpart), ""))[0],
                        amount=amount,
                    )
                    for counterpart, amount in items
                ),
                key=lambda turnover: turnover.account_code,
            )
        )

    out: list[LedgerMonth] = []
    balance = opening
    total_debit = Decimal(0)
    total_credit = Decimal(0)
    for month in months:
        period_id = month["journal_entry__period_id"]
        debits = turnovers(debit_by.get(period_id, []))
        credits = turnovers(credit_by.get(period_id, []))
        explained_debit = sum((turnover.amount for turnover in debits), Decimal(0))
        explained_credit = sum((turnover.amount for turnover in credits), Decimal(0))
        month_opening = balance
        balance = balance + month["debit"] - month["credit"]
        total_debit += month["debit"]
        total_credit += month["credit"]
        out.append(
            LedgerMonth(
                period_id=period_id,
                period_no=month["journal_entry__period__period_no"],
                start_date=month["journal_entry__period__start_date"],
                end_date=month["journal_entry__period__end_date"],
                opening=month_opening,
                debit=month["debit"],
                credit=month["credit"],
                closing=balance,
                debit_by=debits,
                credit_by=credits,
                debit_unassigned=month["debit"] - explained_debit,
                credit_unassigned=month["credit"] - explained_credit,
            )
        )

    return GeneralLedger(
        account_id=account_id,
        account_code=code,
        name_ro=name,
        start_date=first_day,
        end_date=last_day,
        opening=opening,
        months=tuple(out),
        total_debit=total_debit,
        total_credit=total_credit,
        closing=balance,
    )
