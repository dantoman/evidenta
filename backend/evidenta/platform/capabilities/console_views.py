"""`/api/v1/platform/capabilities/` -- the console's capability page (ADR-076 §4.3)."""

from __future__ import annotations

from typing import Any

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.platform.api.permissions import IsPlatformStaff
from evidenta.platform.capabilities.services.console import ActivationRow, list_activations


def serialize(row: ActivationRow) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "subdomain": row.subdomain,
        "legal_name": row.legal_name,
        "company_id": str(row.company_id) if row.company_id else None,
        "company_legal_name": row.company_legal_name,
        "company_idno": row.company_idno,
        "capability_key": row.capability_key,
        "effective_from": row.effective_from.isoformat(),
        "effective_to": row.effective_to.isoformat() if row.effective_to else None,
        "initialisation_state": row.initialisation_state,
        "source": row.source,
        "activated_at": row.activated_at.isoformat(),
    }


class CapabilitiesView(APIView):
    permission_classes = (IsPlatformStaff,)

    def get(self, request: Request) -> Response:
        return Response({"activations": [serialize(row) for row in list_activations()]})
