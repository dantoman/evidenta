"""Posting a manual journal note over HTTP -- the one write path into the ledger.

The endpoint composes and refuses; it computes nothing. Everything it hands the
engine is either the user's (the lines, the date, the description) or read from a
module that owns it: the currency from `platform.tenancy`, the capability profile
from `platform.capabilities`, the tenant and the actor from the request context.
`accounting` may import `platform` (DG), and none of these are reached for
through a model of another business module.

`Idempotency-Key` is required (C9) and is the engine's key, not the endpoint's
(R19): the same key posts once, and a retry answers with the entry the first
attempt wrote instead of writing a second one.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.accounting.posting.services.manual import post_manual_entry
from evidenta.platform.api.idempotency import read_key
from evidenta.platform.capabilities.services.profile import active_profile
from evidenta.platform.rls.context import MissingTenantContextError, current_context
from evidenta.platform.tenancy.services.companies import functional_currency


class ManualLineSerializer(serializers.Serializer[dict[str, Any]]):
    """One proposed line. Amounts arrive as strings and stay decimal.

    `debit` and `credit` are not floats and never become floats: the engine
    refuses a value it cannot store exactly, and parsing through a float here
    would have already destroyed the value it is checking.
    """

    account_id = serializers.UUIDField()
    debit = serializers.DecimalField(max_digits=20, decimal_places=4, default=Decimal("0"))
    credit = serializers.DecimalField(max_digits=20, decimal_places=4, default=Decimal("0"))
    description = serializers.CharField(max_length=500, required=False, allow_blank=True)


class ManualEntrySerializer(serializers.Serializer[dict[str, Any]]):
    company_id = serializers.UUIDField()
    accounting_date = serializers.DateField()
    description = serializers.CharField(max_length=500)
    lines = ManualLineSerializer(many=True)
    # The note's own identity (R13's fourth link). The caller may supply it so a
    # retry from a form that lost its answer keeps the same note; absent, one is
    # allocated here.
    note_id = serializers.UUIDField(required=False)


class ManualEntryView(APIView):
    def post(self, request: Request) -> Response:
        context = current_context()
        if context is None:  # pragma: no cover -- the middleware refuses first
            raise MissingTenantContextError("posting needs a tenant context")

        key = read_key(request._request)

        payload = ManualEntrySerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)

        company_id = data["company_id"]
        # Asked of `tenancy` through its service (D6). Read under the policy, so
        # a company this context cannot see is absent rather than forbidden --
        # and the currency comes off the row that was actually visible, not off
        # an id in the payload.
        currency = functional_currency(company_id)
        accounting_date = data["accounting_date"]

        result = post_manual_entry(
            tenant_id=context.tenant_id,
            company_id=company_id,
            accounting_date=accounting_date,
            functional_currency=currency,
            note_id=data.get("note_id") or uuid.uuid4(),
            payload={
                "description": data["description"],
                "lines": [
                    {
                        "account_id": str(line["account_id"]),
                        "debit": str(line["debit"]),
                        "credit": str(line["credit"]),
                        "description": line.get("description") or None,
                    }
                    for line in data["lines"]
                ],
            },
            idempotency_key=key,
            actor_user_id=context.user_id,
            request_id=context.request_id,
            capability_snapshot=active_profile(company_id, accounting_date).as_snapshot(),
        )

        return Response(
            {
                "accounting_event_id": str(result.accounting_event_id),
                "journal_entry_id": str(result.journal_entry_id),
                # False when the key found an entry an earlier arrival wrote.
                # A caller that cannot tell the two apart reports "posted" twice.
                "posted_now": result.posted_now,
            },
            status=201 if result.posted_now else 200,
        )
