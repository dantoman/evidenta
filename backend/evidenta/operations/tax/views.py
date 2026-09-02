"""The unified monthly return over HTTP.

Nothing here computes anything: generation reads an approved payroll run through
payroll's public service and **freezes** what it read. A return is an artefact, so
the only writes are creating a version and recording that one was filed.

**No `Idempotency-Key`** (`C9`): none of these produces a financial effect, and the
uniqueness of `(company, period, version)` is what turns a repeated POST into a
refusal rather than a duplicate -- which at this layer is the protection that
matters.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from django.http import HttpResponse
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.operations.tax.services.ipc import (
    correct,
    declaration_in_context,
    declarations_of,
    generate,
    submit,
)
from evidenta.operations.tax.services.reconciliation import reconciliation_report
from evidenta.operations.tax.services.vat_register import (
    RegimeTotal,
    RegisterRow,
    VatRegister,
    vat_register,
    vat_register_csv,
)
from evidenta.platform.api.errors import ApiError
from evidenta.platform.rls.context import MissingTenantContextError, current_context


class GenerateSerializer(serializers.Serializer[dict[str, Any]]):
    year = serializers.IntegerField(min_value=2000, max_value=2100)
    month = serializers.IntegerField(min_value=1, max_value=12)


class SubmissionSerializer(serializers.Serializer[dict[str, Any]]):
    """The date it was filed, given rather than taken from the clock.

    The return goes through the tax service's own channel and is recorded here
    afterwards; a date invented at recording time would answer *when was this
    filed* with *when was this typed*.
    """

    submitted_on = serializers.DateField()


class IpcListView(APIView):
    def get(self, request: Request, company_id: uuid.UUID) -> Response:
        return Response(declarations_of(company_id))

    def post(self, request: Request, company_id: uuid.UUID) -> Response:
        context = _context()
        payload = GenerateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        return Response(
            generate(
                tenant_id=context.tenant_id,
                company_id=company_id,
                year=data["year"],
                month=data["month"],
            ),
            status=201,
        )


class IpcDetailView(APIView):
    def get(self, request: Request, declaration_id: uuid.UUID) -> Response:
        return Response(declaration_in_context(declaration_id))


class IpcCorrectionView(APIView):
    """Art. 188: a change is a corrected return, a new version, never an edit."""

    def post(self, request: Request, declaration_id: uuid.UUID) -> Response:
        return Response(correct(declaration_id=declaration_id), status=201)


class IpcSubmissionView(APIView):
    def post(self, request: Request, declaration_id: uuid.UUID) -> Response:
        payload = SubmissionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        return Response(
            submit(
                declaration_id=declaration_id,
                submitted_on=payload.validated_data["submitted_on"],
            )
        )


class IpcReconciliationView(APIView):
    """`T1`, in both directions, as something a person reads before filing."""

    def get(self, request: Request, declaration_id: uuid.UUID) -> Response:
        return Response(reconciliation_report(declaration_id=declaration_id))


def _context() -> Any:
    context = current_context()
    if context is None:
        raise MissingTenantContextError("no tenant context on this request")
    return context


class DateRequiredError(ApiError):
    code = "tax.date_required"
    status = 400


#: `?export=`, because `?format=` belongs to DRF's own content negotiation.
EXPORT_PARAMETER = "export"


def _regime_total_rendered(total: RegimeTotal) -> dict[str, Any]:
    return {
        "vat_regime_code": total.vat_regime_code,
        "vat_rate_key": total.vat_rate_key,
        "vat_rate": str(total.vat_rate),
        "net": str(total.net),
        "vat": str(total.vat),
    }


def _register_row_rendered(row: RegisterRow) -> dict[str, Any]:
    return {
        "document_id": str(row.document_id),
        "document_type": row.document_type,
        "formatted_number": row.formatted_number,
        "document_date": str(row.document_date),
        "accounting_date": str(row.accounting_date),
        "partner_id": None if row.partner_id is None else str(row.partner_id),
        "partner_name": row.partner_name,
        "kind": row.kind,
        "supplier_document_number": row.supplier_document_number,
        "supplier_document_date": (
            None if row.supplier_document_date is None else str(row.supplier_document_date)
        ),
        "deductible": row.deductible,
        "slices": [
            {
                "vat_regime_code": piece.vat_regime_code,
                "vat_rate_key": piece.vat_rate_key,
                "vat_rate": str(piece.vat_rate),
                "net": str(piece.net),
                "vat": str(piece.vat),
            }
            for piece in row.slices
        ],
        "net": str(row.net),
        "vat": str(row.vat),
        "total": str(row.total),
    }


def _register_rendered(register: VatRegister) -> dict[str, Any]:
    return {
        "side": register.side,
        "period": {
            "id": str(register.period_id),
            "start_date": str(register.start_date),
            "end_date": str(register.end_date),
            "kind": register.kind,
        },
        "rows": [_register_row_rendered(row) for row in register.rows],
        "by_regime": [_regime_total_rendered(total) for total in register.by_regime],
        "totals": {
            "net": str(register.total_net),
            "vat": str(register.total_vat),
            "total": str(register.total_amount),
            "non_deductible_vat": str(register.non_deductible_vat),
        },
        "unposted": register.unposted,
    }


class VatRegisterView(APIView):
    """One side's VAT register for the fiscal period covering a day -- ADR-090.

    ``on`` is required: the period is looked up from it, never defaulted to
    today (ADR-044). ``export=csv`` returns the same register as a file, built
    from the same result (`C20`), in the Romanian context (`C38`).
    """

    def get(self, request: Request, company_id: uuid.UUID, side: str) -> HttpResponse:
        raw = request.query_params.get("on")
        if not raw:
            raise DateRequiredError(
                "`on` is required: the register is that of the period covering a day"
            )
        try:
            on = date.fromisoformat(str(raw))
        except ValueError as exc:
            raise DateRequiredError(f"`on` is {raw!r}, not a date") from exc

        register = vat_register(company_id, side=side, on=on)

        if request.query_params.get(EXPORT_PARAMETER) == "csv":
            which = "livrarilor" if side == "sales" else "procurarilor"
            filename = f"registrul-{which}-{register.start_date:%Y-%m}.csv"
            response = HttpResponse(
                vat_register_csv(register), content_type="text/csv; charset=utf-8"
            )
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response
        return Response(_register_rendered(register))
