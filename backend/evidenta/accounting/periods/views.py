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

from evidenta.accounting.periods.models import FiscalYear, Period, VatPeriod
from evidenta.accounting.periods.services.opening import open_fiscal_year
from evidenta.accounting.periods.services.vat import open_vat_periods


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
