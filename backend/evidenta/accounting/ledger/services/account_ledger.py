"""The account ledger (*fișa contului*) -- F1.8, ADR-053 §3.1.

One row per **document** per account, not per journal line. ADR-053 decided the
granularity by looking at what the reader wants: a 521 opened on a forty-one line
invoice shows one row for that invoice, with the amount and the correspondence,
and expands to the formulas on demand. So the aggregation is over
``journal_entry`` -- the entry is the document's footprint in the register -- and
the correspondence comes from ``journal_formula`` (ADR-048), because the formula
*is* the correspondence and a one-sided line cannot say what it corresponds with.

**Every figure a person adds up is added here** (C19). The opening balance, the
turnovers, the running balance after each row and the closing balance are the
server's; the client formats and never sums. The running balance is computed
over the *whole* window even when the rows are paged, because a balance that
restarted at the top of each page would be wrong in the direction nobody checks.

**An entry without formulas is a row without correspondence, not a missing
row.** A manual note writes lines only (ADR-048 §4), so its row carries the
amount and no counterpart codes; the report says so with `has_formulas` rather
than inventing a pairing from the lines. A closing entry is a document like any
other here (ADR-056): its formulas are the chain and they read as such.

**Included by the line's date, dated by the entry's.** The window selects lines
by ``journal_line.accounting_date`` -- the same column the trial balance sums, so
a ledger's turnover ties to the balance's row for the account, which is the check
an accountant makes first. The row then carries the *entry's* ``accounting_date``,
the date the register shows and the drill-down repeats. The two coincide for
every computed posting; a manual note is allowed to date a line inside the
entry's period but not on the entry's day (``manual.ManualLine``), and for such a
note a row can sit in the window by one of its lines while showing the entry's
day -- the balance counts the line, the register names the entry, and this report
says both rather than choosing one.

**Both halves of R14 ride on the row.** A reversal names what it cancels and a
cancelled entry names its reversal, as the register does, so a reader scanning
the ledger can tell a correction from a movement without opening every entry.

**Served by `journal_line_account_idx`** -- `(company_id, account_id,
accounting_date)` -- which is the index ADR-053 §4 names for exactly this read.
`tests/volume/test_account_ledger.py` checks that the plan uses it at scale, and
how long the busiest account's month takes under the application role.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import DecimalField, Min, Q, Sum, Value
from django.db.models.functions import Coalesce

from evidenta.accounting.coa.services.accounts import names_for
from evidenta.accounting.ledger.errors import LedgerAccountNotFoundError
from evidenta.accounting.ledger.models import JournalEntry, JournalFormula, JournalLine

ZERO = Value(Decimal("0"), output_field=DecimalField(max_digits=20, decimal_places=4))

#: Rows per answer. The totals below are computed over the whole window
#: regardless; only the rows are cut, and the answer says so. A month of a busy
#: account in the "Mare" scenario is ~1.500 documents (F0.11), so a page of
#: two thousand covers the read ADR-053 sets the target on without cutting it.
PAGE = 2_000


@dataclass(frozen=True, slots=True)
class Correspondent:
    """One account on the other side of a formula, and how much went through it."""

    account_id: uuid.UUID
    account_code: str
    #: Amount debited to the ledger's account against this correspondent.
    debit: Decimal
    #: Amount credited to the ledger's account against this correspondent.
    credit: Decimal


@dataclass(frozen=True, slots=True)
class LedgerRow:
    """One document's footprint on one account."""

    journal_entry_id: uuid.UUID
    entry_number: str
    #: The entry's -- the date the register shows (ADR-039 §9).
    accounting_date: date
    document_date: date
    entry_type: str
    description: str
    debit: Decimal
    credit: Decimal
    #: Debit-positive, after this row, over the whole window (C19).
    balance: Decimal
    #: From the formulas; empty for a lines-only entry.
    correspondents: tuple[Correspondent, ...]
    has_formulas: bool
    #: R14, both directions: what this entry cancels, and what cancelled it.
    reverses_entry_id: uuid.UUID | None
    reversed_by_entry_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class AccountLedger:
    account_id: uuid.UUID
    account_code: str
    name_ro: str
    start_date: date
    end_date: date
    #: Debit-positive, before ``start_date``.
    opening: Decimal
    rows: tuple[LedgerRow, ...]
    truncated: bool
    total_debit: Decimal
    total_credit: Decimal
    closing: Decimal


def account_ledger(
    company_id: uuid.UUID, account_id: uuid.UUID, start_date: date, end_date: date
) -> AccountLedger:
    """The ledger of one account over ``[start_date, end_date]``, both ends inclusive.

    Refuses with `ledger.account_not_found` for an account this context cannot
    see -- through `coa`'s service, never its models (`D6`) -- rather than
    answering with an empty ledger, which would read as "nothing happened".
    """
    naming = names_for(company_id, [account_id]).get(account_id)
    if naming is None:
        raise LedgerAccountNotFoundError(
            f"account {account_id} is not visible in this context for company {company_id}"
        )
    code, name = naming

    own = JournalLine.objects.filter(company_id=company_id, account_id=account_id)
    before = own.filter(accounting_date__lt=start_date).aggregate(
        debit=Coalesce(Sum("debit"), ZERO), credit=Coalesce(Sum("credit"), ZERO)
    )
    opening = before["debit"] - before["credit"]

    inside = own.filter(accounting_date__gte=start_date, accounting_date__lte=end_date)
    totals = inside.aggregate(
        debit=Coalesce(Sum("debit"), ZERO), credit=Coalesce(Sum("credit"), ZERO)
    )

    # One row per entry. The amounts are the account's lines of that entry inside
    # the window; the date and the number are the entry's, read next.
    per_entry = list(
        inside.values("journal_entry_id").annotate(
            debit=Coalesce(Sum("debit"), ZERO),
            credit=Coalesce(Sum("credit"), ZERO),
            document_date=Min("document_date"),
        )
    )

    entry_ids = [row["journal_entry_id"] for row in per_entry]
    headers = {
        entry.id: entry
        for entry in JournalEntry.objects.filter(id__in=entry_ids).only(
            "id",
            "entry_number",
            "accounting_date",
            "entry_type",
            "description",
            "reverses_entry_id",
        )
    }
    # What cancelled what, for the page (R14). One query, the register's way.
    reversed_by = dict(
        JournalEntry.objects.filter(reverses_entry_id__in=entry_ids).values_list(
            "reverses_entry_id", "id"
        )
    )

    # The register's order: the entry's date, then its number -- the number is
    # text, allocated per year, so it sorts within a day, not across the window.
    per_entry.sort(
        key=lambda row: (
            headers[row["journal_entry_id"]].accounting_date
            if row["journal_entry_id"] in headers
            else start_date,
            headers[row["journal_entry_id"]].entry_number
            if row["journal_entry_id"] in headers
            else "",
        )
    )
    truncated = len(per_entry) > PAGE
    page = per_entry[:PAGE]
    page_ids = [row["journal_entry_id"] for row in page]

    # The correspondence, from the formulas that touch this account on either
    # side (ADR-048). Grouped per entry and per counterpart, because a document
    # with forty-one lines against one customer is one correspondence.
    formulas = (
        JournalFormula.objects.filter(company_id=company_id, journal_entry_id__in=page_ids)
        .filter(Q(debit_account_id=account_id) | Q(credit_account_id=account_id))
        .values("journal_entry_id", "debit_account_id", "credit_account_id")
        .annotate(amount=Coalesce(Sum("amount"), ZERO))
    )
    by_entry: dict[uuid.UUID, dict[uuid.UUID, list[Decimal]]] = {}
    counterpart_ids: set[uuid.UUID] = set()
    for formula in formulas:
        if formula["debit_account_id"] == account_id:
            counterpart, side = formula["credit_account_id"], 0
        else:
            counterpart, side = formula["debit_account_id"], 1
        counterpart_ids.add(counterpart)
        cell = by_entry.setdefault(formula["journal_entry_id"], {}).setdefault(
            counterpart, [Decimal(0), Decimal(0)]
        )
        cell[side] += formula["amount"]

    named = names_for(company_id, counterpart_ids)

    rows: list[LedgerRow] = []
    balance = opening
    for row in page:
        entry = headers.get(row["journal_entry_id"])
        balance = balance + row["debit"] - row["credit"]
        correspondents = tuple(
            Correspondent(
                account_id=counterpart,
                # An id in place of a code means an account this context cannot
                # see -- shown, not skipped, so the row still explains itself.
                account_code=named.get(counterpart, (str(counterpart), ""))[0],
                debit=cell[0],
                credit=cell[1],
            )
            for counterpart, cell in sorted(
                by_entry.get(row["journal_entry_id"], {}).items(),
                key=lambda item: named.get(item[0], (str(item[0]), ""))[0],
            )
        )
        rows.append(
            LedgerRow(
                journal_entry_id=row["journal_entry_id"],
                entry_number=entry.entry_number if entry else "",
                accounting_date=entry.accounting_date if entry else row["document_date"],
                document_date=row["document_date"],
                entry_type=entry.entry_type if entry else "",
                description=entry.description if entry else "",
                debit=row["debit"],
                credit=row["credit"],
                balance=balance,
                correspondents=correspondents,
                has_formulas=bool(correspondents),
                reverses_entry_id=entry.reverses_entry_id if entry else None,
                reversed_by_entry_id=reversed_by.get(row["journal_entry_id"]),
            )
        )

    return AccountLedger(
        account_id=account_id,
        account_code=code,
        name_ro=name,
        start_date=start_date,
        end_date=end_date,
        opening=opening,
        rows=tuple(rows),
        truncated=truncated,
        total_debit=totals["debit"],
        total_credit=totals["credit"],
        closing=opening + totals["debit"] - totals["credit"],
    )
