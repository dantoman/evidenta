"""Exchange rates and revaluations over HTTP -- `/api/v1/accounting/currency/`.

**Reading a rate is open** (every tenant sees the same official rate) and asks
for a day, never for "the latest": the screen shows the rate a document will be
converted at, and that is the rate of the document's date or a refusal
(ADR-039 section 3.2, `currency.rate_not_found`). Writing goes through the
loader under `P-3` and has no endpoint here; the console's door is another
session's.

**A revaluation is a posting**, so `Idempotency-Key` is required (`C9`). The key
that decides is the engine's -- one revaluation per company and date (`R19`) --
and the header is what the rule asks of every endpoint with a financial effect.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.accounting.currency.models import RateType
from evidenta.accounting.currency.services.rates import rate_on
from evidenta.accounting.currency.services.revaluation import (
    items_of,
    list_revaluations,
    revalue_monetary_items,
)
from evidenta.platform.api.errors import ApiError
from evidenta.platform.api.idempotency import read_key
from evidenta.platform.capabilities.services.profile import active_profile
from evidenta.platform.rls.context import MissingTenantContextError, current_context


class RateQueryInvalidError(ApiError):
    code = "currency.rate_query_invalid"
    status = 422


class RateView(APIView):
    def get(self, request: Request) -> Response:
        currency = str(request.query_params.get("currency") or "").strip().upper()
        raw_on = str(request.query_params.get("on") or "").strip()
        if len(currency) != 3 or not currency.isalpha():
            raise RateQueryInvalidError("currency is a three-letter ISO 4217 code")
        try:
            on = date.fromisoformat(raw_on)
        except ValueError:
            raise RateQueryInvalidError("on is a date, YYYY-MM-DD") from None
        rate = rate_on(currency, on)
        return Response(
            {
                "currency": currency,
                "rate_date": on.isoformat(),
                "rate": str(rate),
                "rate_type": RateType.BNM_OFFICIAL,
            }
        )


class RevaluationSerializer(serializers.Serializer[dict[str, Any]]):
    as_of = serializers.DateField()


class RevaluationListView(APIView):
    def get(self, request: Request, company_id: uuid.UUID) -> Response:
        return Response(items_of(list_revaluations(company_id)))

    def post(self, request: Request, company_id: uuid.UUID) -> Response:
        context = current_context()
        if context is None:  # pragma: no cover -- the middleware refuses first
            raise MissingTenantContextError("a revaluation needs a tenant context")
        read_key(request._request)

        payload = RevaluationSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        as_of = payload.validated_data["as_of"]

        result = revalue_monetary_items(
            tenant_id=context.tenant_id,
            company_id=company_id,
            as_of=as_of,
            actor_user_id=context.user_id,
            request_id=context.request_id,
            capability_snapshot=active_profile(company_id, as_of).as_snapshot(),
        )
        body = items_of([result.revaluation])[0]
        body["posted_now"] = result.posted_now
        return Response(body, status=201 if result.posted_now else 200)
