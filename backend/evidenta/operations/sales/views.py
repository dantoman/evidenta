"""Sales invoices over HTTP -- open a draft, price it, issue it.

**Issuing is one call**, and that is the design rather than a shortcut: validating
without posting leaves a numbered document with no accounting effect, and two
calls that must happen in order are two chances to make only the first. The
service does both in the order the acts impose.

**`Idempotency-Key` is not read here** (`C9`) and the reason is worth stating: the
key that matters is on the accounting event, keyed by the document (`R19`,
ADR-073 §8). A second issue of the same invoice returns the first result, which
is what the header would have bought -- so a header would be a second mechanism
for a property the event already has.

**The two discriminators are required by the serializer**, not defaulted. What is
sold and whether the counterparty is a resident each select an account, and
neither can be derived from anything this system holds.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.operations.sales.models import RevenueKind, SaleNature, SalesDocument
from evidenta.operations.sales.services.documents import open_sale
from evidenta.operations.sales.services.issuing import issue_and_post
from evidenta.operations.sales.services.lines import Position, write_lines
from evidenta.platform.capabilities.services.profile import active_profile
from evidenta.platform.documents.services.lifecycle import get_document
from evidenta.platform.documents.services.lines import (
    DocumentTotals,
    totals_of,
    totals_of_many,
)
from evidenta.platform.rls.context import MissingTenantContextError, current_context


class LineSerializer(serializers.Serializer[dict[str, Any]]):
    description = serializers.CharField()
    quantity = serializers.DecimalField(max_digits=20, decimal_places=6)
    unit_price = serializers.DecimalField(max_digits=20, decimal_places=4)
    #: Stated on every line, never defaulted (ADR-089): a line issued under a
    #: treatment nobody chose is a VAT amount nobody chose. The service decides
    #: whether the company may state it on the document's date.
    vat_regime_code = serializers.CharField(max_length=64)


class SaleSerializer(serializers.Serializer[dict[str, Any]]):
    partner_id = serializers.UUIDField()
    document_date = serializers.DateField()
    accounting_date = serializers.DateField(required=False, allow_null=True)
    #: Required over the wire although the service defaults it, and the asymmetry
    #: is deliberate: forgetting the field would make a credit note an invoice,
    #: which recognises revenue instead of a return. The service's default serves
    #: callers inside the process, which state the nature by choosing the function
    #: they call; an HTTP body states it or is refused (ADR-073 §7).
    nature = serializers.ChoiceField(choices=SaleNature.values)
    #: No default on either: both select an account, and neither is derivable.
    revenue_kind = serializers.ChoiceField(choices=RevenueKind.values)
    partner_resident = serializers.BooleanField()
    external_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    lines = LineSerializer(many=True)


class LinesSerializer(serializers.Serializer[dict[str, Any]]):
    lines = LineSerializer(many=True)


class SalesListView(APIView):
    def get(self, request: Request, company_id: uuid.UUID) -> Response:
        rows = list(
            SalesDocument.objects.filter(company_id=company_id)
            .select_related("document")
            .order_by("-document__document_date", "-document__created_at")
        )
        # The register shows each invoice's total, and the screen adds nothing
        # up (`C19`): the figure travels with the row, summed once for the list.
        totals = totals_of_many(row.document_id for row in rows)
        return Response([_rendered(row, totals[row.document_id]) for row in rows])

    def post(self, request: Request, company_id: uuid.UUID) -> Response:
        payload = SaleSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)

        document_id = open_sale(
            company_id=company_id,
            partner_id=data["partner_id"],
            document_date=data["document_date"],
            accounting_date=data.get("accounting_date"),
            nature=data["nature"],
            revenue_kind=data["revenue_kind"],
            partner_resident=data["partner_resident"],
            external_number=data.get("external_number") or None,
            notes=data.get("notes") or None,
        )
        _write_lines(document_id, data["lines"])
        return Response(_detail(document_id), status=201)


class SalesDetailView(APIView):
    def get(self, request: Request, document_id: uuid.UUID) -> Response:
        return Response(_detail(document_id))


class SalesLinesView(APIView):
    def put(self, request: Request, document_id: uuid.UUID) -> Response:
        payload = LinesSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        _write_lines(document_id, list(payload.validated_data["lines"]))
        return Response(_detail(document_id))


class SalesIssuanceView(APIView):
    """Validate and post, in that order, in one call."""

    def post(self, request: Request, document_id: uuid.UUID) -> Response:
        context = _context()
        document = get_document(document_id)
        result = issue_and_post(
            document_id=document_id,
            actor_user_id=context.user_id,
            request_id=context.request_id,
            capability_snapshot=active_profile(
                document.company_id, document.accounting_date
            ).as_snapshot(),
        )
        payload = _detail(document_id)
        payload["posting"] = {
            "accounting_event_id": str(result.accounting_event_id),
            "journal_entry_id": (str(result.journal_entry_id) if result.journal_entry_id else None),
            "posted_now": result.posted_now,
        }
        return Response(payload)


def _write_lines(document_id: uuid.UUID, lines: list[dict[str, Any]]) -> None:
    write_lines(
        document_id,
        [
            Position(
                description=line["description"],
                quantity=Decimal(line["quantity"]),
                unit_price=Decimal(line["unit_price"]),
                vat_regime_code=line["vat_regime_code"],
            )
            for line in lines
        ],
    )


def _detail(document_id: uuid.UUID) -> dict[str, Any]:
    row = SalesDocument.objects.filter(document_id=document_id).select_related("document").first()
    if row is None:
        raise MissingTenantContextError("no such sale in this context")
    return _rendered(row, totals_of(document_id))


def _rendered(row: SalesDocument, totals: DocumentTotals) -> dict[str, Any]:
    document = row.document
    return {
        "id": str(document.id),
        "formatted_number": document.formatted_number,
        "document_date": str(document.document_date),
        "accounting_date": str(document.accounting_date),
        "state": document.state,
        "partner_id": str(document.partner_id) if document.partner_id else None,
        "currency": document.currency,
        "nature": row.nature,
        "revenue_kind": row.revenue_kind,
        "partner_resident": row.partner_resident,
        "totals": {
            "net": str(totals.net),
            "vat": str(totals.vat),
            "total": str(totals.total),
        },
    }


def _context() -> Any:
    context = current_context()
    if context is None:
        raise MissingTenantContextError("no tenant context on this request")
    return context
