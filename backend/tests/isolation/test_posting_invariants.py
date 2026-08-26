"""The six invariants, each broken on purpose -- F1.4.3, ADR-036 section 5.2.

The criterion for this task is not "the checks exist". It is that every one of
the six has a test which **violates it deliberately and sees the refusal** --
because a guard nobody has watched refuse is a guard whose shape nobody knows,
and this repository has already found two that passed by never firing.

So each section below is one invariant, and each contains at least one posting
built to be wrong in exactly that way. The happy path is here too, once: without
it, a `verify` that refused everything would pass the whole file.

**No account code from the chart appears here.** The engine resolves accounts by
id and never reads a code, so the fixture uses codes no published chart uses
(``FIXTURE-D``, ``FIXTURE-C``, ...). The content of the general chart is `OD-22`,
open; a plausible-looking `221` in a fixture would be that content arriving
through the back door, and the next reader would take it for the real thing
(R15).

**Under the application role, like every test in this suite** (T1). The two
checks that read -- the period and the chart -- go through the same policies a
request does, so a posting that only passes because the seeding connection could
see more would fail here.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest

from evidenta.accounting.periods.errors import (
    PeriodLockedError,
    PeriodNotFoundError,
    PeriodNotOpenError,
)
from evidenta.accounting.posting.invariants import (
    AccountNotPostableError,
    MalformedLineAmountError,
    MixedCompanyError,
    MixedPeriodError,
    MixedTenantError,
    NoLinesError,
    Origin,
    OutOfBalanceError,
    PostingRefusedError,
    ProposedLine,
    ProposedPosting,
    SourceNotSingularError,
    ZeroAmountLineError,
    verify,
)
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

#: A Wednesday in the open month. Everything is dated relative to it, so a change
#: of month in the fixture cannot leave one test silently checking another period.
POSTING = date(2026, 1, 15)


# --- the world ---------------------------------------------------------------


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="posting")


def seed_account(
    seed: Callable[..., None],
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    code: str,
    *,
    blocked: bool = False,
    valid_from: str = "2020-01-01",
    valid_to: str | None = None,
) -> uuid.UUID:
    """One account of the company's own -- ``origin = 'company'``, no template.

    Deliberately not instantiated from a template. The engine asks the chart
    service for the set of postable ids and nothing else; building a template
    version here would add rows no assertion reads, and would put invented
    account codes one step closer to looking official.
    """
    account_id = uuid.uuid4()
    seed(
        "INSERT INTO company_account (id, tenant_id, company_id, account_code,"
        " parent_id, origin, template_account_id, name_ro, account_class,"
        " normal_balance, allows_subaccounts, currency_tracking, quantity_tracking,"
        " required_dimensions, is_blocked, valid_from, valid_to, created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, NULL, 'company', NULL, %s, 'asset', 'debit',"
        " false, false, false, '{}'::text[], %s, %s, %s, now(), now())",
        [
            account_id,
            tenant_id,
            company_id,
            code,
            f"Cont de fixture {code}",
            blocked,
            valid_from,
            valid_to,
        ],
    )
    return account_id


def seed_period(
    seed: Callable[..., None],
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    year_id: uuid.UUID,
    *,
    period_no: int,
    start: str,
    end: str,
    status: str,
) -> uuid.UUID:
    """One month. A closed or locked one must say when it was closed."""
    period_id = uuid.uuid4()
    closed_at = "now()" if status in ("closed", "locked") else "NULL"
    seed(
        "INSERT INTO period (id, tenant_id, company_id, fiscal_year_id, period_no,"
        " start_date, end_date, status, reopened_count, closed_at, created_at, updated_at)"
        f" VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, {closed_at}, now(), now())",
        [period_id, tenant_id, company_id, year_id, period_no, start, end, status],
    )
    return period_id


@pytest.fixture
def scene(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> dict[str, uuid.UUID]:
    """One company, three months in three states, four accounts.

    Three states because R12 has three answers and they are not interchangeable:
    reopening fixes a closed month and can never fix a locked one, so a caller
    that could not tell them apart could not tell a user what to do next.
    """
    tenant = world["tenant_a"]
    company = company_of(tenant, "1002600000401", "Alpha Postare")
    grant_company(tenant, company, world["user_a"], world["user_a"])

    year_id = uuid.uuid4()
    seed(
        "INSERT INTO fiscal_year (id, tenant_id, company_id, code, start_date, end_date,"
        " status, created_at, updated_at)"
        " VALUES (%s, %s, %s, '2026', '2026-01-01', '2026-12-31', 'open', now(), now())",
        [year_id, tenant, company],
    )

    return {
        "tenant": tenant,
        "company": company,
        "open_period": seed_period(
            seed,
            tenant,
            company,
            year_id,
            period_no=1,
            start="2026-01-01",
            end="2026-01-31",
            status="open",
        ),
        "closed_period": seed_period(
            seed,
            tenant,
            company,
            year_id,
            period_no=2,
            start="2026-02-01",
            end="2026-02-28",
            status="closed",
        ),
        "locked_period": seed_period(
            seed,
            tenant,
            company,
            year_id,
            period_no=3,
            start="2026-03-01",
            end="2026-03-31",
            status="locked",
        ),
        "debit_account": seed_account(seed, tenant, company, "FIXTURE-D"),
        "credit_account": seed_account(seed, tenant, company, "FIXTURE-C"),
        "blocked_account": seed_account(seed, tenant, company, "FIXTURE-B", blocked=True),
        "closed_account": seed_account(seed, tenant, company, "FIXTURE-X", valid_to="2026-01-10"),
    }


# --- building a proposal -----------------------------------------------------


def make_line(
    scene: dict[str, uuid.UUID],
    *,
    debit: str = "0",
    credit: str = "0",
    account_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    company_id: uuid.UUID | None = None,
    on: date = POSTING,
) -> ProposedLine:
    return ProposedLine(
        tenant_id=tenant_id or scene["tenant"],
        company_id=company_id or scene["company"],
        accounting_date=on,
        account_id=account_id or scene["debit_account"],
        debit=Decimal(debit),
        credit=Decimal(credit),
    )


def balanced(scene: dict[str, uuid.UUID], amount: str = "1000.0000") -> tuple[ProposedLine, ...]:
    """The smallest correct posting: one debit, one credit, same amount."""
    return (
        make_line(scene, debit=amount),
        make_line(scene, credit=amount, account_id=scene["credit_account"]),
    )


def make_posting(
    scene: dict[str, uuid.UUID],
    lines: tuple[ProposedLine, ...],
    *,
    on: date = POSTING,
    event_id: uuid.UUID | None = None,
    origin: Origin | None = None,
    with_event: bool = True,
    with_origin: bool = True,
) -> ProposedPosting:
    return ProposedPosting(
        tenant_id=scene["tenant"],
        company_id=scene["company"],
        accounting_date=on,
        accounting_event_id=(event_id or uuid.uuid4()) if with_event else None,
        origin=(
            origin or Origin(module="manual", document_type="fixture", document_id=uuid.uuid4())
        )
        if with_origin
        else None,
        lines=lines,
    )


# --- the posting that is correct ---------------------------------------------


def test_a_well_formed_posting_is_accepted_and_names_its_period(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """And it returns the period, which is not a convenience.

    Resolving the period is invariant 3's own work. Handing it back means the
    writer does not resolve it a second time: between two reads a month can be
    closed, and the entry would land in a period the engine checked as open.
    """
    with tenant_context(context):
        assert verify(make_posting(scene, balanced(scene))) == scene["open_period"]


# --- invariant 1: the sums are equal, in the functional currency (R11) -------


def test_an_unbalanced_posting_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The database says the same thing at COMMIT, in the wrong shape.

    ``journal_entry_balance_at_commit`` is a deferred constraint trigger: it
    fires after the last statement, with a ``check_violation`` that reaches
    Python as ``IntegrityError`` and carries no stable code. The engine answers
    the same question with one (C10), before the write.
    """
    lines = (
        make_line(scene, debit="1000.0000"),
        make_line(scene, credit="999.0000", account_id=scene["credit_account"]),
    )
    with tenant_context(context), pytest.raises(OutOfBalanceError) as excinfo:
        verify(make_posting(scene, lines))
    assert excinfo.value.code == "posting.out_of_balance"


def test_a_posting_with_no_lines_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Zero equals zero, so the balance check alone would let this through.

    It is the one case where invariant 1 is satisfied and the posting is still
    not one -- the database catches it at COMMIT with "has no amount", by which
    time the handler has returned.
    """
    with tenant_context(context), pytest.raises(NoLinesError) as excinfo:
        verify(make_posting(scene, ()))
    assert excinfo.value.code == "posting.no_lines"


# --- invariant 2: one tenant (R1), and therefore one company ----------------


def test_a_line_belonging_to_another_tenant_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID], world: dict[str, uuid.UUID]
) -> None:
    """The RLS policy refuses the row too, and cannot say why.

    ``WITH CHECK (tenant_id = app.current_tenant_id() ...)`` answers "new row
    violates row-level security policy" -- true, unbranchable, and identical to
    the message a missing context produces.
    """
    lines = (
        make_line(scene, debit="1000.0000", tenant_id=world["tenant_b"]),
        make_line(scene, credit="1000.0000", account_id=scene["credit_account"]),
    )
    with tenant_context(context), pytest.raises(MixedTenantError) as excinfo:
        verify(make_posting(scene, lines))
    assert excinfo.value.code == "posting.mixed_tenant"


def test_a_line_belonging_to_another_company_is_refused(
    context: TenantContext,
    scene: dict[str, uuid.UUID],
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> None:
    """Same tenant, second company -- and the database would accept both lines.

    The second company is granted deliberately, which is what makes this a real
    case rather than one RLS happens to catch. ``journal_line``'s policy admits
    any company the context may reach (``rls.has_company_access``), and an
    accountant with two client companies may reach both; ``company_id`` itself is
    a plain column with no key (R21). So both lines pass, the entry is written
    across two companies, and it is found later by a trial balance that stopped
    adding up.
    """
    other = company_of(world["tenant_a"], "1002600000402", "Alpha Secunda")
    grant_company(world["tenant_a"], other, world["user_a"], world["user_a"])
    lines = (
        make_line(scene, debit="1000.0000", company_id=other),
        make_line(scene, credit="1000.0000", account_id=scene["credit_account"]),
    )
    with tenant_context(context), pytest.raises(MixedCompanyError) as excinfo:
        verify(make_posting(scene, lines))
    assert excinfo.value.code == "posting.mixed_company"


# --- invariant 3: one period, and it is open (R12) --------------------------


def test_a_closed_period_refuses_the_posting(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """R12 says the engine refuses, not the interface -- and here it does.

    **The refusal arrives as a `periods.*` error, not a `posting.*` one**, and
    that is the contract rather than an oversight: the period module owns the
    three-state machine and its three codes, and re-raising them under one
    posting code would tell a caller "it did not post" while hiding whether
    reopening is even possible. Both families are `ApiError`, so a caller that
    only records the failure catches that and reads `.code`.
    """
    february = date(2026, 2, 10)
    lines = (
        make_line(scene, debit="1000.0000", on=february),
        make_line(scene, credit="1000.0000", account_id=scene["credit_account"], on=february),
    )
    with tenant_context(context), pytest.raises(PeriodNotOpenError) as excinfo:
        verify(make_posting(scene, lines, on=february))
    assert excinfo.value.code == "periods.period_not_open"


def test_a_locked_period_refuses_with_its_own_code(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Not flattened into one "did not post" code, deliberately.

    Reopening answers a closed month and never answers a locked one, so a caller
    that cannot tell the two apart cannot tell the user what to do next.
    """
    march = date(2026, 3, 10)
    lines = (
        make_line(scene, debit="1000.0000", on=march),
        make_line(scene, credit="1000.0000", account_id=scene["credit_account"], on=march),
    )
    with tenant_context(context), pytest.raises(PeriodLockedError) as excinfo:
        verify(make_posting(scene, lines, on=march))
    assert excinfo.value.code == "periods.period_locked"


def test_a_date_no_period_covers_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """A hole in the calendar is not a closed month.

    Answering it by creating a period on demand would let the first posting of an
    unopened exercise build its own container, and nobody would ever review the
    date that opened it.
    """
    later = date(2027, 5, 4)
    lines = (
        make_line(scene, debit="1000.0000", on=later),
        make_line(scene, credit="1000.0000", account_id=scene["credit_account"], on=later),
    )
    with tenant_context(context), pytest.raises(PeriodNotFoundError) as excinfo:
        verify(make_posting(scene, lines, on=later))
    assert excinfo.value.code == "periods.period_not_found"


def test_a_line_outside_the_postings_period_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """One entry, two months. The database checks only the entry's own date.

    ``journal_entry_needs_open_period`` compares ``journal_entry.accounting_date``
    against its period. Line dates are never looked at -- and they are the
    partition column of the largest table in the system, so an entry straddling
    two months lands in two partitions and its own period contains half of it.
    """
    lines = (
        make_line(scene, debit="1000.0000"),
        make_line(
            scene, credit="1000.0000", account_id=scene["credit_account"], on=date(2026, 2, 3)
        ),
    )
    with tenant_context(context), pytest.raises(MixedPeriodError) as excinfo:
        verify(make_posting(scene, lines))
    assert excinfo.value.code == "posting.mixed_period"


def test_a_line_dated_elsewhere_inside_the_same_period_is_accepted(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The invariant says *period*, not *date*, and the difference is deliberate.

    Refusing this would be stricter than ADR-036 section 5.2 asks -- and the
    stricter rule is not obviously the right one to invent here, so it is not
    invented. The last day of the month is used on purpose: ``period.end_date``
    is inclusive, unlike every half-open validity window in the system, and
    comparing it as exclusive would reject the closing day of every month.
    """
    lines = (
        make_line(scene, debit="1000.0000", on=date(2026, 1, 2)),
        make_line(
            scene, credit="1000.0000", account_id=scene["credit_account"], on=date(2026, 1, 31)
        ),
    )
    with tenant_context(context):
        assert verify(make_posting(scene, lines)) == scene["open_period"]


# --- invariant 4: the account exists and is valid on the day ----------------


def test_an_account_outside_the_chart_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Nothing in the database can catch this one.

    ``journal_line.account_id`` carries no foreign key, by design (R21): ten
    incoming keys is a table that gets redesigned rather than repartitioned. The
    accepted consequence is stated in the ledger's own docstring -- validation
    happens when the posting resolves. This is that validation.
    """
    lines = (
        make_line(scene, debit="1000.0000", account_id=uuid.uuid4()),
        make_line(scene, credit="1000.0000", account_id=scene["credit_account"]),
    )
    with tenant_context(context), pytest.raises(AccountNotPostableError) as excinfo:
        verify(make_posting(scene, lines))
    assert excinfo.value.code == "posting.account_not_postable"


def test_a_blocked_account_is_refused(context: TenantContext, scene: dict[str, uuid.UUID]) -> None:
    """Blocking forbids new postings and keeps history readable (Spec B 2.4)."""
    lines = (
        make_line(scene, debit="1000.0000", account_id=scene["blocked_account"]),
        make_line(scene, credit="1000.0000", account_id=scene["credit_account"]),
    )
    with tenant_context(context), pytest.raises(AccountNotPostableError):
        verify(make_posting(scene, lines))


def test_an_account_closed_before_the_date_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Closed on 10 January; the posting is dated the 15th."""
    lines = (
        make_line(scene, debit="1000.0000", account_id=scene["closed_account"]),
        make_line(scene, credit="1000.0000", account_id=scene["credit_account"]),
    )
    with tenant_context(context), pytest.raises(AccountNotPostableError):
        verify(make_posting(scene, lines))


def test_the_same_account_is_postable_before_it_was_closed(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The chart is asked about the posting's date, never about today (R18).

    Same account, same fixture, five days earlier -- accepted. A resolver that
    read the clock would answer a recalculation of a closed period with this
    year's chart, silently and looking correct.
    """
    early = date(2026, 1, 5)
    lines = (
        make_line(scene, debit="1000.0000", account_id=scene["closed_account"], on=early),
        make_line(scene, credit="1000.0000", account_id=scene["credit_account"], on=early),
    )
    with tenant_context(context):
        assert verify(make_posting(scene, lines, on=early)) == scene["open_period"]


# --- invariant 5: no line with a zero amount --------------------------------


def test_a_zero_amount_line_is_refused(context: TenantContext, scene: dict[str, uuid.UUID]) -> None:
    """The entry around it still balances, which is why it needs a check at all.

    ``journal_line_one_side_only`` refuses the row too, at INSERT. What this
    proves is the part that CHECK cannot give: a stable code and the line number,
    delivered before any row of the entry exists -- so the event is marked
    ``failed`` with a reason rather than a half-written entry being rolled back.
    """
    lines = (
        make_line(scene, debit="1000.0000"),
        make_line(scene, credit="1000.0000", account_id=scene["credit_account"]),
        make_line(scene, account_id=scene["blocked_account"]),
    )
    with tenant_context(context), pytest.raises(ZeroAmountLineError) as excinfo:
        verify(make_posting(scene, lines))
    assert excinfo.value.code == "posting.zero_amount_line"


def test_a_line_carrying_both_sides_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """One movement modelled as one line instead of two.

    ``journal_line_one_side_only`` refuses it in the database as well. The code
    is separate from the zero case because the diagnosis is: a zero line is
    usually a missing value, this is a handler with the wrong shape.
    """
    lines = (
        make_line(scene, debit="1000.0000", credit="1000.0000"),
        make_line(scene, credit="1000.0000", account_id=scene["credit_account"]),
    )
    with tenant_context(context), pytest.raises(MalformedLineAmountError) as excinfo:
        verify(make_posting(scene, lines))
    assert excinfo.value.code == "posting.malformed_line_amount"


def test_a_negative_amount_is_refused(context: TenantContext, scene: dict[str, uuid.UUID]) -> None:
    """A negative line would make the month's turnover go *down* by the entry.

    The same reason storno mirrors the lines instead of negating them (Spec B
    section 9.2): a trial balance would stop showing the activity that happened.
    """
    lines = (
        make_line(scene, debit="-1000.0000"),
        make_line(scene, credit="-1000.0000", account_id=scene["credit_account"]),
    )
    with tenant_context(context), pytest.raises(MalformedLineAmountError):
        verify(make_posting(scene, lines))


# --- invariant 6: exactly one source (R13) ----------------------------------


def test_a_posting_naming_no_accounting_event_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Even a manual note has one (Spec B section 1.5).

    Two paths into the ledger would mean lineage, idempotency and effect
    enumeration implemented twice, and the second implementation is always the
    one that breaks.
    """
    with tenant_context(context), pytest.raises(SourceNotSingularError) as excinfo:
        verify(make_posting(scene, balanced(scene), with_event=False))
    assert excinfo.value.code == "posting.source_not_singular"


def test_a_posting_naming_no_source_document_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The last hop of the R13 chain carries no foreign key, by design (D2).

    A key from ``accounting_event`` to the source document would make accounting
    know the schema of the module that produced it. Nothing else notices the link
    is missing, so this is where it is noticed.
    """
    with tenant_context(context), pytest.raises(SourceNotSingularError):
        verify(make_posting(scene, balanced(scene), with_origin=False))


def test_a_source_with_a_blank_document_type_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """A partial origin is worse than none: it looks populated.

    ``source_document_type`` is a text column with no CHECK, so an empty string
    is a perfectly valid row and a dead end for anybody drilling down.
    """
    origin = Origin(module="manual", document_type="  ", document_id=uuid.uuid4())
    with tenant_context(context), pytest.raises(SourceNotSingularError):
        verify(make_posting(scene, balanced(scene), origin=origin))


# --- the contract around the six --------------------------------------------


def test_the_cheap_checks_run_before_the_database_is_touched(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """An unbalanced posting into a closed period reports the balance.

    Order is part of the contract, not an accident of how the function was
    written: an importer pays the two reads for every bad row otherwise. This
    test is what stops a later reordering from being invisible.
    """
    february = date(2026, 2, 10)
    lines = (
        make_line(scene, debit="1000.0000", on=february),
        make_line(scene, credit="1.0000", account_id=scene["credit_account"], on=february),
    )
    with tenant_context(context), pytest.raises(OutOfBalanceError):
        verify(make_posting(scene, lines, on=february))


def test_every_refusal_carries_a_distinct_stable_code() -> None:
    """C10: the code is the contract, the message is for the log.

    Checked over the family rather than per class, so a copied-and-pasted
    subclass that forgot to change ``code`` fails here instead of at the first
    caller that branched on it and got the wrong answer.
    """
    family = PostingRefusedError.__subclasses__()
    codes = [subclass.code for subclass in family]

    assert len(codes) == len(set(codes))
    assert all(code.startswith("posting.") for code in codes)
    assert len(family) >= 6
