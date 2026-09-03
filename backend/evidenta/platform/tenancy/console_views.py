"""The console's page of spaces -- ADR-076 §4.3, first row of the table.

List only. Creating a space from the console is foreseen by ADR-078 §3.1 ("cât e
închisă autoservirea, se creează tenanți prin firmă și prin consolă") and is not
here: the operator command `create_tenant` is the console's channel today, and a
space created without a member has to be claimable (`P-11`, ADR-081), which is
not built. Suspending and archiving are Spec A §9.4 regimes the product does
not serve yet; a button for them would promise a state nothing implements.
"""

from __future__ import annotations

from typing import Any

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.platform.api.permissions import IsPlatformStaff
from evidenta.platform.tenancy.services.console import SpaceRow, list_spaces


def _iso(value: Any) -> str | None:
    return None if value is None else value.isoformat()


def serialize(row: SpaceRow) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "subdomain": row.subdomain,
        "legal_name": row.legal_name,
        "legal_form": row.legal_form,
        "idno": row.idno,
        "status": row.status,
        "claimed_at": _iso(row.claimed_at),
        "suspended_at": _iso(row.suspended_at),
        "offboarding_started_at": _iso(row.offboarding_started_at),
        "archived_at": _iso(row.archived_at),
        "created_at": _iso(row.created_at),
        "company_count": row.company_count,
        "member_count": row.member_count,
    }


class SpacesView(APIView):
    permission_classes = (IsPlatformStaff,)

    def get(self, request: Request) -> Response:
        return Response({"spaces": [serialize(row) for row in list_spaces()]})
