"""The console's page of support grants -- list for every employee, request for `support`.

`POST` is `P-7` (ADR-077 §5): the function checks the caller's role, the space,
the ticket and the justification in SQL, and writes the log row itself. The view
resolves the space from its subdomain and translates the function's refusals into
codes. Whole-space requests only: a support employee on the console cannot list
a client's companies -- that is the point of the console -- so a company-scoped
grant is not something it can ask for by name.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.platform.api.errors import ApiError
from evidenta.platform.api.permissions import IsPlatformStaff, IsPlatformSupport
from evidenta.platform.support.services import console


class RequestApiError(ApiError):
    def __init__(self, error: console.RequestRefusedError) -> None:
        self.code = error.code
        self.status = error.status
        super().__init__(str(error))


class RequestInput(serializers.Serializer[dict[str, Any]]):
    space = serializers.CharField()
    request_ref = serializers.CharField()
    justification = serializers.CharField()

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        unknown = set(self.initial_data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({name: "câmp necunoscut" for name in sorted(unknown)})
        return attrs


def _iso(value: Any) -> str | None:
    return None if value is None else value.isoformat()


def serialize(row: console.ConsoleGrantRow) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "subdomain": row.subdomain,
        "legal_name": row.legal_name,
        "company_id": str(row.company_id) if row.company_id else None,
        "requested_by_email": row.requested_by_email,
        "request_ref": row.request_ref,
        "justification": row.justification,
        "requested_at": _iso(row.requested_at),
        "approved_at": _iso(row.approved_at),
        "expires_at": _iso(row.expires_at),
        "revoked_at": _iso(row.revoked_at),
        "status": row.status,
    }


class ConsoleGrantsView(APIView):
    def get_permissions(self) -> list[BasePermission]:
        if self.request.method == "POST":
            return [IsPlatformSupport()]
        return [IsPlatformStaff()]

    def get(self, request: Request) -> Response:
        return Response({"grants": [serialize(row) for row in console.list_grants()]})

    def post(self, request: Request) -> Response:
        data = RequestInput(data=request.data)
        data.is_valid(raise_exception=True)
        valid = data.validated_data
        try:
            grant_id = console.request_grant(
                subdomain=str(valid["space"]),
                company_id=None,
                request_ref=str(valid["request_ref"]),
                justification=str(valid["justification"]),
            )
        except console.RequestRefusedError as refusal:
            raise RequestApiError(refusal) from refusal
        return Response({"grant_id": str(grant_id)}, status=201)
