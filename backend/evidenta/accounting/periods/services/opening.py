"""Opening an exercise, and the months it is made of -- F1.5.2, ADR-039 section 6.

The periods are generated from the exercise, not created one by one. That is the
whole reason the assumption "twelve months, January to December" cannot creep
back in: nobody types a period, so nobody types a January.

**Where this gets called from is not built yet.** Choosing a company's first
exercise belongs to onboarding, and creating a company is `P-9` (ADR-040),
decided and unwritten -- the same missing screen that leaves ``instantiate_chart``
without a production caller. Until then the service is called directly, which is
what the tests do and what a data migration would do.
"""

from __future__ import annotations

import calendar as _calendar
import uuid
from datetime import date

from django.db import transaction

from evidenta.accounting.periods.errors import (
    CompanyNotVisibleError,
    FiscalYearCodeTakenError,
    FiscalYearOverlapsError,
    InvalidFiscalYearWindowError,
)
from evidenta.accounting.periods.models import FiscalYear, FiscalYearStatus, Period
from evidenta.platform.audit.services.recording import record
from evidenta.platform.rls.context import MissingTenantContextError, current_context
from evidenta.platform.tenancy.services.access import company_visible_in_context

MAX_EXERCISE_MONTHS = 12


def _last_day_of_month(day: date) -> date:
    return day.replace(day=_calendar.monthrange(day.year, day.month)[1])


def _first_day_of_next_month(day: date) -> date:
    return (
        day.replace(year=day.year + 1, month=1, day=1)
        if day.month == 12
        else day.replace(month=day.month + 1, day=1)
    )


def _months_between(start: date, end: date) -> int:
    """Whole months covered by ``[start, end]``, both aligned to month edges."""
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


def _validate_window(start_date: date, end_date: date) -> None:
    """The exercise must be whole calendar months, and at most twelve of them.

    Both halves are law, not tidiness. The accounting period is strictly monthly
    (ADR-039 section 7), so an exercise starting on the 15th could not be divided
    into periods at all -- it would need either a half month, which does not
    exist, or a period silently stretched, which is worse. And art. 24 knows no
    exercise longer than twelve months: the rule that once carried a first period
    to 31 December of the *following* year lived in Legea 113/2007 and is gone
    (ADR-039 section 6).
    """
    if end_date <= start_date:
        raise InvalidFiscalYearWindowError(
            f"an exercise ends after it starts; {start_date} to {end_date} does not"
        )
    if start_date.day != 1:
        raise InvalidFiscalYearWindowError(
            f"an exercise starts on the first of a month; {start_date} does not, and the "
            f"accounting period is strictly monthly (ADR-039 section 7)"
        )
    if end_date != _last_day_of_month(end_date):
        raise InvalidFiscalYearWindowError(
            f"an exercise ends on the last day of a month; {end_date} does not"
        )
    months = _months_between(start_date, end_date)
    if months > MAX_EXERCISE_MONTHS:
        raise InvalidFiscalYearWindowError(
            f"{months} months: no exercise runs longer than {MAX_EXERCISE_MONTHS} "
            f"(Legea 287/2017, art. 24 -- see ADR-039 section 6)"
        )


@transaction.atomic
def open_fiscal_year(
    company_id: uuid.UUID, code: str, start_date: date, end_date: date
) -> FiscalYear:
    """Create the exercise and every period inside it, all ``open``.

    ``code`` is what an accountant calls the exercise -- ``2026``, or ``2026/2027``
    for one that straddles the calendar year. It is not parsed and nothing is
    derived from it: the dates are the truth, and deriving them from a label
    would put back the assumption this whole entity exists to remove.

    Periods are numbered within the exercise, so period 1 of an April-to-March
    exercise is April. Numbering them by calendar month would make the twelfth
    period of such an exercise be number 3, and every report grouping by
    ``period_no`` would quietly reorder itself.
    """
    context = current_context()
    if context is None:
        raise MissingTenantContextError("open_fiscal_year needs a tenant context")

    # Asked of `tenancy` rather than read off `Company`: the row's tenant is the
    # one in context by construction, since every policy here requires it, and
    # importing the model to find out would be `D6` arriving as a convenience.
    if not company_visible_in_context(company_id):
        raise CompanyNotVisibleError(f"company {company_id} is not visible in this context")

    _validate_window(start_date, end_date)

    if FiscalYear.objects.filter(company_id=company_id, code=code).exists():
        raise FiscalYearCodeTakenError(f"company {company_id} already has an exercise {code!r}")

    # The database refuses an overlap as well, with an exclusion constraint --
    # this query exists so the caller gets a stable code instead of an integrity
    # error, not because it is the guarantee. The guarantee is in the constraint,
    # where the 1C importer and any data migration also meet it.
    overlapping = FiscalYear.objects.filter(
        company_id=company_id, start_date__lte=end_date, end_date__gte=start_date
    ).first()
    if overlapping is not None:
        raise FiscalYearOverlapsError(
            f"{start_date} to {end_date} overlaps exercise {overlapping.code!r} "
            f"({overlapping.start_date} to {overlapping.end_date}); two exercises over "
            f"one day means two answers to which period a posting falls in"
        )

    year = FiscalYear.objects.create(
        tenant_id=context.tenant_id,
        company_id=company_id,
        code=code,
        start_date=start_date,
        end_date=end_date,
        status=FiscalYearStatus.OPEN,
    )

    periods = []
    month_start = start_date
    number = 1
    while month_start <= end_date:
        periods.append(
            Period(
                tenant_id=context.tenant_id,
                company_id=company_id,
                fiscal_year=year,
                period_no=number,
                start_date=month_start,
                end_date=_last_day_of_month(month_start),
            )
        )
        month_start = _first_day_of_next_month(month_start)
        number += 1
    Period.objects.bulk_create(periods)

    record(
        action="fiscal_year.opened",
        entity_type="fiscal_year",
        entity_id=year.id,
        company_id=company_id,
        new_value={
            "code": code,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "periods": len(periods),
        },
    )
    return year
