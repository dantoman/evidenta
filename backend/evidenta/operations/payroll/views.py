"""Payroll over HTTP -- people, contracts, amendments, timesheet.

Nothing here computes anything. The endpoints record what an employer decided --
who works here, under which clauses, from when, by which order -- and read it
back. What those facts are worth in money is the payroll run, and an amount
returned from here would be that calculation living in the wrong layer.

**No `Idempotency-Key`** (`C9`): none of these produces a financial effect. The
contract number and the amendment number are unique per company, so a repeated
POST is refused by the database rather than silently duplicated -- which is the
protection that matters at this layer.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.fiscal.registry.services.relationships import relationship_types
from evidenta.operations.payroll.models import EMPLOYER_CAS_POINTS, TaxResidency
from evidenta.operations.payroll.services.contracts import (
    add_amendment,
    as_dict,
    clauses_in_force_on,
    contract_in_context,
    contracts_of,
    create_contract,
    end_contract,
)
from evidenta.operations.payroll.services.people import (
    create_employee,
    employee_in_context,
    employees_of,
)
from evidenta.operations.payroll.services.timesheets import (
    close_month,
    days_of,
    month_in_context,
    months_of,
    open_month,
    set_days,
)
from evidenta.platform.api.errors import ApiError
from evidenta.platform.rls.context import MissingTenantContextError, current_context


class EmployeeSerializer(serializers.Serializer[dict[str, Any]]):
    last_name = serializers.CharField()
    first_name = serializers.CharField()
    tax_residency = serializers.ChoiceField(choices=TaxResidency.values)
    idnp = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    identity_document_type = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    identity_document_number = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    social_insurance_code = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class ContractSerializer(serializers.Serializer[dict[str, Any]]):
    employee_id = serializers.UUIDField()
    relationship_type = serializers.CharField()
    contract_number = serializers.CharField()
    signed_on = serializers.DateField()
    effective_from = serializers.DateField()
    effective_to = serializers.DateField(required=False, allow_null=True)
    hire_order_number = serializers.CharField()
    hire_order_date = serializers.DateField()
    position_title = serializers.CharField()
    base_salary = serializers.DecimalField(max_digits=18, decimal_places=4)
    weekly_hours = serializers.DecimalField(max_digits=5, decimal_places=2)
    cas_payer_point = serializers.ChoiceField(choices=list(EMPLOYER_CAS_POINTS))


class AmendmentSerializer(serializers.Serializer[dict[str, Any]]):
    amendment_number = serializers.CharField()
    signed_on = serializers.DateField()
    effective_from = serializers.DateField()
    order_number = serializers.CharField()
    order_date = serializers.DateField()
    changed_clause = serializers.CharField()
    note = serializers.CharField(required=False, allow_blank=True, default="")
    position_title = serializers.CharField(required=False, allow_null=True)
    base_salary = serializers.DecimalField(
        max_digits=18, decimal_places=4, required=False, allow_null=True
    )
    weekly_hours = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True
    )


class TerminationSerializer(serializers.Serializer[dict[str, Any]]):
    ended_on = serializers.DateField()
    order_number = serializers.CharField()
    order_date = serializers.DateField()


class TimesheetSerializer(serializers.Serializer[dict[str, Any]]):
    year = serializers.IntegerField(min_value=2000, max_value=2100)
    month = serializers.IntegerField(min_value=1, max_value=12)
    norm_hours = serializers.DecimalField(max_digits=7, decimal_places=2)


class DaySerializer(serializers.Serializer[dict[str, Any]]):
    work_date = serializers.DateField()
    hours_worked = serializers.DecimalField(max_digits=5, decimal_places=2)
    night_hours = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, default=Decimal("0")
    )
    holiday_hours = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, default=Decimal("0")
    )


class DaysSerializer(serializers.Serializer[dict[str, Any]]):
    days = DaySerializer(many=True)


class EmployeeListView(APIView):
    def get(self, request: Request, company_id: uuid.UUID) -> Response:
        return Response(employees_of(company_id, query=request.query_params.get("q")))

    def post(self, request: Request, company_id: uuid.UUID) -> Response:
        context = _context()
        payload = EmployeeSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        employee = create_employee(
            tenant_id=context.tenant_id,
            company_id=company_id,
            last_name=data["last_name"],
            first_name=data["first_name"],
            tax_residency=data["tax_residency"],
            idnp=data.get("idnp"),
            identity_document_type=data.get("identity_document_type"),
            identity_document_number=data.get("identity_document_number"),
            social_insurance_code=data.get("social_insurance_code"),
        )
        return Response(employee_in_context(employee.id), status=201)


class EmployeeDetailView(APIView):
    def get(self, request: Request, employee_id: uuid.UUID) -> Response:
        return Response(employee_in_context(employee_id))


class ContractListView(APIView):
    def get(self, request: Request, company_id: uuid.UUID) -> Response:
        employee = request.query_params.get("employee_id")
        return Response(
            contracts_of(
                company_id,
                employee_id=uuid.UUID(employee) if employee else None,
                include_ended=request.query_params.get("include_ended") == "true",
            )
        )

    def post(self, request: Request, company_id: uuid.UUID) -> Response:
        context = _context()
        payload = ContractSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        contract = create_contract(
            tenant_id=context.tenant_id,
            company_id=company_id,
            employee_id=data["employee_id"],
            relationship_type=data["relationship_type"],
            contract_number=data["contract_number"],
            signed_on=data["signed_on"],
            effective_from=data["effective_from"],
            effective_to=data.get("effective_to"),
            hire_order_number=data["hire_order_number"],
            hire_order_date=data["hire_order_date"],
            position_title=data["position_title"],
            base_salary=data["base_salary"],
            weekly_hours=data["weekly_hours"],
            cas_payer_point=data["cas_payer_point"],
        )
        return Response(as_dict(contract), status=201)


class ContractDetailView(APIView):
    def get(self, request: Request, contract_id: uuid.UUID) -> Response:
        return Response(contract_in_context(contract_id))


class AmendmentListView(APIView):
    def post(self, request: Request, contract_id: uuid.UUID) -> Response:
        payload = AmendmentSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        add_amendment(
            contract_id=contract_id,
            amendment_number=data["amendment_number"],
            signed_on=data["signed_on"],
            effective_from=data["effective_from"],
            order_number=data["order_number"],
            order_date=data["order_date"],
            changed_clause=data["changed_clause"],
            note=data.get("note", ""),
            position_title=data.get("position_title"),
            base_salary=data.get("base_salary"),
            weekly_hours=data.get("weekly_hours"),
        )
        return Response(contract_in_context(contract_id), status=201)


class ContractTerminationView(APIView):
    def post(self, request: Request, contract_id: uuid.UUID) -> Response:
        payload = TerminationSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        end_contract(
            contract_id=contract_id,
            ended_on=data["ended_on"],
            order_number=data["order_number"],
            order_date=data["order_date"],
        )
        return Response(contract_in_context(contract_id))


class ContractClausesView(APIView):
    """What was in force on a date -- read by walking the series (ADR-067)."""

    def get(self, request: Request, contract_id: uuid.UUID) -> Response:
        raw = request.query_params.get("on")
        if not raw:
            raise ClauseDateRequiredError(
                "the date is required: 'what is in force' with no date is a question "
                "about today asked of a contract that has a history"
            )
        try:
            on = date.fromisoformat(raw)
        except ValueError as exc:
            raise ClauseDateRequiredError(f"{raw!r} is not a date") from exc

        clauses = clauses_in_force_on(contract_id, on)
        return Response(
            {
                "on": str(on),
                "position_title": clauses.position_title,
                "base_salary": str(clauses.base_salary),
                "weekly_hours": str(clauses.weekly_hours),
                "set_by": clauses.set_by,
            }
        )


class ClauseDateRequiredError(ApiError):
    code = "payroll.clause_date_required"
    status = 422


class TimesheetListView(APIView):
    def get(self, request: Request, company_id: uuid.UUID) -> Response:
        return Response(months_of(company_id))

    def post(self, request: Request, company_id: uuid.UUID) -> Response:
        context = _context()
        payload = TimesheetSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        sheet = open_month(
            tenant_id=context.tenant_id,
            company_id=company_id,
            year=data["year"],
            month=data["month"],
            norm_hours=data["norm_hours"],
        )
        return Response(month_in_context(sheet.id), status=201)


class TimesheetDetailView(APIView):
    def get(self, request: Request, timesheet_id: uuid.UUID) -> Response:
        return Response(month_in_context(timesheet_id))


class TimesheetDaysView(APIView):
    def get(self, request: Request, timesheet_id: uuid.UUID, contract_id: uuid.UUID) -> Response:
        return Response(days_of(timesheet_id=timesheet_id, contract_id=contract_id))

    def put(self, request: Request, timesheet_id: uuid.UUID, contract_id: uuid.UUID) -> Response:
        payload = DaysSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        return Response(
            set_days(
                timesheet_id=timesheet_id,
                contract_id=contract_id,
                days=list(payload.validated_data["days"]),
            )
        )


class TimesheetClosingView(APIView):
    def post(self, request: Request, timesheet_id: uuid.UUID) -> Response:
        return Response(close_month(timesheet_id=timesheet_id))


class RelationshipTypeListView(APIView):
    def get(self, request: Request) -> Response:
        return Response(
            [
                {"code": row.code, "statutory_reference": row.statutory_reference}
                for row in relationship_types()
            ]
        )


def _context() -> Any:
    context = current_context()
    if context is None:
        raise MissingTenantContextError("no tenant context on this request")
    return context
