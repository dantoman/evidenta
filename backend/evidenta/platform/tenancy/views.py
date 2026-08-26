"""The companies this context can reach -- the list every company-scoped screen
needs before it can ask for anything else.

**No filtering here.** `Company.objects.all()` returns exactly the companies the
caller may see, because the policy on the table says so: tenant in context, tenant
access, company access. Adding a `.filter()` would create the impression of safety
and mask the absence of context (C3), which is the failure the invariant exists to
prevent.

Read-only, deliberately. Creating a company is `P-9`
([ADR-040](../../../../docs/decisions/040-crearea-tenantului-si-a-companiei.md)) --
a privileged path, decided and unwritten -- and an endpoint that could create one
here would be the shortcut around it.
"""

from __future__ import annotations

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.platform.tenancy.models import Company


class CompanyListView(APIView):
    """Every company the caller may reach, in a stable order.

    Ordered by legal name rather than by creation: a list that reorders itself
    when somebody adds a company is a list whose second entry means something
    different tomorrow.
    """

    def get(self, request: Request) -> Response:
        rows = Company.objects.all().order_by("legal_name", "idno")
        return Response(
            [
                {
                    "id": str(company.id),
                    "legal_name": company.legal_name,
                    "idno": company.idno,
                    "functional_currency": company.functional_currency,
                }
                for company in rows
            ]
        )
