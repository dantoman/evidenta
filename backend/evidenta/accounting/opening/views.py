"""The way into the opening balances -- F1.7.2, ADR-039 section 11.

The services have been complete since the batch model landed and nothing reached
them, which had a consequence worth stating plainly: the product was usable only
by a company founded today. A firm arriving from 1C had no way to bring its
balances in, so its trial balance started at zero and meant nothing.

The endpoints compose and refuse; they compute nothing. Every amount is the
user's, and every check belongs to a service that owns the rule -- the balance of
the general-ledger set, the agreement between analytical detail and its control
account, the currency. An HTTP layer that re-checked any of them would be a
second opinion, and the two would drift.

**Three of the six row kinds are exposed, deliberately.** ``add_rows`` accepts
general-ledger, receivable, payable, inventory, asset and payroll rows. The last
three name ``item_id``, ``asset_id`` and ``employee_id`` -- entities of F4 and F2,
which do not exist yet. An endpoint accepting an id with no table behind it is one
nobody can call correctly while looking like delivered function. The service is
untouched; this surface grows when the modules do.

**Posting is the only step that takes an ``Idempotency-Key``** (`C9`), and it is
the engine's key rather than the endpoint's (`R19`): the same key posts one entry,
and a retry answers with what the first attempt wrote. Creating a batch and adding
rows are not financial effects -- a duplicate batch is visible, editable and
rejectable, which is the difference.
"""

from __future__ import annotations

import uuid
from typing import Any

from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.accounting.opening.models import BatchSource
from evidenta.accounting.opening.services.batches import (
    GlRow,
    PartnerRow,
    add_rows,
    batch_in_context,
    create_batch,
    decomposition,
    load_contents,
    validate_batch,
)
from evidenta.accounting.opening.services.posting import post_batch
from evidenta.platform.api.idempotency import read_key
from evidenta.platform.capabilities.services.profile import active_profile
from evidenta.platform.rls.context import MissingTenantContextError, current_context
from evidenta.platform.tenancy.services.companies import functional_currency


def _context() -> Any:
    context = current_context()
    if context is None:  # pragma: no cover -- the middleware refuses first
        raise MissingTenantContextError("opening balances need a tenant context")
    return context


class CreateBatchSerializer(serializers.Serializer[dict[str, Any]]):
    """What a batch is before it has a single row.

    ``counterpart_account_id`` is required and has no default. It is the account
    the whole set balances against, and Spec B calls for it to be named rather
    than assumed: a wrong counterpart is a wrong opening entry that balances, and
    those are the ones nobody notices.
    """

    as_of_date = serializers.DateField()
    source = serializers.ChoiceField(choices=BatchSource.values)
    counterpart_account_id = serializers.UUIDField()


class GlRowSerializer(serializers.Serializer[dict[str, Any]]):
    """One general-ledger balance. Amounts arrive as strings and stay decimal.

    Never floats: the service refuses a value it cannot store exactly, and
    parsing through a float would have destroyed the value before the check.
    """

    account_id = serializers.UUIDField()
    debit = serializers.DecimalField(max_digits=20, decimal_places=4, default=0)
    credit = serializers.DecimalField(max_digits=20, decimal_places=4, default=0)
    currency = serializers.CharField(max_length=3, required=False, allow_null=True)
    amount_currency = serializers.DecimalField(
        max_digits=20, decimal_places=4, required=False, allow_null=True
    )


class PartnerRowSerializer(GlRowSerializer):
    """A receivable or a payable, which is a balance *plus* who owes it.

    The document fields are optional here and not decorative: an opening
    receivable with no document is a number the accountant cannot chase, and the
    ones that carry a due date are what an ageing report is built from.
    """

    partner_id = serializers.UUIDField()
    document_type = serializers.CharField(required=False, allow_null=True)
    document_number = serializers.CharField(required=False, allow_null=True)
    document_date = serializers.DateField(required=False, allow_null=True)
    due_date = serializers.DateField(required=False, allow_null=True)


class AddRowsSerializer(serializers.Serializer[dict[str, Any]]):
    gl = GlRowSerializer(many=True, required=False)
    receivables = PartnerRowSerializer(many=True, required=False)
    payables = PartnerRowSerializer(many=True, required=False)


class BatchListView(APIView):
    """Create a batch for one company. The company is in the path (`C8`)."""

    def post(self, request: Request, company_id: uuid.UUID) -> Response:
        context = _context()
        payload = CreateBatchSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)

        # Read for its side effect as much as its value: it refuses a company
        # this context cannot see, before a row is written.
        functional_currency(company_id)

        batch = create_batch(
            company_id=company_id,
            as_of_date=data["as_of_date"],
            source=data["source"],
            counterpart_account_id=data["counterpart_account_id"],
            created_by_user_id=context.user_id,
        )
        return Response(_summary(batch), status=201)


class BatchDetailView(APIView):
    """The batch with what it holds, and what it decomposes to per account.

    ``decomposition`` is the number the accountant actually reads: the analytical
    rows summed by account, which is what has to agree with the general-ledger
    set before anything posts. Computed by the service, not here (`C19` is about
    grids, but the reason is the same one).
    """

    def get(self, request: Request, batch_id: uuid.UUID) -> Response:
        batch = batch_in_context(batch_id)
        contents = load_contents(batch)
        return Response(
            {
                **_summary(batch),
                "gl": [
                    {
                        "account_id": str(row.account_id),
                        "debit": str(row.debit),
                        "credit": str(row.credit),
                        "currency": row.currency,
                    }
                    for row in contents.gl
                ],
                "receivables": [_partner(row) for row in contents.receivables],
                "payables": [_partner(row) for row in contents.payables],
                "decomposition": {
                    str(account_id): str(amount)
                    for account_id, amount in decomposition(contents).items()
                },
            }
        )


class BatchRowsView(APIView):
    def post(self, request: Request, batch_id: uuid.UUID) -> Response:
        payload = AddRowsSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)

        add_rows(
            batch_id,
            gl=[GlRow(**row) for row in data.get("gl", [])],
            receivables=[PartnerRow(**row) for row in data.get("receivables", [])],
            payables=[PartnerRow(**row) for row in data.get("payables", [])],
        )
        return Response(_summary(batch_in_context(batch_id)), status=200)


class BatchValidationView(APIView):
    """``draft -> validated``: every rule the set has to satisfy, run at once.

    A separate step from posting on purpose. The accountant wants to know the set
    agrees *before* committing to an entry, and a refusal here costs nothing --
    while a refusal during posting has already allocated a number.
    """

    def post(self, request: Request, batch_id: uuid.UUID) -> Response:
        batch = batch_in_context(batch_id)
        validated = validate_batch(batch_id, functional_currency(batch.company_id))
        return Response(_summary(validated), status=200)


class BatchPostingView(APIView):
    def post(self, request: Request, batch_id: uuid.UUID) -> Response:
        context = _context()
        key = read_key(request._request)
        batch = batch_in_context(batch_id)

        result = post_batch(
            batch_id=batch_id,
            functional_currency=functional_currency(batch.company_id),
            idempotency_key=key,
            actor_user_id=context.user_id,
            request_id=context.request_id,
            capability_snapshot=active_profile(batch.company_id, batch.as_of_date).as_snapshot(),
        )
        return Response(
            {
                "accounting_event_id": str(result.accounting_event_id),
                "journal_entry_id": str(result.journal_entry_id),
                "posted_now": result.posted_now,
            },
            status=201 if result.posted_now else 200,
        )


def _summary(batch: Any) -> dict[str, Any]:
    return {
        "id": str(batch.id),
        "company_id": str(batch.company_id),
        "as_of_date": batch.as_of_date.isoformat(),
        "source": batch.source,
        "status": batch.status,
        "counterpart_account_id": str(batch.counterpart_account_id),
    }


def _partner(row: Any) -> dict[str, Any]:
    return {
        "account_id": str(row.account_id),
        "partner_id": str(row.partner_id),
        "debit": str(row.debit),
        "credit": str(row.credit),
        "document_type": row.document_type,
        "document_number": row.document_number,
        "document_date": row.document_date.isoformat() if row.document_date else None,
        "due_date": row.due_date.isoformat() if row.due_date else None,
    }
