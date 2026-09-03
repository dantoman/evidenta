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
from evidenta.platform.api.idempotency import read_key
from evidenta.platform.capabilities.services.profile import active_profile
from evidenta.platform.documents.services.lifecycle import get_document
from evidenta.platform.rls.context import MissingTenantContextError, current_context


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

        context = current_context()
        if context is None:  # pragma: no cover -- the middleware refuses first
            raise MissingTenantContextError("a settlement needs a tenant context")
        # Read under the policy, for the profile the engine posts under when the
        # settlement crosses currencies (ADR-097). A document this context cannot
        # see is absent (IZ-04), and the service refuses the rest.
        settled = get_document(data["settled_document_id"])
        # C9: an allocation is an effect -- across currencies a posting -- and a
        # retry must find its first arrival, not allocate again (R19).
        key = read_key(request._request)

        result = allocate(
            idempotency_key=key,
            settled_document_id=data["settled_document_id"],
            movement_document_id=data["movement_document_id"],
            amount=Decimal(data["amount"]),
            actor_user_id=context.user_id,
            request_id=context.request_id,
            capability_snapshot=active_profile(
                settled.company_id, settled.accounting_date
            ).as_snapshot(),
        )
        return Response(
            {
                "settlement_id": str(result.settlement_id),
                "outstanding_after": str(result.outstanding_after),
                "currency": result.currency,
                "amount_currency": str(result.amount_currency),
                "journal_entry_id": (
                    str(result.journal_entry_id) if result.journal_entry_id else None
                ),
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
        "currency": item.currency,
        "total": str(item.total),
        "allocated": str(item.allocated),
        "outstanding": str(item.outstanding),
    }
