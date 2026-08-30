"""The monthly timesheet -- the input the calculation reads.

**Hours per day, not days per month.** Art. 22 para (1) wants the minimum
contribution base proportional to time worked, and at part time a share of the
contribution at the minimum wage. Days can be derived from hours; hours cannot be
derived from days, and the derivation nobody can perform is the one that gets
guessed.

**A closed month is frozen in the database**, not in this module. A day edited
after the month closed changes a result already reported, and a rule that lives
only in a service is a rule a bulk update walks past.

**No amount here.** The timesheet says how long somebody worked; what that is
worth is the payroll run, which is a later task.
"""

from __future__ import annotations

import calendar
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Sum

from evidenta.operations.payroll.models import (
    EmploymentContract,
    Timesheet,
    TimesheetDay,
    TimesheetStatus,
)
from evidenta.platform.api.errors import ApiError
from evidenta.platform.audit.services.recording import record


class TimesheetMalformedError(ApiError):
    code = "payroll.timesheet_malformed"
    status = 422


class TimesheetExistsError(ApiError):
    code = "payroll.timesheet_exists"
    status = 409


class TimesheetNotFoundError(ApiError):
    code = "payroll.timesheet_not_found"
    status = 404


class TimesheetClosedError(ApiError):
    """The month is closed and its days are frozen.

    A separate code from `timesheet_malformed` on purpose (`C10`): "you may not
    do this now" and "what you sent is wrong" call for different things from
    whoever is holding the screen.
    """

    code = "payroll.timesheet_closed"
    status = 409


def open_month(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    year: int,
    month: int,
    norm_hours: Decimal,
) -> Timesheet:
    """Open one month for attendance.

    `norm_hours` is entered, not derived: the working-time norm comes from the
    production calendar, which this repository does not hold. Deriving it from a
    calendar we do not have would be a number nobody can defend -- so it is asked
    for, which is what an accountant supplies anyway.
    """
    if not 1 <= month <= 12:
        raise TimesheetMalformedError("a month is between 1 and 12")
    if norm_hours is None or norm_hours <= 0:
        raise TimesheetMalformedError(
            "the month's norm of working hours is required: it is what the "
            "proportion in art. 22 para (1) is taken against"
        )

    try:
        with transaction.atomic():
            sheet = Timesheet.objects.create(
                tenant_id=tenant_id,
                company_id=company_id,
                year=year,
                month=month,
                norm_hours=norm_hours,
            )
    except IntegrityError as exc:
        raise TimesheetExistsError(f"{year}-{month:02d} is already open or closed") from exc

    record(
        action="payroll.timesheet_opened",
        entity_type="timesheet",
        entity_id=sheet.id,
        company_id=company_id,
        new_value={"year": year, "month": month, "norm_hours": str(norm_hours)},
    )
    return sheet


def set_days(
    *,
    timesheet_id: uuid.UUID,
    contract_id: uuid.UUID,
    days: list[dict[str, Any]],
) -> dict[str, Any]:
    """Write one contract's days for the month, replacing what was there.

    Replacing rather than merging: a screen that sends a month sends the whole
    month, and a merge would leave a day somebody deleted still counted. Every
    date is checked against the month it claims to belong to -- otherwise a day
    of March lands in the February sheet and the total is right in neither.
    """
    sheet = Timesheet.objects.filter(id=timesheet_id).first()
    if sheet is None:
        raise TimesheetNotFoundError("no such timesheet in this context")
    if sheet.status != TimesheetStatus.OPEN:
        raise TimesheetClosedError(
            f"{sheet.year}-{sheet.month:02d} is closed; its days no longer change"
        )

    contract = EmploymentContract.objects.filter(
        id=contract_id, company_id=sheet.company_id
    ).first()
    if contract is None:
        raise TimesheetMalformedError("no such contract in this company")

    last = calendar.monthrange(sheet.year, sheet.month)[1]
    first_day = date(sheet.year, sheet.month, 1)
    last_day = date(sheet.year, sheet.month, last)

    rows: list[TimesheetDay] = []
    seen: set[date] = set()
    for entry in days:
        work_date = _as_date(entry.get("work_date"))
        if not first_day <= work_date <= last_day:
            raise TimesheetMalformedError(
                f"{work_date} is not a day of {sheet.year}-{sheet.month:02d}"
            )
        if work_date in seen:
            raise TimesheetMalformedError(f"{work_date} appears twice")
        seen.add(work_date)

        worked = _as_hours(entry.get("hours_worked"), "hours_worked")
        night = _as_hours(entry.get("night_hours", 0), "night_hours")
        holiday = _as_hours(entry.get("holiday_hours", 0), "holiday_hours")
        if night > worked or holiday > worked:
            raise TimesheetMalformedError(
                f"{work_date}: night and holiday hours are part of the hours worked, "
                f"not additions to them -- they carry a different rate, not a "
                f"different day"
            )

        rows.append(
            TimesheetDay(
                tenant_id=sheet.tenant_id,
                company_id=sheet.company_id,
                timesheet=sheet,
                contract=contract,
                work_date=work_date,
                hours_worked=worked,
                night_hours=night,
                holiday_hours=holiday,
            )
        )

    with transaction.atomic():
        TimesheetDay.objects.filter(timesheet=sheet, contract=contract).delete()
        TimesheetDay.objects.bulk_create(rows)

    record(
        action="payroll.timesheet_days_set",
        entity_type="timesheet",
        entity_id=sheet.id,
        company_id=sheet.company_id,
        new_value={"contract": str(contract_id), "days": len(rows)},
    )
    return month_in_context(sheet.id)


def close_month(*, timesheet_id: uuid.UUID) -> dict[str, Any]:
    sheet = Timesheet.objects.filter(id=timesheet_id).first()
    if sheet is None:
        raise TimesheetNotFoundError("no such timesheet in this context")
    if sheet.status != TimesheetStatus.OPEN:
        raise TimesheetClosedError(f"{sheet.year}-{sheet.month:02d} is already closed")

    sheet.status = TimesheetStatus.CLOSED
    sheet.save(update_fields=["status"])

    record(
        action="payroll.timesheet_closed",
        entity_type="timesheet",
        entity_id=sheet.id,
        company_id=sheet.company_id,
    )
    return month_in_context(sheet.id)


def months_of(company_id: uuid.UUID) -> list[dict[str, Any]]:
    return [
        {
            "id": str(sheet.id),
            "year": sheet.year,
            "month": sheet.month,
            "norm_hours": str(sheet.norm_hours),
            "status": sheet.status,
        }
        for sheet in Timesheet.objects.filter(company_id=company_id).order_by("-year", "-month")
    ]


def month_in_context(timesheet_id: uuid.UUID) -> dict[str, Any]:
    """The month with one row per contract, totalled **on the server** (`C19`).

    A total computed in the client over a paginated set is a total that can
    disagree with the register; in a payroll sheet that is not a cosmetic
    inconsistency.
    """
    sheet = Timesheet.objects.filter(id=timesheet_id).first()
    if sheet is None:
        raise TimesheetNotFoundError("no such timesheet in this context")

    totals = {
        row["contract_id"]: row
        for row in TimesheetDay.objects.filter(timesheet=sheet)
        .values("contract_id")
        .annotate(
            worked=Sum("hours_worked"),
            night=Sum("night_hours"),
            holiday=Sum("holiday_hours"),
        )
    }

    lines = []
    contracts = EmploymentContract.objects.filter(company_id=sheet.company_id).select_related(
        "employee"
    )
    for contract in contracts.order_by("employee__last_name", "employee__first_name"):
        row = totals.get(contract.id)
        lines.append(
            {
                "contract_id": str(contract.id),
                "contract_number": contract.contract_number,
                "employee_name": (f"{contract.employee.last_name} {contract.employee.first_name}"),
                "hours_worked": str(row["worked"]) if row else "0.00",
                "night_hours": str(row["night"]) if row else "0.00",
                "holiday_hours": str(row["holiday"]) if row else "0.00",
                "days_present": TimesheetDay.objects.filter(
                    timesheet=sheet, contract=contract, hours_worked__gt=0
                ).count(),
            }
        )

    return {
        "id": str(sheet.id),
        "year": sheet.year,
        "month": sheet.month,
        "norm_hours": str(sheet.norm_hours),
        "status": sheet.status,
        "lines": lines,
    }


def days_of(*, timesheet_id: uuid.UUID, contract_id: uuid.UUID) -> list[dict[str, Any]]:
    return [
        {
            "work_date": str(day.work_date),
            "hours_worked": str(day.hours_worked),
            "night_hours": str(day.night_hours),
            "holiday_hours": str(day.holiday_hours),
        }
        for day in TimesheetDay.objects.filter(
            timesheet_id=timesheet_id, contract_id=contract_id
        ).order_by("work_date")
    ]


def _as_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise TimesheetMalformedError(f"{value!r} is not a date") from exc


def _as_hours(value: Any, field: str) -> Decimal:
    try:
        hours = Decimal(str(value))
    except (TypeError, ValueError, ArithmeticError) as exc:
        raise TimesheetMalformedError(f"{field}: {value!r} is not a number") from exc
    if not hours.is_finite() or hours < 0 or hours > 24:
        raise TimesheetMalformedError(f"{field} is between 0 and 24 hours")
    return hours
