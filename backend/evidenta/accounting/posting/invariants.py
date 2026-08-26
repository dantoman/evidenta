"""The six invariants, checked before a line can reach the ledger -- F1.4.3.

ADR-036 section 5.2 lists them, and then says the part that makes the list worth
writing down at all:

    "Verificati de motor, nu de handler. Un handler care ii incalca esueaza la
    postare, nu produce date gresite."

Numbered as the ADR numbers them:

    1  sum of debits = sum of credits, in the functional currency         R11
    2  every line belongs to the same tenant                              R1
    3  every line falls in one period, and that period is open            R12
    4  every line names an account that exists and is valid on the date
    5  no line with a zero amount
    6  the posting names exactly one source                               R13

**What is checked is a proposal, not a row.** Nothing here writes, so a refusal
leaves nothing in the ledger to undo -- the only order that works against an
append-only table, where a wrong line is corrected by a reversal that is itself a
permanent entry.

**What the database already refuses, and what it cannot.** ``0036_ledger`` covers
an unbalanced entry (at commit), a line with two sides, a negative or zero one,
and an entry whose *own* date falls in a period that is not open. Three things it
cannot cover, and none of the three by oversight:

* **the account** -- ``journal_line.account_id`` carries no foreign key, by design
  (R21), so nothing in the schema knows whether the id names an account of this
  company, one closed before that date, or nothing at all
* **the company** -- ``journal_line.company_id`` is a plain column too, and the
  RLS policy admits *any* company the context may reach, which for an accountant
  with two clients is both of them. One entry written across two companies passes
  every constraint
* **the line dates** -- ``journal_entry_needs_open_period`` compares the entry's
  ``accounting_date`` to its period and never looks at the lines, which carry the
  partition column of the largest table in the system

The remaining two are narrower than they look. A foreign ``tenant_id`` is refused
by the RLS policy, but with "new row violates row-level security policy" -- the
same sentence a missing context produces. ``accounting_event.source_document_id``
is ``NOT NULL`` and ``source_module`` has a CHECK, but ``source_document_type`` is
free text, so an empty one is a valid row and a dead end for anybody drilling
down.

**Where it can see it, it answers in the wrong shape.** The balance trigger is a
deferred constraint trigger: it fires at COMMIT, with a ``check_violation`` that
reaches Python as ``IntegrityError`` carrying no stable code, long after the
handler that caused it returned. C10 wants a code a caller can branch on and
record in ``accounting_event.posting_error``. The database stays the barrier that
cannot be bypassed -- the 1C importer and any data migration meet it -- and this
is the barrier that can say *which* rule was broken, to the party that broke it.

**Nothing here derives an amount.** ``debit`` and ``credit`` are functional-currency
amounts the handler produced; the engine sums them and compares. Deriving them
from ``amount_currency * exchange_rate`` would need a rounding rule, and which
rule that is (`DNB-08`) is open -- ``accounting.currency.money`` refuses the same
operation for the same reason, and doing it here would answer the decision by
accident.

**The exception clause of invariant 5 is deliberately not implemented.** The ADR
writes it as "nicio linie cu suma zero, *cu exceptia cazurilor declarate de
handler*". No handler can be given that exception today, because the ledger
schema refuses a zero line regardless of what anybody declares:
``journal_line_one_side_only`` (Spec B section 1.3, already in the database)
requires exactly one side strictly positive. Accepting a declared zero line here
would produce an engine that approves what the next statement refuses, with an
``IntegrityError`` instead of a code. Honouring the clause means changing that
CHECK, which is an ADR, not a task -- reported rather than decided.

**No account code appears in this module, and none ever should.** The engine
resolves accounts by id, through the chart service; the content of the general
chart is `OD-22`/`OD-23`, open, and a code written here would be that content
arriving through the back door (R15).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from evidenta.accounting.coa.services.accounts import postable_accounts
from evidenta.accounting.periods.services.resolution import assert_postable
from evidenta.platform.api.errors import ApiError

ZERO = Decimal(0)


class PostingRefusedError(ApiError):
    """Base of every refusal the engine issues before anything is written.

    One family, so the caller that records the failure on the accounting event
    can catch it without enumerating the members, while ``posting_error`` keeps
    the specific code (C10) rather than a message. A caller that needs to tell
    the cases apart branches on ``code``; one that only needs "this did not post"
    catches the base.
    """

    code = "posting.refused"
    status = 409


class NoLinesError(PostingRefusedError):
    """A posting with no lines. Balanced at zero is not balanced, it is empty.

    Filed under invariant 1 because that is where it hides: zero equals zero, so
    the balance check passes an empty posting and the deferred trigger refuses it
    at COMMIT with "has no amount", after the handler is long gone.
    """

    code = "posting.no_lines"


class OutOfBalanceError(PostingRefusedError):
    """Invariant 1 -- R11, Spec B section 1.6."""

    code = "posting.out_of_balance"


class MixedTenantError(PostingRefusedError):
    """Invariant 2 -- R1.

    The RLS policy on ``journal_line`` refuses a foreign ``tenant_id`` at INSERT,
    which is the barrier that holds when this code is bypassed. It says so with
    "new row violates row-level security policy" -- true, unbranchable, and
    indistinguishable from a missing context.
    """

    code = "posting.mixed_tenant"


class MixedCompanyError(PostingRefusedError):
    """Invariant 2, one level down -- and the precondition for 3 and 4.

    ADR-036 writes the invariant about the tenant. The company half is not an
    addition: ``journal_entry`` carries exactly one ``company_id`` and the lines
    denormalise it, so lines from two companies under one entry is the same
    defect. It also has to be settled before the two checks that follow can run
    at all -- a period and a chart of accounts are per company, so a posting
    spanning two companies has two calendars and two charts and no answer.
    """

    code = "posting.mixed_company"


class MixedPeriodError(PostingRefusedError):
    """Invariant 3, first half -- lines outside the posting's own period.

    The period being *open* is the second half, and it is not raised here: that
    is ``periods.assert_postable``, which already owns the three-state machine
    and its three codes. Re-deciding "open" at the point of posting would be a
    second copy of R12, and the copy is always the one that drifts.
    """

    code = "posting.mixed_period"


class AccountNotPostableError(PostingRefusedError):
    """Invariant 4 -- the account is absent, closed on that date, or blocked.

    **One code for the three, and the reason is D6 rather than a preference.**
    Telling them apart needs the account row itself, and reading
    ``coa.models.CompanyAccount`` from here is exactly the import the dependency
    rule forbids. What the chart offers as a public service is
    ``postable_accounts(company, on_date)`` -- the set a posting on that date may
    use -- so the engine can say the id is not in it, and not why. The message
    names the three possibilities so the reader knows where to look.
    """

    code = "posting.account_not_postable"


class ZeroAmountLineError(PostingRefusedError):
    """Invariant 5 -- a line carrying nothing.

    ``journal_line_one_side_only`` refuses it as well, at INSERT, and that is the
    barrier that holds against the importer. What is added here is a code, the
    line number, and the timing: the refusal lands before any row of the entry
    exists, so the event can be marked ``failed`` with a reason
    (``accounting_event_failed_has_reason``) instead of a half-written entry
    being rolled back.

    Why it is worth refusing at all, rather than dropped: a zero line survives
    every aggregate. The entry would still balance and the trial balance would
    still be right, so nothing downstream would ever point at it. See the module
    docstring for why the ADR's exception clause has no implementation.
    """

    code = "posting.zero_amount_line"


class MalformedLineAmountError(PostingRefusedError):
    """The rest of what a well-formed amount excludes: two sides, or a negative.

    The same question invariant 5 asks -- is this line an amount at all -- and
    the same pair of database CHECKs refuses both
    (``journal_line_one_side_only``, ``journal_line_amounts_not_negative``). A
    separate code because the diagnosis differs: a zero line is usually a missing
    value, while both sides at once is a handler that modelled one movement as
    one line instead of two.
    """

    code = "posting.malformed_line_amount"


class SourceNotSingularError(PostingRefusedError):
    """Invariant 6 -- R13, the chain that has to be navigable in both directions.

    ``Journal Line -> Journal Entry -> Accounting Event -> Source Document ->
    Sursa``. The weak link is the last hop: ``accounting_event.source_document_id``
    carries no foreign key, because a key there would make ``accounting`` know the
    schema of the module that produced the document (D2). Nothing else checks that
    the link is populated, so a posting with no origin would be a permanent ledger
    entry that answers "what is this?" with nothing.
    """

    code = "posting.source_not_singular"


@dataclass(frozen=True, slots=True)
class Origin:
    """What the posting is *of* -- the fourth link of the R13 chain.

    A manual journal note is not a second shape here: it is a source like any
    other, with ``module = "manual"`` and the note as its document (Spec B section
    1.5). Two shapes would mean lineage implemented twice, and the second
    implementation is always the one that breaks.
    """

    module: str
    document_type: str
    document_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class ProposedLine:
    """One line as the handler proposes it, before anything is written.

    **Deliberately narrow: these are the columns the six invariants are about,
    not the full journal line.** A ``journal_line`` also carries the transaction
    currency, the rate, the three dates and the fifteen analytical columns. What
    a handler must return in total is the handler contract, F1.4.4, which is
    blocked on the accounting questions `C1`-`C5` of ADR-036 section 11 -- so
    fixing that shape here would answer a blocked decision from the module least
    able to argue about it.

    ``debit`` and ``credit`` are **functional-currency** amounts, which is what
    makes invariant 1 the one the ADR states: a foreign-currency posting balances
    in MDL and need not balance in EUR.
    """

    tenant_id: uuid.UUID
    company_id: uuid.UUID
    accounting_date: date
    account_id: uuid.UUID
    debit: Decimal
    credit: Decimal


@dataclass(frozen=True, slots=True)
class ProposedPosting:
    """A handler's output plus the context the engine judges it in.

    ``accounting_event_id`` and ``origin`` are optional **so that invariant 6 has
    something to refuse**. Neither is optional in the ledger: ``journal_entry``
    has ``accounting_event_id NOT NULL``, and the event has a source. The
    absence being representable here is what lets the engine answer with a code
    instead of letting a ``NotNullViolation`` surface three layers away.
    """

    tenant_id: uuid.UUID
    company_id: uuid.UUID
    #: The date of the posting itself -- the one that decides the period, the
    #: fiscal parameters and the handler version (R17, R18). A line may carry its
    #: own date within the same period; this is the entry's.
    accounting_date: date
    accounting_event_id: uuid.UUID | None
    origin: Origin | None
    lines: tuple[ProposedLine, ...]


def verify(posting: ProposedPosting) -> uuid.UUID:
    """Refuse the posting, or return the id of the period it lands in.

    The return value is not a convenience: resolving the period is invariant 3's
    own work, and handing it back means the writer does not resolve it a second
    time and get a different answer -- between the two reads a month can be
    closed, and the entry would then be written into a period the engine checked
    as open.

    **Order is part of the contract.** Every check that needs no database runs
    first, so a malformed proposal is refused without touching one -- a bulk
    importer pays that cost per bad row. Scope comes before the two checks that
    read: a period and a chart belong to one company, and a posting that spans
    two has no single answer to ask them for.

    **Not every refusal is a ``PostingRefusedError``.** The "period is open" half
    of invariant 3 surfaces as the period module's own error, with its own code --
    ``periods.period_not_open``, ``periods.period_locked``,
    ``periods.period_not_found``. Flattening the three into one posting code would
    tell a caller "it did not post" while hiding whether reopening is even
    possible, which is the one thing they need to know. Every refusal is an
    ``ApiError`` carrying a code (C10), so a caller that only records the failure
    catches that; one that has to act on it branches on ``code``.
    """
    if not posting.lines:
        raise NoLinesError(
            f"posting for company {posting.company_id} on {posting.accounting_date} "
            f"has no lines; balanced at zero is not balanced, it is empty"
        )

    _check_scope(posting)
    _check_line_amounts(posting)
    _check_balance(posting)
    _check_origin(posting)
    period_id = _check_period(posting)
    _check_accounts(posting)
    return period_id


def _check_scope(posting: ProposedPosting) -> None:
    """Invariant 2 -- one tenant, one company, and the header's own."""
    tenants = {line.tenant_id for line in posting.lines} | {posting.tenant_id}
    if len(tenants) > 1:
        named = ", ".join(sorted(str(t) for t in tenants))
        raise MixedTenantError(
            f"a posting spans {len(tenants)} tenants ({named}); one entry belongs to "
            f"one tenant, and cross-tenant reads live only in read models (R1, R7)"
        )

    companies = {line.company_id for line in posting.lines} | {posting.company_id}
    if len(companies) > 1:
        named = ", ".join(sorted(str(c) for c in companies))
        raise MixedCompanyError(
            f"a posting spans {len(companies)} companies ({named}); a journal entry "
            f"carries exactly one, and the period and the chart of accounts it is "
            f"checked against are that company's"
        )


def _check_line_amounts(posting: ProposedPosting) -> None:
    """Invariant 5 -- every line is exactly one strictly positive side."""
    for number, line in enumerate(posting.lines, start=1):
        if line.debit < ZERO or line.credit < ZERO:
            raise MalformedLineAmountError(
                f"line {number} carries a negative amount (debit {line.debit}, "
                f"credit {line.credit}); the opposite side of a movement is the "
                f"other column, never a minus sign -- a negative line would make "
                f"the month's turnover go down by the entry that happened"
            )
        if line.debit > ZERO and line.credit > ZERO:
            raise MalformedLineAmountError(
                f"line {number} carries both sides (debit {line.debit}, credit "
                f"{line.credit}); that is one movement modelled as one line instead "
                f"of two, and it is unwriteable anyway"
            )
        if line.debit == ZERO and line.credit == ZERO:
            raise ZeroAmountLineError(
                f"line {number} on account {line.account_id} carries no amount; it "
                f"survives every aggregate, so the entry still balances and the line "
                f"sits in the ledger permanently meaning nothing"
            )


def _check_balance(posting: ProposedPosting) -> None:
    """Invariant 1 -- R11, in the functional currency."""
    debit = sum((line.debit for line in posting.lines), ZERO)
    credit = sum((line.credit for line in posting.lines), ZERO)
    if debit != credit:
        raise OutOfBalanceError(
            f"debit {debit} does not equal credit {credit} (difference "
            f"{debit - credit}) across {len(posting.lines)} line(s)"
        )


def _check_origin(posting: ProposedPosting) -> None:
    """Invariant 6 -- exactly one accounting event, naming exactly one source."""
    if posting.accounting_event_id is None:
        raise SourceNotSingularError(
            "a posting names no accounting event; every entry has one, a manual "
            "note included (Spec B section 1.5), because two paths into the ledger "
            "means lineage and idempotency implemented twice"
        )

    origin = posting.origin
    if origin is None:
        raise SourceNotSingularError(
            f"event {posting.accounting_event_id} names no source document; the last "
            f"hop of the R13 chain carries no foreign key (D2), so nothing else will "
            f"notice it is missing"
        )

    missing = [
        field
        for field, value in (("module", origin.module), ("document_type", origin.document_type))
        if not value.strip()
    ]
    if missing:
        raise SourceNotSingularError(
            f"the source of event {posting.accounting_event_id} is incomplete: "
            f"{', '.join(missing)} is blank. A partial origin is a ledger row that "
            f"cannot be navigated back to what caused it"
        )


def _check_period(posting: ProposedPosting) -> uuid.UUID:
    """Invariant 3 -- one period for every line, and that period open (R12).

    ``assert_postable`` answers the second half and owns its codes:
    ``periods.period_not_found`` for a hole in the calendar,
    ``periods.period_not_open`` for a closed month, ``periods.period_locked`` for
    one that will never reopen. They are not re-raised as posting codes -- the
    remedies differ per code, and flattening them into one would tell a caller
    "it did not post" while hiding whether reopening is even possible.

    ``end_date`` is **inclusive** on ``period``, unlike the half-open validity
    windows elsewhere in the system. Comparing against it as if it were exclusive
    would silently reject the last day of every month.
    """
    period = assert_postable(posting.company_id, posting.accounting_date)

    outside = sorted(
        {
            line.accounting_date
            for line in posting.lines
            if not (period.start_date <= line.accounting_date <= period.end_date)
        }
    )
    if outside:
        raise MixedPeriodError(
            f"line date(s) {', '.join(d.isoformat() for d in outside)} fall outside "
            f"period {period.start_date.isoformat()}..{period.end_date.isoformat()}, "
            f"which is the one the posting is dated into "
            f"({posting.accounting_date.isoformat()})"
        )

    return period.id


def _check_accounts(posting: ProposedPosting) -> None:
    """Invariant 4 -- every account exists and may receive a posting that day.

    Judged at the **posting's** date, not each line's. A posting has one date;
    invariant 3 has already tied every line to the period that date falls in, and
    asking the chart a different question per line would make one entry able to
    use two charts.

    There is no fallback account and there is no lenient mode. ADR-036 section
    5.1: "Un rol nelegat e eroare la postare" -- posting quietly to a generic
    account is the worst available failure, because it is discovered months
    later, by someone who cannot tell what should have been there.
    """
    chart = postable_accounts(posting.company_id, posting.accounting_date)
    postable = {account.id for account in chart}
    unknown = sorted({line.account_id for line in posting.lines} - postable)
    if unknown:
        named = ", ".join(str(a) for a in unknown)
        raise AccountNotPostableError(
            f"account(s) {named} cannot receive a posting "
            f"dated {posting.accounting_date.isoformat()}: absent from this company's "
            f"chart, closed on that date, or blocked. There is no fallback account -- "
            f"posting to a generic one is found months later, by someone who cannot "
            f"tell what should have been there"
        )
