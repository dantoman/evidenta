"""The companies this context can reach -- the list every company-scoped screen
needs before it can ask for anything else.

**No filtering here.** `Company.objects.all()` returns exactly the companies the
caller may see, because the policy on the table says so: tenant in context, tenant
access, company access. Adding a `.filter()` would create the impression of safety
and mask the absence of context (C3), which is the failure the invariant exists to
prevent.

Creating one is `P-9`
([ADR-040](../../../../docs/decisions/040-crearea-tenantului-si-a-companiei.md)),
now written: `POST` goes through `rls.provision_company` and nowhere else. The
endpoint is not the shortcut around the privileged path, it is its only caller.

**No fiscal year is opened here.** Opening an exercise is `accounting`, and
`platform` does not import it (DG). The client creates the company, then opens
the exercise -- two calls, both explicit, rather than one endpoint that quietly
reaches across the module graph.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.platform.tenancy.models import Company
from evidenta.platform.tenancy.services.provisioning import provision_company


def _rendered(company: Company) -> dict[str, Any]:
    return {
        "id": str(company.id),
        "legal_name": company.legal_name,
        "idno": company.idno,
        "functional_currency": company.functional_currency,
        "accounting_start_date": str(company.accounting_start_date),
        # Nullable on the way out too: a screen that showed an empty string could
        # not tell "no classifier code recorded" from "recorded as blank".
        "cuatm_code": company.cuatm_code,
        "caem_code": company.caem_code,
    }


class CreateCompanySerializer(serializers.Serializer[dict[str, Any]]):
    """Shape only. Whether the caller may create anything is the function's
    question, and answering it here would mean answering it twice."""

    # IDNO is thirteen digits in Moldova. Validated as a shape, not as a
    # checksum: the checksum rule is not in a text this repository has, and a
    # made-up one would refuse real companies.
    idno = serializers.RegexField(r"^\d{13}$")
    legal_name = serializers.CharField(max_length=255)
    functional_currency = serializers.RegexField(r"^[A-Z]{3}$", default="MDL")
    accounting_start_date = serializers.DateField(required=False)
    #: The two codes a statutory return's header carries. Optional, because
    #: neither classifier is in this repository -- a company recorded without them
    #: is ordinary, and a return generated meanwhile says which one is missing.
    cuatm_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    caem_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class CompanyListView(APIView):
    """Every company the caller may reach, in a stable order.

    Ordered by legal name rather than by creation: a list that reorders itself
    when somebody adds a company is a list whose second entry means something
    different tomorrow.
    """

    def get(self, request: Request) -> Response:
        rows = Company.objects.all().order_by("legal_name", "idno")
        return Response([_rendered(company) for company in rows])

    def post(self, request: Request) -> Response:
        """Create one company -- `P-9`."""
        payload = CreateCompanySerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)

        company = provision_company(
            idno=data["idno"],
            legal_name=data["legal_name"],
            functional_currency=data["functional_currency"],
            accounting_start=data.get("accounting_start_date"),
            cuatm_code=data.get("cuatm_code"),
            caem_code=data.get("caem_code"),
        )
        return Response(_rendered(company), status=201)
