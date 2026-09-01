"""The company's control panel -- what the ledger can answer about a company today.

**One service, because the panel is one question**: how does this company stand
in the month it is in. Asked as six separate endpoints it would be six windows a
screen has to agree on, and the first time two of them disagreed -- a turnover
read for June beside a balance read for the year -- nothing on the panel would
say which was wrong.

**Every figure here is a total, and every total is the database's** (C19). The
screen formats strings; it never adds one to another. That is not a style rule on
a dashboard: a KPI is read at a glance and checked by nobody, which makes it the
worst possible place for a sum computed over whatever rows the browser happened
to hold.

**Windows are whole months, and that is a decision.** A turnover "as of the 18th"
is not comparable with the previous month's, and the panel puts the two side by
side -- so the month is `[1st, last]`, the previous month is the whole previous
month, and the year to date ends with the month rather than with the day the
question was asked. The caller's date decides *which* month, never how much of
it. The dates come out with every figure so a reader can see the window rather
than assume it.

**What this service refuses to answer**, and why it is refused here rather than
drawn empty on the screen:

* *When a declaration is due.* The reporting calendar is a fiscal parameter with
  `valid_from` / `valid_to` and a source (R15, ADR-039 section 7.1);
  `fiscal_parameter` is empty (`OD-22`). A deadline written from memory into a
  panel an accountant plans their week from is exactly the defect R15 exists to
  prevent -- see `periods/services/vat.py`, which refuses the same thing.
* *How much VAT is payable.* That is a declaration, and nothing computes one yet.
  Two account balances subtracted from each other would look like the answer and
  carry none of its rules.
* *Which receivables are overdue, and by how long.* A document carries
  `document_date`, not a due date: nothing in the system knows a payment term, so
  "scadent" cannot be said at all -- neither as a figure nor as an ageing band.

The screen states each of these in place of the figure, naming what is missing.
That is the whole difference between a panel with a gap in it and a panel that
guesses.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce, TruncMonth

from evidenta.accounting.coa.services.accounts import names_for, postable_accounts
from evidenta.accounting.ledger.models import EntryStatus, JournalEntry, JournalLine
from evidenta.accounting.ledger.services.correspondence import correspondence
from evidenta.accounting.slots.services.binding import (
    RoleAccountMissingError,
    RoleNotBoundError,
    resolve_role,
)
from evidenta.masterdata.partners.services.directory import legal_names_for
from evidenta.platform.documents.registry import types_owned_by
from evidenta.platform.documents.services.lifecycle import unposted_work

ZERO = Value(Decimal("0"), output_field=DecimalField(max_digits=20, decimal_places=4))

#: Months in the series, the current one included. Six because that is what the
#: panel draws; a longer history is the general ledger's, which has the columns
#: for it.
SERIES_MONTHS = 6

#: How many entries the panel lists. Five, and the register is one click away:
#: a panel that listed fifty would be a worse register, not a better panel.
LATEST_ENTRIES = 5

#: The role the cash tile reads. A role, never an account code: which subaccount
#: a company keeps its cash on is the company's chart (R28), and `2411` written
#: here would be right for most companies and quietly wrong for the rest.
CASH_ROLE = "CASA_MDL"

#: The document families whose unfinished work the panel counts, by owning
#: module. The types themselves are the registry's answer, never a list spelled
#: here -- that vocabulary belongs to the modules that own it.
OWNERS = ("purchases", "sales", "treasury")


@dataclass(frozen=True, slots=True)
class Turnover:
    """What moved in a window, both sides of it."""

    start_date: date
    end_date: date
    debit: Decimal
    credit: Decimal

    @property
    def balanced(self) -> bool:
        """Σ debit = Σ credit over the window.

        It holds per entry already (R11, in the database), so a false here means
        a line reached the ledger outside the engine -- which is what makes it
        worth showing rather than assuming.
        """
        return self.debit == self.credit


@dataclass(frozen=True, slots=True)
class PanelEntry:
    """One line of the panel's register extract.

    ``partner_name`` is the counterparty of the entry's first line that names
    one, and it is empty rather than invented when no line does: a manual note
    between two accounts has no counterparty, and a panel that filled the column
    with the description would make one look like the other.
    """

    id: uuid.UUID
    entry_number: str
    accounting_date: date
    description: str
    partner_name: str
    amount: Decimal
    entry_type: str
    reverses_entry_id: uuid.UUID | None
    reversed_by_entry_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class DocumentWork:
    """Documents of one family that have not reached the ledger yet.

    Two states, and they are different work: a draft is unfinished, a validated
    document is finished and unposted. Summed into one number the panel would say
    "seven documents" and hide which seven need what.
    """

    owner: str
    draft: int
    confirmed: int


@dataclass(frozen=True, slots=True)
class Cash:
    """The cash account the company's chart binds to `CASA_MDL`, and its balance."""

    account_id: uuid.UUID
    account_code: str
    name_ro: str
    balance: Decimal


@dataclass(frozen=True, slots=True)
class Overview:
    on: date
    month: Turnover
    previous_month: Turnover
    year_to_date: Turnover
    series: tuple[Turnover, ...]
    latest_entries: tuple[PanelEntry, ...]
    draft_entries: int
    documents: tuple[DocumentWork, ...]
    #: ``None`` when the chart binds no cash account. Not a zero: an unbound role
    #: means nobody has said which account this is, and zero would be an answer.
    cash: Cash | None
    #: Turnover in the month that no formula explains -- lines entered without a
    #: correspondence, which is what a manual note produces.
    unexplained: Decimal
    #: Accounts with movement in the month that a posting dated in it could not
    #: use: blocked, or closed before it.
    unpostable_with_turnover: int


def month_start(day: date) -> date:
    return day.replace(day=1)


def month_end(day: date) -> date:
    """The last day of ``day``'s month, without a calendar table.

    The 28th of next month is inside it for every month of every year, so
    stepping back to the first and off by a day lands on the last -- February in
    a leap year included.
    """
    following = day.replace(day=28) + timedelta(days=4)
    return following.replace(day=1) - timedelta(days=1)


def months_back(first_of_month: date, count: int) -> date:
    """``count`` months before a first-of-month, as a first-of-month."""
    year, month = divmod(first_of_month.year * 12 + first_of_month.month - 1 - count, 12)
    return date(year, month + 1, 1)


def company_overview(company_id: uuid.UUID, on: date) -> Overview:
    """The panel for the month ``on`` falls in."""
    start = month_start(on)
    end = month_end(on)
    series_start = months_back(start, SERIES_MONTHS - 1)

    by_month = _turnover_by_month(company_id, series_start, end)
    series = tuple(
        _window(months_back(start, SERIES_MONTHS - 1 - step), by_month)
        for step in range(SERIES_MONTHS)
    )

    return Overview(
        on=on,
        month=series[-1],
        previous_month=series[-2],
        # From the first of January rather than from twelve months back: the
        # fiscal year is the calendar year (Codul fiscal art. 121), and this is
        # the window an accountant checks a balance over.
        year_to_date=_turnover(company_id, date(on.year, 1, 1), end),
        series=series,
        latest_entries=_latest_entries(company_id),
        draft_entries=JournalEntry.objects.filter(
            company_id=company_id, status=EntryStatus.DRAFT
        ).count(),
        documents=_documents(company_id),
        cash=_cash(company_id, end),
        unexplained=correspondence(company_id, start, end).unassigned,
        unpostable_with_turnover=_unpostable_with_turnover(company_id, start, end),
    )


def _turnover_by_month(
    company_id: uuid.UUID, start: date, end: date
) -> dict[date, tuple[Decimal, Decimal]]:
    """Every month of the span in one grouped query, keyed by its first day.

    One query rather than one per month: six round trips to answer a bar chart is
    six times the work for an answer the database groups in a single scan of the
    same index.
    """
    rows = (
        JournalLine.objects.filter(
            company_id=company_id, accounting_date__gte=start, accounting_date__lte=end
        )
        .annotate(month=TruncMonth("accounting_date"))
        .values("month")
        .annotate(debit=Coalesce(Sum("debit"), ZERO), credit=Coalesce(Sum("credit"), ZERO))
    )
    return {row["month"]: (row["debit"], row["credit"]) for row in rows}


def _window(first: date, by_month: dict[date, tuple[Decimal, Decimal]]) -> Turnover:
    debit, credit = by_month.get(first, (Decimal("0"), Decimal("0")))
    return Turnover(start_date=first, end_date=month_end(first), debit=debit, credit=credit)


def _turnover(company_id: uuid.UUID, start: date, end: date) -> Turnover:
    totals = JournalLine.objects.filter(
        company_id=company_id, accounting_date__gte=start, accounting_date__lte=end
    ).aggregate(debit=Coalesce(Sum("debit"), ZERO), credit=Coalesce(Sum("credit"), ZERO))
    return Turnover(start_date=start, end_date=end, debit=totals["debit"], credit=totals["credit"])


def _latest_entries(company_id: uuid.UUID) -> tuple[PanelEntry, ...]:
    """The last few postings, newest first -- and what each one is.

    Posted only. Drafts are counted separately, in the work the panel says is
    open: an extract of the register that mixed the two would show an amount that
    has not moved anything beside amounts that have.

    Both halves of R14 travel with the row, as they do on the register: what this
    entry cancels, and whether it has itself been cancelled. A panel that showed
    a reversed entry as a plain posting would be showing an amount that is no
    longer there.
    """
    entries = list(
        JournalEntry.objects.filter(company_id=company_id, status=EntryStatus.POSTED).order_by(
            "-accounting_date", "-entry_number"
        )[:LATEST_ENTRIES]
    )
    if not entries:
        return ()

    ids = [entry.id for entry in entries]
    reversals = dict(
        JournalEntry.objects.filter(company_id=company_id, reverses_entry_id__in=ids).values_list(
            "reverses_entry_id", "id"
        )
    )

    partner_of: dict[uuid.UUID, uuid.UUID] = {}
    for line in (
        JournalLine.objects.filter(journal_entry_id__in=ids, partner_id__isnull=False)
        .order_by("line_number")
        .values("journal_entry_id", "partner_id")
    ):
        partner_id = line["partner_id"]
        # The filter above already excludes them; the column is nullable, so the
        # narrowing is written rather than assumed.
        if partner_id is not None:
            partner_of.setdefault(line["journal_entry_id"], partner_id)
    # The legal name, never the internal one (C39), and asked of `masterdata`
    # through its service rather than read from its tables (D6).
    names = legal_names_for(list(dict.fromkeys(partner_of.values())))

    rows = []
    for entry in entries:
        partner_id = partner_of.get(entry.id)
        rows.append(
            PanelEntry(
                id=entry.id,
                entry_number=entry.entry_number,
                accounting_date=entry.accounting_date,
                description=entry.description,
                partner_name=names.get(partner_id, "") if partner_id is not None else "",
                # One side is enough because both are equal (R11), and the panel
                # has room for one column.
                amount=entry.total_debit,
                entry_type=entry.entry_type,
                reverses_entry_id=entry.reverses_entry_id,
                reversed_by_entry_id=reversals.get(entry.id),
            )
        )
    return tuple(rows)


def _documents(company_id: uuid.UUID) -> tuple[DocumentWork, ...]:
    """Unfinished document work, by owning module.

    Which types a family holds is the registry's answer (`types_owned_by`), and
    the counts are `platform.documents`' own: this module may not read that
    table, and asking through the service is what `D6` asks for rather than a
    concession to it.
    """
    types = {owner: types_owned_by(owner) for owner in OWNERS}
    counted = {
        row.document_type: row
        for row in unposted_work(company_id, [code for codes in types.values() for code in codes])
    }

    work = []
    for owner in OWNERS:
        rows = [counted[code] for code in types[owner] if code in counted]
        draft = sum(row.draft for row in rows)
        confirmed = sum(row.confirmed for row in rows)
        if draft or confirmed:
            work.append(DocumentWork(owner=owner, draft=draft, confirmed=confirmed))
    return tuple(work)


def _cash(company_id: uuid.UUID, end: date) -> Cash | None:
    """What is in the till, if the chart says which account that is.

    ``None`` rather than zero when the role is unbound or names a subaccount this
    chart does not contain. Both are the same answer to the reader -- nobody has
    said which account this is -- and both are legitimate: a company that keeps no
    cash binds no cash account, and a panel that answered `0,00 MDL` would be
    stating a balance for an account that does not exist.
    """
    try:
        account_id = resolve_role(company_id, CASH_ROLE, end)
    except (RoleNotBoundError, RoleAccountMissingError):
        return None

    naming = names_for(company_id, [account_id]).get(account_id)
    if naming is None:
        return None

    totals = JournalLine.objects.filter(
        company_id=company_id, account_id=account_id, accounting_date__lte=end
    ).aggregate(debit=Coalesce(Sum("debit"), ZERO), credit=Coalesce(Sum("credit"), ZERO))

    code, name = naming
    return Cash(
        account_id=account_id,
        account_code=code,
        name_ro=name,
        # Debit-positive, like the trial balance: cash on the credit side is a
        # fact worth seeing rather than one to fold into the expected column.
        balance=totals["debit"] - totals["credit"],
    )


def _unpostable_with_turnover(company_id: uuid.UUID, start: date, end: date) -> int:
    """Accounts that moved in the month and could not be posted to within it.

    Blocked, or closed before the month ended. Not an error on its own -- an
    account blocked *after* the movement is exactly this -- which is why the panel
    counts them and names none: the answer is a reading of the chart, and the
    chart screen is where that reading happens.
    """
    moved = {
        row["account_id"]
        for row in JournalLine.objects.filter(
            company_id=company_id, accounting_date__gte=start, accounting_date__lte=end
        )
        .values("account_id")
        .distinct()
    }
    if not moved:
        return 0
    postable = {account.id for account in postable_accounts(company_id, end)}
    return len(moved - postable)
