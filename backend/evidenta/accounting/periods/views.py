"""Opening an exercise over HTTP -- what a new company needs before it can post.

Separate from creating the company on purpose: `platform` does not import
`accounting` (DG), so the endpoint that creates a company cannot open an exercise
in the same call. Two explicit calls beat one endpoint that reaches across the
module graph, and the second one is where the dates are stated rather than
assumed.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.accounting.periods.errors import FiscalYearNotFoundError
from evidenta.accounting.periods.models import FiscalYear, Period, VatPeriod
from evidenta.accounting.periods.services.checks import closing_checks
from evidenta.accounting.periods.services.lifecycle import (
    exercise_with_periods,
    period_in_context,
    reopen_period,
)
from evidenta.accounting.periods.services.opening import open_fiscal_year
from evidenta.accounting.periods.services.vat import open_vat_periods
from evidenta.accounting.posting.services.closing import close_month, close_year
from evidenta.platform.capabilities.services.profile import active_profile
from evidenta.platform.rls.context import MissingTenantContextError, current_context
from evidenta.platform.tenancy.services.companies import functional_currency


class OpenFiscalYearSerializer(serializers.Serializer[dict[str, Any]]):
    """The exercise to open. Everything optional, defaulting to the calendar year.

    The default is the calendar year because that is the ordinary case in
    Moldova, not because the dates can be derived from the code: `code` is what
    an accountant calls the exercise and nothing is parsed out of it. A company
    whose exercise is not calendar states its dates, and they are stored as
    stated.
    """

    code = serializers.CharField(max_length=32, required=False)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)


def _rendered(year: FiscalYear) -> dict[str, Any]:
    return {
        "id": str(year.id),
        "code": year.code,
        "start_date": str(year.start_date),
        "end_date": str(year.end_date),
        "status": year.status,
        "periods": Period.objects.filter(fiscal_year_id=year.id).count(),
    }


class FiscalYearView(APIView):
    def get(self, request: Request, company_id: uuid.UUID) -> Response:
        rows = FiscalYear.objects.filter(company_id=company_id).order_by("start_date")
        return Response([_rendered(year) for year in rows])

    def post(self, request: Request, company_id: uuid.UUID) -> Response:
        payload = OpenFiscalYearSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)

        year = date.today().year
        start = data.get("start_date") or date(year, 1, 1)
        end = data.get("end_date") or date(start.year, 12, 31)
        code = data.get("code") or str(start.year)

        opened = open_fiscal_year(company_id, code, start, end)
        return Response(_rendered(opened), status=201)


class OpenVatPeriodsSerializer(serializers.Serializer[dict[str, Any]]):
    """The months to open, both stated. No default to the calendar year here:
    the sequence starts in the month the registration did, and only the caller
    knows which -- the service refuses anything that is not a month edge."""

    first_month = serializers.DateField()
    through = serializers.DateField()


def _vat_period_rendered(period: VatPeriod) -> dict[str, Any]:
    return {
        "id": str(period.id),
        "start_date": str(period.start_date),
        "end_date": str(period.end_date),
        "kind": period.kind,
    }


class VatPeriodView(APIView):
    """The VAT fiscal periods of a company -- ADR-039 §7, with a door since ADR-090.

    Separate from the registration for the reason the exercise is separate from
    the company: `platform` records the registration and does not import
    `accounting`, where the period lives. Two calls, and the second refuses a
    month the registration does not cover.
    """

    def get(self, request: Request, company_id: uuid.UUID) -> Response:
        rows = VatPeriod.objects.filter(company_id=company_id).order_by("start_date")
        return Response([_vat_period_rendered(period) for period in rows])

    def post(self, request: Request, company_id: uuid.UUID) -> Response:
        payload = OpenVatPeriodsSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        opened = open_vat_periods(company_id, data["first_month"], data["through"])
        return Response([_vat_period_rendered(period) for period in opened], status=201)


# --- the closing door (G1) ---------------------------------------------------------
#
# Four routes over services that already existed with no way in. The refusals are
# the engine's (`R12`; `periods.errors`), and the door only exposes them: nothing
# here decides whether a month may close. `close_month` and `close_year` are the
# posting engine's, because a closing is an accounting event somebody can point
# at (`R13`) -- the period primitive alone would change a status and record no
# event.
#
# **`Idempotency-Key` is not read here** (`C9`), for the reason the sales door
# gives: the key that matters is on the accounting event (`R19`), and the closing
# services derive it from the object -- `period.month_closed:<period>:<count>`,
# `period.year_closed:<year>` -- so a retry of the same closing answers with the
# same event. A header would be a second mechanism for a property the event has.
#
# **ADR-007 stays open.** Nothing here names the period a reversal lands in; the
# door closes and reopens months and leaves the correction's date to the
# reversal route, which requires it.


class ReopeningSerializer(serializers.Serializer[dict[str, Any]]):
    """The reason, required and not blank. The service refuses a blank reason
    too; the serializer says so before it, with the generic invalid code, so a
    client that forgot the field learns that at integration time."""

    reason = serializers.CharField(max_length=1000)


def _period_rendered(period: Period) -> dict[str, Any]:
    return {
        "id": str(period.id),
        "period_no": period.period_no,
        "start_date": str(period.start_date),
        "end_date": str(period.end_date),
        "status": period.status,
        "closed_at": period.closed_at.isoformat() if period.closed_at else None,
        "reopened_count": period.reopened_count,
    }


def _context() -> Any:
    context = current_context()
    if context is None:
        raise MissingTenantContextError("no tenant context on this request")
    return context


class PeriodListView(APIView):
    """The months of one exercise, in order, with their state.

    The company is in the path (`C8`) and is checked against the exercise: an
    exercise reached through the wrong company is answered as absent, the same
    answer a foreign one gets (IZ-04).
    """

    def get(self, request: Request, company_id: uuid.UUID, year_id: uuid.UUID) -> Response:
        year, periods = exercise_with_periods(year_id)
        if year.company_id != company_id:
            raise FiscalYearNotFoundError(f"exercise {year_id} is not visible in this context")
        return Response([_period_rendered(period) for period in periods])


class ClosingChecksView(APIView):
    """What stands between the month and its closing, counted on the server."""

    def get(self, request: Request, period_id: uuid.UUID) -> Response:
        return Response(
            [
                {"code": check.code, "count": check.count, "blocking": check.blocking}
                for check in closing_checks(period_id)
            ]
        )


class PeriodClosingView(APIView):
    """``open -> closed``, with its event. Posts nothing (ADR-039 section 10)."""

    def post(self, request: Request, period_id: uuid.UUID) -> Response:
        context = _context()
        period = period_in_context(period_id)
        result = close_month(
            period_id,
            actor_user_id=context.user_id,
            request_id=context.request_id,
            capability_snapshot=active_profile(period.company_id, period.end_date).as_snapshot(),
        )
        return Response(
            {
                "period": _period_rendered(period_in_context(period_id)),
                "accounting_event_id": str(result.accounting_event_id),
            }
        )


class PeriodReopeningView(APIView):
    """``closed -> open``, while the exercise is open, with the reason recorded."""

    def post(self, request: Request, period_id: uuid.UUID) -> Response:
        payload = ReopeningSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        period = reopen_period(period_id, str(payload.validated_data["reason"]))
        return Response(_period_rendered(period))


class FiscalYearClosingView(APIView):
    """The chain of ADR-050 (6/7 -> 351 -> 333), the last month, the exercise.

    One call and one transaction, in the service's order. The currency is the
    company's own, read from `tenancy` the way every other posting door reads
    it; the capability profile is the one in force on the exercise's last day,
    which is the date the chain carries (`R26`).
    """

    def post(self, request: Request, year_id: uuid.UUID) -> Response:
        context = _context()
        year, _ = exercise_with_periods(year_id)
        result = close_year(
            year_id,
            functional_currency=functional_currency(year.company_id),
            actor_user_id=context.user_id,
            request_id=context.request_id,
            capability_snapshot=active_profile(year.company_id, year.end_date).as_snapshot(),
        )
        closed, _ = exercise_with_periods(year_id)
        return Response(
            {
                "fiscal_year": _rendered(closed),
                "accounting_event_id": str(result.accounting_event_id),
                "journal_entry_id": (
                    str(result.journal_entry_id) if result.journal_entry_id else None
                ),
                "formulas": result.formulas,
                "periods_locked": result.periods_locked,
            }
        )
