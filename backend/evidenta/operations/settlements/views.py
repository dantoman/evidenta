"""Open balances and matching over HTTP -- ADR-087.

**One GET for both lists.** They are read together or not at all: a matching
screen that fetched them separately would render one column and leave the other
loading, which on this screen means offering an allocation against half the truth.

**The POST carries three fields and nothing else.** Which document, which
movement, how much -- the side, the residence and the counterparty are read from
the documents, because they were asked once already.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.operations.settlements.services.allocation import allocate, outstanding
from evidenta.operations.settlements.services.balances import (
    OpenItem,
    open_documents,
    open_movements,
)


class AllocationSerializer(serializers.Serializer[dict[str, Any]]):
    settled_document_id = serializers.UUIDField()
    movement_document_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=20, decimal_places=2)


class OpenItemsView(APIView):
    def get(self, request: Request, company_id: uuid.UUID) -> Response:
        return Response(
            {
                "documents": [_rendered(item) for item in open_documents(company_id)],
                "movements": [_rendered(item) for item in open_movements(company_id)],
            }
        )


class AllocationView(APIView):
    def post(self, request: Request) -> Response:
        payload = AllocationSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)

        result = allocate(
            settled_document_id=data["settled_document_id"],
            movement_document_id=data["movement_document_id"],
            amount=Decimal(data["amount"]),
        )
        return Response(
            {
                "settlement_id": str(result.settlement_id),
                "outstanding_after": str(result.outstanding_after),
                # Read back rather than computed here: the number the screen shows
                # next is the one the rule will use next.
                "document_outstanding": str(outstanding(data["settled_document_id"])),
            },
            status=201,
        )


def _rendered(item: OpenItem) -> dict[str, Any]:
    return {
        "document_id": str(item.document_id),
        "document_type": item.document_type,
        "formatted_number": item.formatted_number,
        "document_date": str(item.document_date),
        "partner_id": str(item.partner_id) if item.partner_id else None,
        "side": item.side,
        "total": str(item.total),
        "allocated": str(item.allocated),
        "outstanding": str(item.outstanding),
    }
