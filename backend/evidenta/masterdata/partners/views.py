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
    update_partner,
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
    #: Required whenever a VAT code is sent. The service refuses the pair
    #: otherwise, and the refusal is the point: a start date invented at
    #: data-entry time answers "was this counterparty registered on the day of
    #: the document" with the day somebody typed the card.
    vat_valid_from = serializers.DateField(required=False, allow_null=True)
    short_name = serializers.CharField(required=False, allow_null=True)
    internal_name = serializers.CharField(required=False, allow_null=True)
    default_currency = serializers.CharField(required=False, allow_null=True, max_length=3)
    default_payment_terms_days = serializers.IntegerField(
        required=False, allow_null=True, min_value=0
    )
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
            vat_valid_from=data.get("vat_valid_from"),
            short_name=data.get("short_name"),
            internal_name=data.get("internal_name"),
            default_currency=data.get("default_currency"),
            default_payment_terms_days=data.get("default_payment_terms_days"),
            is_customer=data["is_customer"],
            is_supplier=data["is_supplier"],
        )
        return Response(partner_in_context(partner.id), status=201)


class EditPartnerSerializer(serializers.Serializer[dict[str, Any]]):
    """Shape only, and every field optional: this is a PATCH.

    What may be changed at all is the service's question -- `EDITABLE` there --
    so this does not repeat the list as a second authority. It only refuses
    shapes: a blank currency code, a negative payment term.
    """

    legal_name = serializers.CharField(max_length=255, required=False)
    short_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    internal_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    default_currency = serializers.RegexField(
        r"^[A-Za-z]{3}$", required=False, allow_blank=True, allow_null=True
    )
    default_payment_terms_days = serializers.IntegerField(
        required=False, allow_null=True, min_value=0, max_value=365
    )
    is_customer = serializers.BooleanField(required=False)
    is_supplier = serializers.BooleanField(required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Refuse a field this form does not own, by name.

        DRF drops undeclared keys silently, which is the wrong shape here: a
        caller that sends `idno` believes it is being applied, and the answer
        would be a `200` carrying the old value -- a correction that looked like
        it worked. Measured: without this, the identity test got its request
        through and read back an unchanged partner.
        """
        unknown = set(self.initial_data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError(
                {field: "nu se schimbă din formularul partenerului" for field in sorted(unknown)}
            )
        return attrs


class PartnerDetailView(APIView):
    def get(self, request: Request, partner_id: uuid.UUID) -> Response:
        return Response(partner_in_context(partner_id))

    def patch(self, request: Request, partner_id: uuid.UUID) -> Response:
        """Correct a partner. Identity and VAT are not in it -- see the service."""
        payload = EditPartnerSerializer(data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        return Response(update_partner(partner_id, **payload.validated_data))


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
