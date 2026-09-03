"""`/api/v1/platform/privileged-log/` -- the console's audit page (ADR-076 §4.3)."""

from __future__ import annotations

from typing import Any

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.platform.api.errors import ApiError
from evidenta.platform.api.permissions import IsPlatformStaff
from evidenta.platform.audit.models import PrivilegedPath
from evidenta.platform.audit.services.console import LogRow, path_catalogue, privileged_log


class LogFilterInvalidError(ApiError):
    code = "audit.filter_invalid"
    status = 400


def serialize(row: LogRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "occurred_at": row.occurred_at.isoformat(),
        "path_code": row.path_code,
        "actor": row.actor,
        "actor_user_id": str(row.actor_user_id) if row.actor_user_id else None,
        "actor_email": row.actor_email,
        "subject_tenant_id": str(row.subject_tenant_id) if row.subject_tenant_id else None,
        "subject_subdomain": row.subject_subdomain,
        "tenant_count": row.tenant_count,
        "request_id": row.request_id,
        "justification": row.justification,
        "payload": row.payload,
    }


class PrivilegedLogView(APIView):
    permission_classes = (IsPlatformStaff,)

    def get(self, request: Request) -> Response:
        path_code = request.query_params.get("path") or None
        if path_code is not None and path_code not in PrivilegedPath.values:
            raise LogFilterInvalidError(f"{path_code!r} is not a privileged path code")
        raw_limit = request.query_params.get("limit") or "100"
        try:
            limit = int(raw_limit)
        except ValueError as exc:
            raise LogFilterInvalidError(f"limit {raw_limit!r} is not a number") from exc
        rows = privileged_log(
            path_code=path_code,
            subdomain=request.query_params.get("space") or None,
            limit=limit,
        )
        return Response({"paths": path_catalogue(), "rows": [serialize(row) for row in rows]})
