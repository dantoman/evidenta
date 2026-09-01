"""Supplier invoices over HTTP -- open a draft, price it, record it.

The mirror of the sales views, with the two differences the domain has:

**The supplier's number and date are required on the way in.** They are not
allocated and they are not ours; without them the same invoice arriving twice --
typed once and imported once -- cannot be recognised as one document (`R20`).

**Two discriminators, not one.** Where the cost lands selects the expense account
and whether the supplier is a resident selects the payable. Neither is derivable
from anything this system holds, so both are required by the serializer rather
than defaulted (ADR-073 §2).

**`Idempotency-Key` is not read here** (`C9`), for the reason the sales views give:
the key that matters is on the accounting event, keyed by the document (`R19`).
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.operations.purchases.models import CostDestination, PurchaseDocument
from evidenta.operations.purchases.services.documents import open_purchase
from evidenta.operations.purchases.services.lines import service_line
from evidenta.operations.purchases.services.recording import record_and_post
from evidenta.platform.capabilities.services.profile import active_profile
from evidenta.platform.documents.services.lifecycle import get_document
from evidenta.platform.documents.services.lines import (
    DocumentTotals,
    replace_lines,
    totals_of,
    totals_of_many,
)
from evidenta.platform.rls.context import MissingTenantContextError, current_context


class LineSerializer(serializers.Serializer[dict[str, Any]]):
    description = serializers.CharField()
    quantity = serializers.DecimalField(max_digits=20, decimal_places=6)
    unit_price = serializers.DecimalField(max_digits=20, decimal_places=4)


class PurchaseSerializer(serializers.Serializer[dict[str, Any]]):
    partner_id = serializers.UUIDField()
    document_date = serializers.DateField()
    accounting_date = serializers.DateField(required=False, allow_null=True)
    #: Theirs, as written on the paper. Required, and never allocated by us.
    supplier_document_number = serializers.CharField(max_length=100)
    supplier_document_date = serializers.DateField()
    #: No default on either: each selects an account, and neither is derivable.
    cost_destination = serializers.ChoiceField(choices=CostDestination.values)
    partner_resident = serializers.BooleanField()
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    lines = LineSerializer(many=True)


class LinesSerializer(serializers.Serializer[dict[str, Any]]):
    lines = LineSerializer(many=True)


class PurchaseListView(APIView):
    def get(self, request: Request, company_id: uuid.UUID) -> Response:
        rows = list(
            PurchaseDocument.objects.filter(company_id=company_id)
            .select_related("document")
            .order_by("-supplier_document_date", "-document__created_at")
        )
        # The register shows each invoice's total, and the screen adds nothing
        # up (`C19`): the figure travels with the row, summed once for the list.
        totals = totals_of_many(row.document_id for row in rows)
        return Response([_rendered(row, totals[row.document_id]) for row in rows])

    def post(self, request: Request, company_id: uuid.UUID) -> Response:
        payload = PurchaseSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)

        document_id = open_purchase(
            company_id=company_id,
            partner_id=data["partner_id"],
            document_date=data["document_date"],
            accounting_date=data.get("accounting_date"),
            supplier_document_number=data["supplier_document_number"],
            supplier_document_date=data["supplier_document_date"],
            cost_destination=data["cost_destination"],
            partner_resident=data["partner_resident"],
            notes=data.get("notes") or None,
        )
        _write_lines(document_id, data["lines"], data["document_date"])
        return Response(_detail(document_id), status=201)


class PurchaseDetailView(APIView):
    def get(self, request: Request, document_id: uuid.UUID) -> Response:
        return Response(_detail(document_id))


class PurchaseLinesView(APIView):
    def put(self, request: Request, document_id: uuid.UUID) -> Response:
        payload = LinesSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        document = get_document(document_id)
        _write_lines(document_id, list(payload.validated_data["lines"]), document.document_date)
        return Response(_detail(document_id))


class PurchaseRecordingView(APIView):
    """Validate and post, in that order, in one call."""

    def post(self, request: Request, document_id: uuid.UUID) -> Response:
        context = _context()
        document = get_document(document_id)
        result = record_and_post(
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


def _write_lines(document_id: uuid.UUID, lines: list[dict[str, Any]], on: Any) -> None:
    replace_lines(
        document_id,
        [
            service_line(
                description=line["description"],
                quantity=Decimal(line["quantity"]),
                unit_price=Decimal(line["unit_price"]),
                on=on,
            )
            for line in lines
        ],
    )


def _detail(document_id: uuid.UUID) -> dict[str, Any]:
    row = (
        PurchaseDocument.objects.filter(document_id=document_id).select_related("document").first()
    )
    if row is None:
        raise MissingTenantContextError("no such purchase in this context")
    return _rendered(row, totals_of(document_id))


def _rendered(row: PurchaseDocument, totals: DocumentTotals) -> dict[str, Any]:
    document = row.document
    return {
        "id": str(document.id),
        # Ours, allocated at validation. Distinct from the supplier's, and both
        # appear: a register that showed only one of them cannot be cross-checked
        # against either the supplier's copy or our own numbering.
        "formatted_number": document.formatted_number,
        "supplier_document_number": row.supplier_document_number,
        "supplier_document_date": str(row.supplier_document_date),
        "document_date": str(document.document_date),
        "accounting_date": str(document.accounting_date),
        "state": document.state,
        "partner_id": str(document.partner_id) if document.partner_id else None,
        "currency": document.currency,
        "cost_destination": row.cost_destination,
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
