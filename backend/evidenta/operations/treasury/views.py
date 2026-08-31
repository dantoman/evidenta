"""Money in and out over HTTP -- open a movement, record it.

**One collection for both directions**, with the direction in the payload: the
person looking at a company's money wants one list, in date order, not two lists
they have to interleave mentally. The two document types stay two -- they number
separately, as they should -- and the direction is what picks between them.

**No lines endpoint.** These documents carry no positions; the amount is a field
on the movement, and a `PUT .../lines` would be a route that could only ever
answer 404.

**`Idempotency-Key` is not read here** (`C9`): the key is on the accounting event,
keyed by the document (`R19`).
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.operations.treasury.models import Direction, TreasuryAccount, TreasuryDocument
from evidenta.operations.treasury.services.documents import open_payment, open_receipt
from evidenta.operations.treasury.services.recording import record_and_post
from evidenta.platform.capabilities.services.profile import active_profile
from evidenta.platform.documents.services.lifecycle import get_document
from evidenta.platform.rls.context import MissingTenantContextError, current_context


class MovementSerializer(serializers.Serializer[dict[str, Any]]):
    direction = serializers.ChoiceField(choices=Direction.values)
    partner_id = serializers.UUIDField()
    document_date = serializers.DateField()
    accounting_date = serializers.DateField(required=False, allow_null=True)
    amount = serializers.DecimalField(max_digits=20, decimal_places=2)
    #: No default: the treasury account is the instrument's, and nothing on the
    #: document knows whether the money went into the till or the bank.
    treasury_account = serializers.ChoiceField(choices=TreasuryAccount.values)
    partner_resident = serializers.BooleanField()
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class TreasuryListView(APIView):
    def get(self, request: Request, company_id: uuid.UUID) -> Response:
        rows = (
            TreasuryDocument.objects.filter(company_id=company_id)
            .select_related("document")
            .order_by("-document__document_date", "-document__created_at")
        )
        return Response([_rendered(row) for row in rows])

    def post(self, request: Request, company_id: uuid.UUID) -> Response:
        payload = MovementSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)

        opener = open_receipt if data["direction"] == Direction.RECEIPT else open_payment
        document_id = opener(
            company_id=company_id,
            partner_id=data["partner_id"],
            document_date=data["document_date"],
            accounting_date=data.get("accounting_date"),
            amount=Decimal(data["amount"]),
            treasury_account=data["treasury_account"],
            partner_resident=data["partner_resident"],
            notes=data.get("notes") or None,
        )
        return Response(_detail(document_id), status=201)


class TreasuryDetailView(APIView):
    def get(self, request: Request, document_id: uuid.UUID) -> Response:
        return Response(_detail(document_id))


class TreasuryRecordingView(APIView):
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


def _detail(document_id: uuid.UUID) -> dict[str, Any]:
    row = (
        TreasuryDocument.objects.filter(document_id=document_id).select_related("document").first()
    )
    if row is None:
        raise MissingTenantContextError("no such movement in this context")
    return _rendered(row)


def _rendered(row: TreasuryDocument) -> dict[str, Any]:
    document = row.document
    return {
        "id": str(document.id),
        "formatted_number": document.formatted_number,
        "document_date": str(document.document_date),
        "accounting_date": str(document.accounting_date),
        "state": document.state,
        "partner_id": str(document.partner_id) if document.partner_id else None,
        "currency": document.currency,
        "direction": row.direction,
        "treasury_account": row.treasury_account,
        # A string, like every other amount on the wire: parsed to a float it
        # would stop being the number the ledger holds.
        "amount": str(row.amount),
        "partner_resident": row.partner_resident,
    }


def _context() -> Any:
    context = current_context()
    if context is None:
        raise MissingTenantContextError("no tenant context on this request")
    return context
