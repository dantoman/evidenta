"""Accounting periods and exercises -- F1.5, under the application role.

Everything here runs inside ``tenant_context``, on the application connection
(T1). A test that closed a period as the owner would prove that the owner can
close a period, which nobody doubted.

Two kinds of assertion, deliberately mixed. The service-level ones say what an
accountant meets; the database-level ones say what is left when the service is
bypassed -- by the 1C importer, by a data migration, by a direct UPDATE. Where a
rule exists in both places, both are tested, because the whole reason the rule is
in the database is that the service is not the only way in.

**The April-to-March exercise is not an exotic case here, it is the default
test.** A suite written entirely on January-to-December would pass with the
calendar assumption baked in everywhere, which is the exact failure ADR-039
section 6 exists to prevent.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date

import pytest
from django.db import connection, transaction
from django.db.utils import IntegrityError, ProgrammingError

from evidenta.accounting.periods.errors import (
    FiscalYearClosedError,
    FiscalYearCodeTakenError,
    FiscalYearOverlapsError,
    InvalidFiscalYearWindowError,
    PeriodLockedError,
    PeriodNotFoundError,
    PeriodNotOpenError,
    PeriodsStillOpenError,
)
from evidenta.accounting.periods.models import FiscalYear, FiscalYearStatus, Period, PeriodStatus
from evidenta.accounting.periods.services.lifecycle import (
    close_fiscal_year,
    close_period,
    reopen_period,
)
from evidenta.accounting.periods.services.opening import open_fiscal_year
from evidenta.accounting.periods.services.resolution import assert_postable, period_for
from evidenta.platform.audit.models import AuditEvent
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="periods")


@pytest.fixture
def company(
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> uuid.UUID:
    company_id = company_of(world["tenant_a"], "1002600000101", "Alpha Contabil")
    grant_company(world["tenant_a"], company_id, world["user_a"], world["user_a"])
    return company_id


def open_calendar_2026(company_id: uuid.UUID) -> FiscalYear:
    return open_fiscal_year(company_id, "2026", date(2026, 1, 1), date(2026, 12, 31))


def open_april_to_march(company_id: uuid.UUID) -> FiscalYear:
    """The ordinary exercise of a subsidiary with a foreign parent.

    Art. 24 para. (1) letter b) of Law 287/2017: an entity applying its parent's
    reporting period. Nothing about it is a corner case except that a calendar
    assumption breaks on it.
    """
    return open_fiscal_year(company_id, "2026/2027", date(2026, 4, 1), date(2027, 3, 31))


# --- opening an exercise ----------------------------------------------------


def test_opening_generates_one_period_per_month(context: TenantContext, company: uuid.UUID) -> None:
    with tenant_context(context):
        year = open_calendar_2026(company)
        periods = list(Period.objects.filter(fiscal_year=year).order_by("period_no"))

        assert len(periods) == 12
        assert [p.period_no for p in periods] == list(range(1, 13))
        assert periods[0].start_date == date(2026, 1, 1)
        assert periods[0].end_date == date(2026, 1, 31)
        assert periods[-1].end_date == date(2026, 12, 31)
        assert all(p.status == PeriodStatus.OPEN for p in periods)


def test_a_non_calendar_exercise_numbers_its_periods_from_its_own_start(
    context: TenantContext, company: uuid.UUID
) -> None:
    """Period 1 is April, not month number 4.

    Numbering by calendar month would make the last period of this exercise
    number 3, and every report grouping by `period_no` would quietly reorder
    itself -- a defect that looks like a sorting bug and is a modelling one.
    """
    with tenant_context(context):
        year = open_april_to_march(company)
        periods = list(Period.objects.filter(fiscal_year=year).order_by("period_no"))

        assert len(periods) == 12
        assert periods[0].period_no == 1
        assert periods[0].start_date == date(2026, 4, 1)
        assert periods[-1].period_no == 12
        assert periods[-1].start_date == date(2027, 3, 1)
        assert periods[-1].end_date == date(2027, 3, 31)

        # February 2027 ends on the 28th. Generated, not typed.
        february = periods[10]
        assert (february.start_date, february.end_date) == (date(2027, 2, 1), date(2027, 2, 28))


def test_a_truncated_exercise_is_allowed(context: TenantContext, company: uuid.UUID) -> None:
    """Reorganisation and liquidation -- art. 24 para. (1) letter a).

    Shorter than twelve months is normal; longer is not.
    """
    with tenant_context(context):
        year = open_fiscal_year(company, "2026-lichidare", date(2026, 1, 1), date(2026, 3, 31))
        assert Period.objects.filter(fiscal_year=year).count() == 3


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (date(2026, 1, 15), date(2026, 12, 31)),  # starts mid-month
        (date(2026, 1, 1), date(2026, 12, 15)),  # ends mid-month
    ],
)
def test_an_exercise_must_be_whole_calendar_months(
    context: TenantContext, company: uuid.UUID, start: date, end: date
) -> None:
    """The accounting period is strictly monthly, so half a month has nowhere to go."""
    with tenant_context(context), pytest.raises(InvalidFiscalYearWindowError):
        open_fiscal_year(company, "bad", start, end)


def test_an_exercise_may_not_run_longer_than_twelve_months(
    context: TenantContext, company: uuid.UUID
) -> None:
    """Thirteen months is a reporting period the law does not know.

    The rule that once carried a first exercise to 31 December of the *following*
    year lived in Legea 113/2007 and is gone (ADR-039 section 6).
    """
    with tenant_context(context), pytest.raises(InvalidFiscalYearWindowError):
        open_fiscal_year(company, "2026-13", date(2026, 1, 1), date(2027, 1, 31))


def test_two_exercises_may_not_overlap(context: TenantContext, company: uuid.UUID) -> None:
    with tenant_context(context):
        open_calendar_2026(company)
        with pytest.raises(FiscalYearOverlapsError):
            open_fiscal_year(company, "2026-bis", date(2026, 6, 1), date(2027, 5, 31))


def test_the_database_refuses_an_overlap_the_service_never_saw(
    context: TenantContext, company: uuid.UUID
) -> None:
    """The service checks; the constraint guarantees.

    This is the path the 1C importer and any data migration take, and it is the
    reason the check is not only in Python.
    """
    with tenant_context(context):
        open_calendar_2026(company)

        with pytest.raises(IntegrityError, match="fiscal_year_no_overlap"), transaction.atomic():
            FiscalYear.objects.create(
                tenant_id=context.tenant_id,
                company_id=company,
                code="2026-smuggled",
                start_date=date(2026, 6, 1),
                end_date=date(2027, 5, 31),
            )


def test_the_same_code_is_refused_once_per_company(
    context: TenantContext, company: uuid.UUID
) -> None:
    with tenant_context(context):
        open_calendar_2026(company)
        with pytest.raises(FiscalYearCodeTakenError):
            open_fiscal_year(company, "2026", date(2027, 1, 1), date(2027, 12, 31))


# --- closing, reopening, locking --------------------------------------------


def test_closing_a_period_records_who_and_when(
    context: TenantContext, company: uuid.UUID, world: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        open_calendar_2026(company)
        january = period_for(company, date(2026, 1, 31))

        closed = close_period(january.id)

        assert closed.status == PeriodStatus.CLOSED
        assert closed.closed_at is not None
        assert closed.closed_by_user_id == world["user_a"]
        assert AuditEvent.objects.filter(action="period.closed", entity_id=january.id).exists()


def test_closing_a_closed_period_is_refused(context: TenantContext, company: uuid.UUID) -> None:
    """A second closing would move the closing date to today.

    Which is worse than it sounds: the date on which a month was closed is the
    one an inspection asks about.
    """
    with tenant_context(context):
        open_calendar_2026(company)
        january = period_for(company, date(2026, 1, 31))
        close_period(january.id)

        with pytest.raises(PeriodNotOpenError):
            close_period(january.id)


def test_reopening_counts_and_keeps_the_reason_in_the_audit(
    context: TenantContext, company: uuid.UUID
) -> None:
    """The reason lives in the audit entry, not in a column.

    A column would be overwritten by the next reopening, and the question asked
    later is how often this happened and why each time.
    """
    with tenant_context(context):
        open_calendar_2026(company)
        january = period_for(company, date(2026, 1, 15))
        close_period(january.id)

        reopened = reopen_period(january.id, "factura primita dupa inchidere")

        assert reopened.status == PeriodStatus.OPEN
        assert reopened.reopened_count == 1
        assert reopened.last_reopened_at is not None

        entry = AuditEvent.objects.filter(action="period.reopened", entity_id=january.id).first()
        assert entry is not None
        assert entry.new_value is not None
        assert entry.new_value["reason"] == "factura primita dupa inchidere"


def test_reopening_without_a_reason_is_refused(context: TenantContext, company: uuid.UUID) -> None:
    with tenant_context(context):
        open_calendar_2026(company)
        january = period_for(company, date(2026, 1, 15))
        close_period(january.id)

        with pytest.raises(PeriodNotOpenError):
            reopen_period(january.id, "   ")


def test_closing_the_exercise_refuses_while_a_period_is_still_open(
    context: TenantContext, company: uuid.UUID
) -> None:
    """Locking a period that still accepts postings would lock work out of its own month."""
    with tenant_context(context):
        year = open_calendar_2026(company)
        close_period(period_for(company, date(2026, 1, 15)).id)

        with pytest.raises(PeriodsStillOpenError):
            close_fiscal_year(year.id)


def test_closing_the_exercise_locks_every_period(
    context: TenantContext, company: uuid.UUID
) -> None:
    with tenant_context(context):
        year = open_calendar_2026(company)
        for period in Period.objects.filter(fiscal_year=year):
            close_period(period.id)

        closed = close_fiscal_year(year.id)

        assert closed.status == FiscalYearStatus.CLOSED
        assert closed.closed_at is not None
        assert set(Period.objects.filter(fiscal_year=year).values_list("status", flat=True)) == {
            PeriodStatus.LOCKED
        }


def test_a_locked_period_is_never_reopened_by_the_service(
    context: TenantContext, company: uuid.UUID
) -> None:
    with tenant_context(context):
        year = open_calendar_2026(company)
        for period in Period.objects.filter(fiscal_year=year):
            close_period(period.id)
        close_fiscal_year(year.id)

        january = period_for(company, date(2026, 1, 15))
        with pytest.raises(PeriodLockedError):
            reopen_period(january.id, "am mai gasit un document")


def test_a_locked_period_is_never_reopened_by_a_direct_update_either(
    context: TenantContext, company: uuid.UUID
) -> None:
    """The trigger, not the service -- this is the path an importer takes.

    A refusal that lives only in Python is a refusal the 1C importer and every
    data migration walk past, and reopening a filed exercise is exactly the thing
    that must not happen quietly.
    """
    with tenant_context(context):
        year = open_calendar_2026(company)
        for period in Period.objects.filter(fiscal_year=year):
            close_period(period.id)
        close_fiscal_year(year.id)
        january = period_for(company, date(2026, 1, 15))

        with pytest.raises(ProgrammingError, match="is locked"), transaction.atomic():
            Period.objects.filter(id=january.id).update(status=PeriodStatus.OPEN)


def test_a_closed_exercise_does_not_let_its_periods_reopen(
    context: TenantContext, company: uuid.UUID
) -> None:
    """The exercise is the outer gate, and it is checked before the period's own state."""
    with tenant_context(context):
        year = open_calendar_2026(company)
        for period in Period.objects.filter(fiscal_year=year):
            close_period(period.id)
        close_fiscal_year(year.id)

        with pytest.raises(FiscalYearClosedError):
            close_fiscal_year(year.id)


# --- what the posting engine will call --------------------------------------


def test_posting_into_a_closed_period_is_refused(
    context: TenantContext, company: uuid.UUID
) -> None:
    """R12, at the level where the engine will ask.

    **This is the half of F1.5.1 that can be demonstrated today.** The other
    half -- the engine itself refusing -- waits for F1.4, and the second barrier
    from Spec B section 6.3, a trigger on `journal_entry`, waits for F1.2.1,
    where the table it sits on is created.
    """
    with tenant_context(context):
        open_calendar_2026(company)
        january = period_for(company, date(2026, 1, 20))

        assert assert_postable(company, date(2026, 1, 20)).id == january.id

        close_period(january.id)
        with pytest.raises(PeriodNotOpenError):
            assert_postable(company, date(2026, 1, 20))


def test_posting_into_a_locked_period_says_so_with_its_own_code(
    context: TenantContext, company: uuid.UUID
) -> None:
    """Two codes, because the remedies differ: one can be reopened, one never can."""
    with tenant_context(context):
        year = open_calendar_2026(company)
        for period in Period.objects.filter(fiscal_year=year):
            close_period(period.id)
        close_fiscal_year(year.id)

        with pytest.raises(PeriodLockedError):
            assert_postable(company, date(2026, 1, 20))


def test_a_late_document_posts_in_the_period_of_its_accounting_date(
    context: TenantContext, company: uuid.UUID
) -> None:
    """ADR-039 section 9: a document dated 28 March, arriving 5 April, March closed.

    The period follows `accounting_date`, never `document_date` -- which is why
    the journal line carries both.
    """
    with tenant_context(context):
        open_calendar_2026(company)
        close_period(period_for(company, date(2026, 3, 28)).id)

        posted_into = assert_postable(company, date(2026, 4, 5))

        assert posted_into.start_date == date(2026, 4, 1)
        assert posted_into.status == PeriodStatus.OPEN


def test_a_date_no_exercise_covers_is_a_loud_refusal(
    context: TenantContext, company: uuid.UUID
) -> None:
    """No period is not the same as a closed period, and inventing one is worse.

    A posting that created its own container would open an exercise nobody chose
    -- and the starting period of a company is irreversible (ADR-039 section 11).
    """
    with tenant_context(context):
        open_calendar_2026(company)
        with pytest.raises(PeriodNotFoundError):
            assert_postable(company, date(2027, 1, 5))


# --- isolation and what cannot be undone ------------------------------------


def test_periods_of_another_tenant_are_invisible(
    context: TenantContext, company: uuid.UUID, world: dict[str, uuid.UUID]
) -> None:
    """IZ-01 for this table: absent, not forbidden."""
    with tenant_context(context):
        open_calendar_2026(company)

    other = TenantContext(
        tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="periods"
    )
    with tenant_context(other):
        assert Period.objects.count() == 0
        assert FiscalYear.objects.count() == 0
        with pytest.raises(PeriodNotFoundError):
            period_for(company, date(2026, 1, 20))


def test_a_period_cannot_be_deleted(context: TenantContext, company: uuid.UUID) -> None:
    """A missing privilege, not a convention in a service.

    A deleted period takes the trace of its own closing with it, and the entries
    posted into it stay behind referencing nothing.
    """
    with tenant_context(context):
        open_calendar_2026(company)
        january = period_for(company, date(2026, 1, 20))

        with (
            pytest.raises(ProgrammingError, match="permission denied"),
            transaction.atomic(),
        ):
            Period.objects.filter(id=january.id).delete()


def test_an_exercise_cannot_be_deleted(context: TenantContext, company: uuid.UUID) -> None:
    """Through raw SQL, because the ORM never gets that far.

    ``Period.fiscal_year`` is ``PROTECT``, so Django refuses in Python first --
    and a test that stopped there would be testing Django. What matters is the
    answer on the path that skips the ORM entirely, which is the one a data
    migration takes.
    """
    with tenant_context(context):
        year = open_calendar_2026(company)

        with (
            pytest.raises(ProgrammingError, match="permission denied"),
            transaction.atomic(),
            connection.cursor() as cursor,
        ):
            cursor.execute("DELETE FROM fiscal_year WHERE id = %s", [year.id])
