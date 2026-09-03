"""Closing, reopening, locking -- F1.5.1, ADR-039 section 8 and Spec B section 6.2.

Three transitions and one that does not exist:

    open   -> closed   closing the month
    closed -> open     reopening, while the exercise is still open
    closed -> locked   closing the exercise, irreversible

``locked -> anything`` is missing on purpose, and its absence is tested. A
correction to a locked period goes through a reversal posted in an open one
(Spec B section 9.3) -- which is also why nothing here needs to reach back into
a closed period to fix it.

Every transition is recorded from the service that made it, explicitly rather
than through a signal (C4). Row timestamps say a row changed; they do not say
who reopened March, or why -- and that is the question a reviewer asks.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import QuerySet

from evidenta.accounting.ledger.services.trial_balance import trial_balance
from evidenta.accounting.periods.errors import (
    FiscalYearClosedError,
    FiscalYearNotFoundError,
    ManagementAccountsNotSettledError,
    PeriodLockedError,
    PeriodNotFoundError,
    PeriodNotOpenError,
    PeriodsStillOpenError,
)
from evidenta.accounting.periods.models import FiscalYear, FiscalYearStatus, Period, PeriodStatus
from evidenta.platform.audit.services.recording import record
from evidenta.platform.notifications.services import dispatch
from evidenta.platform.rls.context import MissingTenantContextError, current_context

#: The class of the management accounts, by the chart's own structure: the first
#: character of the code. `account_class` (asset/expense/...) says which
#: statement a balance lands in; the SNC class is what the norm speaks of, and
#: what "clasa 8" means.
MANAGEMENT_CLASS = "8"


def period_in_context(period_id: uuid.UUID) -> Period:
    """The period, or a refusal that does not say whose it is (IZ-04).

    Public since the closing door: the checks and the views need the row the
    transitions read, and a second reader in `views` would be a second place
    for the not-found answer to drift from this one.
    """
    period = Period.objects.filter(id=period_id).select_related("fiscal_year").first()
    if period is None:
        raise PeriodNotFoundError(f"period {period_id} is not visible in this context")
    return period


def _period_for_update(period_id: uuid.UUID) -> Period:
    """The period row, locked for the transition about to be written.

    Two requests closing (or reopening) the same month could both pass the
    status check on a plain read and both write; the ledger would not suffer --
    the event's key arbitrates -- but the audit would show two closings and the
    closing timestamp would belong to whichever committed last. The lock makes
    the second reader see the first writer's state and refuse.
    """
    period = (
        Period.objects.filter(id=period_id)
        .select_related("fiscal_year")
        .select_for_update(of=("self",))
        .first()
    )
    if period is None:
        raise PeriodNotFoundError(f"period {period_id} is not visible in this context")
    return period


def _actor() -> uuid.UUID:
    """Who is closing. Never a parameter -- it comes from the context.

    A closure whose author the caller chooses records whatever the caller
    prefers, which is not evidence that anyone reviewed the month.
    """
    context = current_context()
    if context is None:
        raise MissingTenantContextError("closing a period needs a tenant context")
    return context.user_id


def unsettled_management_accounts(period: Period) -> list[tuple[str, Decimal]]:
    """The class-8 accounts that still carry a balance at the period's last day.

    Read through the ledger's public service (D6): the balance is a sum over the
    lines up to the period's last day, never a stored figure. One reading for
    the refusal below and for the closing checks that show it beforehand, so the
    screen cannot say "settled" about a month the primitive then refuses.
    """
    balance = trial_balance(period.company_id, period.start_date, period.end_date)
    return [
        (row.account_code, row.closing)
        for row in balance.rows
        if row.account_code.startswith(MANAGEMENT_CLASS) and row.closing != 0
    ]


def assert_management_accounts_settled(period: Period) -> None:
    """The class-8 invariant of ADR-039 section 10.1, at the end of the period.

    Checked **here**, on the primitive, so that no path closes a month around it:
    the engine's `posting.services.closing.close_month` is the door that also
    records the event, but a caller reaching this service directly is refused
    just the same.
    """
    unsettled = unsettled_management_accounts(period)
    if unsettled:
        listed = ", ".join(f"{code} ({closing})" for code, closing in unsettled)
        raise ManagementAccountsNotSettledError(
            f"period {period.start_date:%Y-%m} cannot close: management accounts still "
            f"carry a balance at {period.end_date:%d.%m.%Y} -- {listed}. Clasa 8 is settled "
            f"through the ordinary postings, not by the closing (ADR-039 section 10.1)"
        )


@transaction.atomic
def close_period(period_id: uuid.UUID) -> Period:
    """``open -> closed``. Refuses anything else, including a second closing.

    Refuses, too, a month whose management accounts are not settled -- the
    class-8 invariant is validated at closing, not posted (ADR-039 section 10).
    """
    period = _period_for_update(period_id)
    if period.status == PeriodStatus.LOCKED:
        raise PeriodLockedError(f"period {period.start_date:%Y-%m} is locked; it does not reopen")
    if period.status != PeriodStatus.OPEN:
        raise PeriodNotOpenError(
            f"period {period.start_date:%Y-%m} is {period.status}, not open; "
            f"closing it again would move its closing date to today"
        )
    assert_management_accounts_settled(period)

    actor = _actor()
    period.status = PeriodStatus.CLOSED
    period.closed_at = datetime.now(UTC)
    period.closed_by_user_id = actor
    period.save(update_fields=["status", "closed_at", "closed_by_user_id", "updated_at"])

    record(
        action="period.closed",
        entity_type="period",
        entity_id=period.id,
        company_id=period.company_id,
        old_value={"status": PeriodStatus.OPEN.value},
        new_value={"status": PeriodStatus.CLOSED.value},
    )
    return period


@transaction.atomic
def reopen_period(period_id: uuid.UUID, reason: str) -> Period:
    """``closed -> open``, while the exercise is open, with the reason recorded.

    ``reason`` is required and goes into the audit entry, not into a column: the
    next reopening would overwrite a column, and the question asked later is how
    often this happened and why each time, not why the last time.
    """
    if not reason.strip():
        raise PeriodNotOpenError(
            "reopening a closed period needs a reason; an unexplained reopening "
            "is the one an inspection asks about first"
        )

    period = _period_for_update(period_id)
    if period.status == PeriodStatus.LOCKED:
        raise PeriodLockedError(
            f"period {period.start_date:%Y-%m} is locked; correct it with a reversal "
            f"posted in the open period (Spec B section 9.3)"
        )
    if period.status == PeriodStatus.OPEN:
        raise PeriodNotOpenError(f"period {period.start_date:%Y-%m} is already open")
    if period.fiscal_year.status != FiscalYearStatus.OPEN:
        raise FiscalYearClosedError(
            f"exercise {period.fiscal_year.code} is closed; nothing inside it moves again"
        )

    actor = _actor()
    period.status = PeriodStatus.OPEN
    period.reopened_count += 1
    period.last_reopened_at = datetime.now(UTC)
    period.last_reopened_by_user_id = actor
    period.save(
        update_fields=[
            "status",
            "reopened_count",
            "last_reopened_at",
            "last_reopened_by_user_id",
            "updated_at",
        ]
    )

    record(
        action="period.reopened",
        entity_type="period",
        entity_id=period.id,
        company_id=period.company_id,
        old_value={"status": PeriodStatus.CLOSED.value},
        new_value={
            "status": PeriodStatus.OPEN.value,
            "reason": reason,
            "reopened_count": period.reopened_count,
        },
    )
    # Spec B section 6.2 names two obligations for this transition, the audit
    # event and a notification; the second was missing. Every active member of
    # the workspace learns that a closed month moved, in the same transaction.
    dispatch.notify_tenant(
        tenant_id=period.tenant_id,
        type_key="period.reopened",
        params={"period": f"{period.start_date:%m.%Y}", "reason": reason.strip()},
        company_id=period.company_id,
    )
    return period


def _periods_of(year: FiscalYear) -> QuerySet[Period]:
    return Period.objects.filter(fiscal_year=year)


def exercise_with_periods(fiscal_year_id: uuid.UUID) -> tuple[FiscalYear, list[Period]]:
    """The exercise and its periods in order -- for the engine's year closing.

    A public reader (D6): the closing service in `posting` needs the exercise's
    dates and the state of every period, and asks here rather than reaching for
    the models. Refuses with the not-found code when the exercise is not visible
    in this context (IZ-04).
    """
    year = FiscalYear.objects.filter(id=fiscal_year_id).first()
    if year is None:
        raise FiscalYearNotFoundError(f"exercise {fiscal_year_id} is not visible in this context")
    return year, list(_periods_of(year).order_by("period_no"))


@transaction.atomic
def close_fiscal_year(fiscal_year_id: uuid.UUID) -> FiscalYear:
    """Close the exercise and lock every period in it -- irreversibly.

    The order matters and is the reason this is one service rather than two: a
    year marked closed over periods still marked open would leave the refusal to
    post depending on which of the two the caller happened to read.
    """
    year = FiscalYear.objects.filter(id=fiscal_year_id).first()
    if year is None:
        raise FiscalYearNotFoundError(f"exercise {fiscal_year_id} is not visible in this context")
    if year.status != FiscalYearStatus.OPEN:
        raise FiscalYearClosedError(f"exercise {year.code} is already closed")

    still_open = list(
        _periods_of(year).filter(status=PeriodStatus.OPEN).values_list("period_no", flat=True)
    )
    if still_open:
        numbers = ", ".join(str(number) for number in still_open)
        raise PeriodsStillOpenError(
            f"exercise {year.code} still has open periods ({numbers}); closing it "
            f"would lock work in progress out of its own month"
        )

    actor = _actor()
    now = datetime.now(UTC)
    locked = _periods_of(year).filter(status=PeriodStatus.CLOSED).update(status=PeriodStatus.LOCKED)

    year.status = FiscalYearStatus.CLOSED
    year.closed_at = now
    year.closed_by_user_id = actor
    year.save(update_fields=["status", "closed_at", "closed_by_user_id", "updated_at"])

    record(
        action="fiscal_year.closed",
        entity_type="fiscal_year",
        entity_id=year.id,
        company_id=year.company_id,
        old_value={"status": FiscalYearStatus.OPEN.value},
        new_value={"status": FiscalYearStatus.CLOSED.value, "periods_locked": locked},
    )
    return year
