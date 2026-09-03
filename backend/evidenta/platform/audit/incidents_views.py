"""`/api/v1/platform/incidents/` -- the platform's own state, measured now (ADR-076 §4.3)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.platform.api.permissions import IsPlatformStaff
from evidenta.platform.audit.services import incidents


def _plain(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


class IncidentsView(APIView):
    permission_classes = (IsPlatformStaff,)

    def get(self, request: Request) -> Response:
        return Response(
            {
                "database": asdict(incidents.database()),
                "broker": asdict(incidents.broker()),
                "workers": asdict(incidents.workers()),
                "queues": [asdict(q) for q in incidents.queues()],
                "paths": [
                    {k: _plain(v) for k, v in asdict(p).items()} for p in incidents.last_runs()
                ],
            }
        )
