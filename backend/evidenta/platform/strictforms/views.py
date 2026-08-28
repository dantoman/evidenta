"""The register over HTTP -- recording ranges, and accounting for blanks.

**There is no endpoint that hands out a number.** That is the design, not an
omission: a number is taken at posting, inside the document's transaction, under
the allocation's lock. An endpoint that issued one on request would be exactly
the defect the register exists to prevent -- a number spent on a draft somebody
abandoned, and a gap the entity then has to explain to an inspection.

What the endpoints do is what a person does: record a range that arrived from the
tax service, account for a blank that was spoiled, and read how many are left.
"""

from __future__ import annotations

import uuid
from typing import Any

from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.platform.rls.context import MissingTenantContextError, current_context
from evidenta.platform.strictforms.models import (
    FormNumberState,
    StrictFormAllocation,
    StrictFormNumber,
)
from evidenta.platform.strictforms.services.register import (
    VOID_STATES,
    record_allocation,
    remaining,
    void_number,
)
from evidenta.platform.tenancy.services.companies import functional_currency


class AllocationSerializer(serializers.Serializer[dict[str, Any]]):
    """A range as the order describes it.

    Every field is copied off a document the entity received. None of it is
    chosen: the series, the range and the reference all come from the tax
    service, and the form here is a transcription, not a decision.
    """

    form_type_code = serializers.CharField()
    series = serializers.CharField()
    first_number = serializers.IntegerField(min_value=1)
    last_number = serializers.IntegerField(min_value=1)
    issued_on = serializers.DateField()
    source_reference = serializers.CharField()
    responsible_user_id = serializers.UUIDField()
    note = serializers.CharField(required=False, allow_null=True)


class VoidSerializer(serializers.Serializer[dict[str, Any]]):
    form_type_code = serializers.CharField()
    state = serializers.ChoiceField(choices=sorted(VOID_STATES))
    note = serializers.CharField()


class AllocationListView(APIView):
    def get(self, request: Request, company_id: uuid.UUID) -> Response:
        functional_currency(company_id)
        rows = StrictFormAllocation.objects.filter(company_id=company_id).order_by(
            "form_type_code", "issued_on", "first_number"
        )
        return Response([_allocation(row) for row in rows])

    def post(self, request: Request, company_id: uuid.UUID) -> Response:
        context = _context()
        payload = AllocationSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)

        functional_currency(company_id)
        allocation = record_allocation(
            tenant_id=context.tenant_id,
            company_id=company_id,
            form_type_code=data["form_type_code"],
            series=data["series"],
            first_number=data["first_number"],
            last_number=data["last_number"],
            issued_on=data["issued_on"],
            source_reference=data["source_reference"],
            responsible_user_id=data["responsible_user_id"],
            note=data.get("note"),
        )
        return Response(_allocation(allocation), status=201)


class AllocationDetailView(APIView):
    """One range, with what has left it.

    The counts are the register's own arithmetic: issued equals consumed plus
    voided plus remaining. Shown together because that identity is what somebody
    checks, and computing two of the three on a screen invites the third to
    disagree.
    """

    def get(self, request: Request, company_id: uuid.UUID, allocation_id: uuid.UUID) -> Response:
        functional_currency(company_id)
        allocation = StrictFormAllocation.objects.filter(
            id=allocation_id, company_id=company_id
        ).first()
        if allocation is None:
            return Response({"code": "strictforms.no_allocation"}, status=404)

        counts = {state: 0 for state in FormNumberState.values}
        for row in StrictFormNumber.objects.filter(allocation_id=allocation.id):
            counts[str(row.state)] += 1

        return Response({**_allocation(allocation), "counts": counts})


class WithdrawalView(APIView):
    """Stop consuming from a range. Never delete it.

    The numbers already taken from it name it, and a deleted allocation would
    leave them with no series to belong to.
    """

    def post(self, request: Request, company_id: uuid.UUID, allocation_id: uuid.UUID) -> Response:
        functional_currency(company_id)
        allocation = StrictFormAllocation.objects.filter(
            id=allocation_id, company_id=company_id
        ).first()
        if allocation is None:
            return Response({"code": "strictforms.no_allocation"}, status=404)
        allocation.is_active = False
        allocation.save(update_fields=["is_active", "updated_at"])
        return Response(_allocation(allocation))


class VoidView(APIView):
    """Account for a blank that will never carry a document."""

    def post(self, request: Request, company_id: uuid.UUID) -> Response:
        context = _context()
        payload = VoidSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)

        functional_currency(company_id)
        issued = void_number(
            company_id=company_id,
            form_type_code=data["form_type_code"],
            state=data["state"],
            actor_user_id=context.user_id,
            note=data["note"],
        )
        return Response(
            {
                "allocation_id": str(issued.allocation_id),
                "series": issued.series,
                "number": issued.number,
                "formatted": issued.formatted,
                "state": data["state"],
                "remaining": remaining(company_id, data["form_type_code"]),
            },
            status=201,
        )


def _allocation(allocation: StrictFormAllocation) -> dict[str, Any]:
    return {
        "id": str(allocation.id),
        "company_id": str(allocation.company_id),
        "form_type_code": allocation.form_type_code,
        "series": allocation.series,
        "first_number": allocation.first_number,
        "last_number": allocation.last_number,
        "next_number": allocation.next_number,
        "remaining": max(0, allocation.last_number - allocation.next_number + 1),
        "issued_on": allocation.issued_on.isoformat(),
        "source_reference": allocation.source_reference,
        "responsible_user_id": str(allocation.responsible_user_id),
        "is_active": allocation.is_active,
        "note": allocation.note,
    }


def _context() -> Any:
    context = current_context()
    if context is None:  # pragma: no cover -- the middleware refuses first
        raise MissingTenantContextError("the strict-form register needs a tenant context")
    return context
