"""`/api/v1/platform/flags/` -- rings and flags, the console's page (ADR-076 §4.3)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.platform.api.permissions import IsPlatformStaff
from evidenta.platform.flags.services.console import (
    list_flags,
    list_overrides,
    list_ring_assignments,
    list_rings,
)


def _plain(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "hex") and not isinstance(value, bytes | str):
        return str(value)
    return value


def _serialize(row: Any) -> dict[str, Any]:
    return {key: _plain(value) for key, value in asdict(row).items()}


class FlagsView(APIView):
    permission_classes = (IsPlatformStaff,)

    def get(self, request: Request) -> Response:
        return Response(
            {
                "flags": [_serialize(row) for row in list_flags()],
                "rings": [_serialize(row) for row in list_rings()],
                "ring_assignments": [_serialize(row) for row in list_ring_assignments()],
                "overrides": [_serialize(row) for row in list_overrides()],
            }
        )
