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
from typing import Any

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
