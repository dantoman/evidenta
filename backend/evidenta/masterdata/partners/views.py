"""The partner directory over HTTP.

The tenant is never in the path (`C8`): it is the host the browser is already on,
and a partner belongs to the tenant rather than to a company -- the same legal
entity is the same entity for every company of a firm.

The search exists because of a defect the opening-balances screen ran into: a
form that asks a person for a `partner_id` is a form nobody can fill in
correctly. What a person has in front of them is a name and an IDNO, so those are
what the query matches.
"""

from __future__ import annotations

import uuid
from typing import Any

from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.masterdata.partners.models import PartnerKind
from evidenta.masterdata.partners.services.directory import (
    create_partner,
    partner_in_context,
    partners_of,
    set_partner_active,
)
from evidenta.platform.rls.context import MissingTenantContextError, current_context


class PartnerSerializer(serializers.Serializer[dict[str, Any]]):
    """What a partner is on the way in.

    `legal_name` is required and `short_name` is not, and the asymmetry is the
    rule: the legal name is what documents and registers carry (`C39`), while the
    short one exists for the interface and never reaches a printed document.
    """

    legal_name = serializers.CharField()
    kind = serializers.ChoiceField(choices=PartnerKind.values, default=PartnerKind.LEGAL_ENTITY)
    idno = serializers.CharField(required=False, allow_null=True)
    idnp = serializers.CharField(required=False, allow_null=True)
    vat_code = serializers.CharField(required=False, allow_null=True)
    short_name = serializers.CharField(required=False, allow_null=True)
    is_customer = serializers.BooleanField(default=False)
    is_supplier = serializers.BooleanField(default=False)


class ActivationSerializer(serializers.Serializer[dict[str, Any]]):
    active = serializers.BooleanField()


class PartnerListView(APIView):
    def get(self, request: Request) -> Response:
        context = _context()
        return Response(
            partners_of(
                context.tenant_id,
                query=request.query_params.get("q"),
                role=request.query_params.get("role"),
                include_inactive=request.query_params.get("include_inactive") == "true",
            )
        )

    def post(self, request: Request) -> Response:
        context = _context()
        payload = PartnerSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)

        partner = create_partner(
            tenant_id=context.tenant_id,
            legal_name=data["legal_name"],
            kind=data["kind"],
            idno=data.get("idno"),
            idnp=data.get("idnp"),
            vat_code=data.get("vat_code"),
            short_name=data.get("short_name"),
            is_customer=data["is_customer"],
            is_supplier=data["is_supplier"],
        )
        return Response(partner_in_context(partner.id), status=201)


class PartnerDetailView(APIView):
    def get(self, request: Request, partner_id: uuid.UUID) -> Response:
        return Response(partner_in_context(partner_id))


class PartnerActivationView(APIView):
    """Retire a partner, or bring one back. Never delete.

    Entries posted against it still name it, and a deleted partner would leave
    them pointing at nothing.
    """

    def post(self, request: Request, partner_id: uuid.UUID) -> Response:
        payload = ActivationSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        return Response(set_partner_active(partner_id, active=payload.validated_data["active"]))


def _context() -> Any:
    context = current_context()
    if context is None:  # pragma: no cover -- the middleware refuses first
        raise MissingTenantContextError("the partner directory needs a tenant context")
    return context
