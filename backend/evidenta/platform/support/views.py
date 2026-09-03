"""The client's endpoints for support grants -- `/api/v1/support/` (ADR-077 §5-§6).

Served on the client's host, inside their context, through the ordinary policy.
Approving and revoking need `tenant.approve_support_access`; reading the list
needs only membership. The support session itself may read `session` to say, in
the context bar, on which ticket it runs and until when -- and nothing else here,
because a support session is read-only before any view runs.
"""

from __future__ import annotations

import uuid
from typing import Any

from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.platform.api.errors import ApiError
from evidenta.platform.identity.services.roles import RoleError
from evidenta.platform.support.models import SupportGrant
from evidenta.platform.support.services import grants


class SupportApiError(ApiError):
    def __init__(self, error: grants.SupportGrantError) -> None:
        self.code = error.code
        self.status = error.status
        super().__init__(str(error))


class PermissionRequiredError(ApiError):
    code = "api.forbidden"
    status = 403


class ApproveInput(serializers.Serializer[dict[str, Any]]):
    hours = serializers.IntegerField(required=False, min_value=1, max_value=72)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        unknown = set(self.initial_data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({name: "câmp necunoscut" for name in sorted(unknown)})
        return attrs


def _iso(value: Any) -> str | None:
    return None if value is None else value.isoformat()


def serialize(grant: SupportGrant) -> dict[str, Any]:
    return {
        "id": str(grant.id),
        "company_id": str(grant.company_id) if grant.company_id else None,
        "request_ref": grant.request_ref,
        "justification": grant.justification,
        "requested_at": _iso(grant.requested_at),
        "approved_at": _iso(grant.approved_at),
        "expires_at": _iso(grant.expires_at),
        "revoked_at": _iso(grant.revoked_at),
        "status": grants.status_of(grant),
    }


def _guard(action: Any) -> Any:
    try:
        return action()
    except RoleError as refusal:
        # Only a denied permission is the caller's 403; `PERMISSION_CHECK_NOT_SELF`
        # is a programming error and stays loud (as `tenancy` treats it).
        if getattr(refusal, "code", None) == "PERMISSION_DENIED":
            raise PermissionRequiredError(str(refusal)) from refusal
        raise
    except grants.SupportGrantError as refusal:
        raise SupportApiError(refusal) from refusal


class GrantsView(APIView):
    def get(self, request: Request) -> Response:
        return Response({"grants": [serialize(g) for g in _guard(grants.list_grants)]})


class ApproveView(APIView):
    def post(self, request: Request, grant_id: uuid.UUID) -> Response:
        data = ApproveInput(data=request.data)
        data.is_valid(raise_exception=True)
        hours = data.validated_data.get("hours")
        grant = _guard(lambda: grants.approve(grant_id, hours=hours))
        return Response({"grant": serialize(grant)})


class RevokeView(APIView):
    def post(self, request: Request, grant_id: uuid.UUID) -> Response:
        grant = _guard(lambda: grants.revoke(grant_id))
        return Response({"grant": serialize(grant)})


class SessionView(APIView):
    """What a support session runs on -- for the bar that says so (ADR-077 §6)."""

    def get(self, request: Request) -> Response:
        grant = grants.session_grant()
        if grant is None:
            return Response({"grant": None})
        return Response({"grant": serialize(grant)})
