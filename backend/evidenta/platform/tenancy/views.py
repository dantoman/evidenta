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

import uuid
from typing import Any

from django.http import Http404
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.platform.engagement.services.directory import delegations_for_client
from evidenta.platform.identity.services.access import (
    RoleView,
    describe_my_access,
    roles_in_context,
)
from evidenta.platform.tenancy.models import Company, Tenant
from evidenta.platform.tenancy.services.companies import (
    EDITABLE_FIELDS,
    close_company,
    update_company,
)
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
        # Added with the company screen (ADR-083). `status` in particular: until
        # that ADR nothing read it, so nothing showed it either -- and a closed
        # company that looks identical to an open one in the list is how somebody
        # spends ten minutes wondering why a posting is refused.
        "short_name": company.short_name,
        "registered_address": company.registered_address,
        "status": company.status,
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


def _role_rendered(role: RoleView) -> dict[str, Any]:
    return {
        "key": role.key,
        "name": role.name,
        "level": role.level,
        "is_system": role.is_system,
        "permissions": list(role.permissions),
    }


class WorkspaceView(APIView):
    """The workspace itself: who holds the account, and what the caller may do.

    It exists because nothing on any screen said either. The subdomain was the
    only visible thing about the account holder, so *whose* books these are was a
    question the product answered nowhere -- and the rights a person holds were
    readable only in the database.

    **The account holder is a person, not a company** (ADR-085). The workspace is
    assigned to a user; the companies inside it are peers. The common case in
    Moldova is one entrepreneur holding several firms -- more common than a
    corporate holding -- and there is no parent company to point at. What the
    workspace carries of its own is a **billing identity**: who the subscription
    invoice is made out to, which may be a person or a firm and is nobody's
    ledger.

    **The people of the workspace are deliberately absent.** ``membership`` is
    policed self-row (0011), so listing them would return the caller alone and
    look like an answer. `OD-37` is the decision that would make the question
    askable; until then this endpoint answers about the caller.
    """

    def get(self, request: Request) -> Response:
        user_id = request.authenticated_user_id  # type: ignore[attr-defined]
        tenant_id = request.authenticated_tenant_id  # type: ignore[attr-defined]

        # One row each, both readable: `tenant` through `rls.has_tenant_access`,
        # `user` through the self-row policy. Neither needs a filter to be safe;
        # the primary keys come from the context the middlewares established.
        tenant = Tenant.objects.get(pk=tenant_id)
        mine = describe_my_access(user_id=user_id, tenant_id=tenant_id)

        return Response(
            {
                "tenant": {
                    "id": str(tenant.id),
                    "subdomain": tenant.subdomain,
                    "legal_name": tenant.legal_name,
                    # The **subscriber's** fiscal identity, for the subscription
                    # invoice -- not an accounting entity. A workspace is held by
                    # a person (ADR-085), and the person may or may not be a firm.
                    # Nothing is derived from it: no company of this workspace is
                    # singled out as "the holder's", because in the common case
                    # -- one entrepreneur, four companies -- there is no such
                    # company, and picking one would be an invention.
                    "idno": tenant.idno,
                    "legal_form": tenant.legal_form,
                    "status": tenant.status,
                },
                "me": {
                    "user_id": str(user_id),
                    "email": mine.email,
                    "full_name": mine.full_name,
                    "membership_status": mine.membership_status,
                    "role": _role_rendered(mine.role) if mine.role else None,
                    "companies": [
                        {
                            "company_id": str(row.company_id),
                            "role_key": row.role_key,
                            "granted_via": row.granted_via,
                        }
                        for row in mine.companies
                    ],
                },
                "roles": [_role_rendered(role) for role in roles_in_context()],
                "delegated_access": [
                    {
                        "engagement_id": str(row.engagement_id),
                        "firm_name": row.firm_name,
                        "status": row.status,
                        "covers_all_companies": row.covers_all_companies,
                        "valid_from": str(row.valid_from),
                        "valid_to": str(row.valid_to) if row.valid_to else None,
                    }
                    for row in delegations_for_client(tenant_id)
                ],
            }
        )


class UpdateCompanySerializer(serializers.Serializer[dict[str, Any]]):
    """The fields a company card may correct. Every one optional -- this is a PATCH.

    Shape only, again: *whether* the caller may change anything is
    ``update_company``'s question, and which fields are refusable is its list.
    A serializer that also owned the list would be a second copy of the rule.
    """

    legal_name = serializers.CharField(max_length=255, required=False)
    short_name = serializers.CharField(
        max_length=255, required=False, allow_blank=True, allow_null=True
    )
    registered_address = serializers.JSONField(required=False, allow_null=True)
    cuatm_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    caem_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class CloseCompanySerializer(serializers.Serializer[dict[str, Any]]):
    #: Required, and not as ceremony: a company that stopped trading and one
    #: closed by mistake are indistinguishable afterwards without it.
    reason = serializers.CharField(max_length=500)


class CompanyDetailView(APIView):
    """One company: read it, or correct what may be corrected -- ADR-083.

    No filtering here either. The policy answers "may this caller see it"; the
    permission answers "may this caller change it", and the two are different
    questions with different answers -- a firm's user may hold access to a
    company and no key over it.
    """

    def get(self, request: Request, company_id: uuid.UUID) -> Response:
        company = Company.objects.filter(id=company_id).first()
        if company is None:
            # Absent, never forbidden: distinguishing them would confirm that an
            # id exists in a tenant this caller cannot see (IZ-04).
            raise Http404
        return Response(_rendered(company))

    def patch(self, request: Request, company_id: uuid.UUID) -> Response:
        payload = UpdateCompanySerializer(data=request.data, partial=True)
        payload.is_valid(raise_exception=True)

        # Keys the serializer dropped are passed on rather than ignored, so the
        # service can refuse them by name. Silently discarding `idno` would let a
        # screen believe it had changed something it had not.
        submitted: dict[str, Any] = request.data if isinstance(request.data, dict) else {}
        unknown = {key: value for key, value in submitted.items() if key not in EDITABLE_FIELDS}
        company = update_company(company_id, **unknown, **dict(payload.validated_data))
        return Response(_rendered(company))


class CompanyCloseView(APIView):
    """Stop a company receiving postings. Its own route, and its own key.

    A `POST` to a named sub-resource rather than a `PATCH` of `status`: closing
    is a decision with a reason, not a field that happens to change value.
    """

    def post(self, request: Request, company_id: uuid.UUID) -> Response:
        payload = CloseCompanySerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        company = close_company(company_id, reason=str(payload.validated_data["reason"]))
        return Response(_rendered(company))
