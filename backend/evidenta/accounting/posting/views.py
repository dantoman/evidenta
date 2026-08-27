"""Posting a manual note, and cancelling one -- the write paths into the ledger.

The endpoint composes and refuses; it computes nothing. Everything it hands the
engine is either the user's (the lines, the date, the description) or read from a
module that owns it: the currency from `platform.tenancy`, the capability profile
from `platform.capabilities`, the tenant and the actor from the request context.
`accounting` may import `platform` (DG), and none of these are reached for
through a model of another business module.

`Idempotency-Key` is required (C9) and is the engine's key, not the endpoint's
(R19): the same key posts once, and a retry answers with the entry the first
attempt wrote instead of writing a second one.

A correction is a storno and never an edit (R10). It goes through the same engine
as the note it cancels -- `posting.services.reversal` -- so the endpoint below
composes and refuses exactly like the other one, and there is no path here that
touches a posted row.

**The correction's date is required and has no default.** Which date a reversal
carries is ADR-007, open, and the service refuses to guess it; an HTTP layer that
filled it in with today would close that decision from the worst possible place --
silently, in the module least able to argue about it.
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
from evidenta.accounting.posting.services.reversal import post_reversal
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


class ReverseEntrySerializer(serializers.Serializer[dict[str, Any]]):
    """What a storno needs beyond the entry it cancels.

    `reason` is not decoration and is not defaulted: it is the only part of a
    correction a reader cannot reconstruct from the ledger itself. The amounts,
    the accounts and the link are all in the mirror entry; why somebody decided
    to cancel is not.
    """

    company_id = serializers.UUIDField()
    accounting_date = serializers.DateField()
    reason = serializers.CharField(max_length=500)
    # ADR-006's other half: where the correction belongs, when that differs from
    # where it posts. Absent for a correction inside its own open period.
    corrects_period_id = serializers.UUIDField(required=False)


class ReverseEntryView(APIView):
    def post(self, request: Request, entry_id: uuid.UUID) -> Response:
        context = current_context()
        if context is None:  # pragma: no cover -- the middleware refuses first
            raise MissingTenantContextError("posting needs a tenant context")

        key = read_key(request._request)

        payload = ReverseEntrySerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)

        company_id = data["company_id"]
        accounting_date = data["accounting_date"]
        # Read for its side effect as much as its value: it refuses a company
        # this context cannot see, before anything is emitted.
        functional_currency(company_id)

        result = post_reversal(
            tenant_id=context.tenant_id,
            company_id=company_id,
            entry_id=entry_id,
            accounting_date=accounting_date,
            reason=data["reason"],
            idempotency_key=key,
            actor_user_id=context.user_id,
            request_id=context.request_id,
            capability_snapshot=active_profile(company_id, accounting_date).as_snapshot(),
            corrects_period_id=data.get("corrects_period_id"),
        )

        return Response(
            {
                "accounting_event_id": str(result.accounting_event_id),
                "journal_entry_id": str(result.journal_entry_id),
                "posted_now": result.posted_now,
            },
            status=201 if result.posted_now else 200,
        )
