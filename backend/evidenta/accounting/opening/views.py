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

**All six row kinds are exposed.** Three of them arrived later than the others,
and the reason they waited is worth keeping: ``item_id``, ``asset_id`` and
``employee_id`` named entities that did not exist, and an endpoint accepting an
id with no table behind it looked like delivered function. Employees exist now
(`payroll`), and the cumulative set is what lets a company activate payroll in
the middle of a year without granting the year's exemptions twice (ADR-061). The
item and the asset are still identities of the *source* system -- there is no
asset registry yet and no HTTP surface for items -- so the screen says so and
the identifier is the one the company will attach the object to later. Refusing
the set until then would refuse the stock and the fixed assets of every company
that arrives from 1C, which is every company that arrives.

**The payroll set carries a closed vocabulary and a sign.** ``code`` is one of
the three keys of ADR-061 -- refused here, by the serializer, because the model
deliberately holds no CHECK on it -- and ``amount`` is never negative, which the
database also refuses (``opening_balance_payroll_amount_not_negative``). The
serializer says it first so the answer is a 400 with a code rather than an
integrity error.

**Posting is the only step that takes an ``Idempotency-Key``** (`C9`), and it is
the engine's key rather than the endpoint's (`R19`): the same key posts one entry,
and a retry answers with what the first attempt wrote. Creating a batch and adding
rows are not financial effects -- a duplicate batch is visible, editable and
rejectable, which is the difference.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.accounting.opening.models import BatchSource
from evidenta.accounting.opening.services.batches import (
    AssetRow,
    GlRow,
    InventoryRow,
    PartnerRow,
    PayrollRow,
    add_rows,
    batch_in_context,
    batches_of,
    create_batch,
    decomposition,
    load_contents,
    validate_batch,
)
from evidenta.accounting.opening.services.cumulatives import CUMULATIVE_CODES
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
    # Numele campului se ciocneste cu `Field.source` din DRF, care e declarat
    # `str | None` pe clasa de baza — de aceea o adnotare nu ajuta: nu e o
    # deducere gresita, e o redefinire reala de tip. La rulare nu se ciocneste
    # nimic (metaclasa muta campurile declarate in `_declared_fields`), iar
    # numele ramane `source` fiindca asta e forma de pe sarma si asta citeste
    # clientul. Ignorarea e tintita si **verificata ca folosita**: `mypy .`
    # raporteaza exact aceasta linie, deci nu putrezeste tacut ca una nefolosita.
    source = serializers.ChoiceField(choices=BatchSource.values)  # type: ignore[assignment]
    counterpart_account_id = serializers.UUIDField()


class GlRowSerializer(serializers.Serializer[dict[str, Any]]):
    """One general-ledger balance. Amounts arrive as strings and stay decimal.

    Never floats: the service refuses a value it cannot store exactly, and
    parsing through a float would have destroyed the value before the check.
    """

    account_id = serializers.UUIDField()
    # `Decimal("0")`, nu `0`: campul e zecimal, iar implicitul lui trebuie sa fie
    # de acelasi fel. DRF ar fi convertit oricum, deci nu se schimba nimic la
    # rulare — se schimba doar ce poate afirma verificatorul de tipuri, si
    # `mypy .` din CI chiar il refuza pe `int`.
    debit = serializers.DecimalField(max_digits=20, decimal_places=4, default=Decimal(0))
    credit = serializers.DecimalField(max_digits=20, decimal_places=4, default=Decimal(0))
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


class InventoryRowSerializer(serializers.Serializer[dict[str, Any]]):
    """One stock balance: what, where, how much, and what it cost.

    ``total_cost`` is the debit and the only side there is -- a negative stock
    balance is a defect of the source, and the service refuses it. Quantity and
    unit are both required, because a journal line may carry a quantity only
    with a unit; the unit cost travels but nothing recomputes the total from it
    (ADR-038 section 7.3, and the rounding that would take is `DNB-08`).
    """

    account_id = serializers.UUIDField()
    item_id = serializers.UUIDField()
    uom_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=20, decimal_places=6)
    total_cost = serializers.DecimalField(max_digits=20, decimal_places=4)
    warehouse_id = serializers.UUIDField(required=False, allow_null=True)
    lot = serializers.CharField(required=False, allow_null=True)
    unit_cost = serializers.DecimalField(
        max_digits=20, decimal_places=6, required=False, allow_null=True
    )
    currency = serializers.CharField(max_length=3, required=False, allow_null=True)
    amount_currency = serializers.DecimalField(
        max_digits=20, decimal_places=4, required=False, allow_null=True
    )


class AssetRowSerializer(serializers.Serializer[dict[str, Any]]):
    """One fixed asset: two accounts, two amounts, and the schedule it arrives with.

    ``accumulated_depreciation`` defaults to zero because an asset bought last
    month has none, and a zero leg posts no line. ``in_service_date`` and
    ``remaining_months`` do not post; they ride with the batch so the asset
    module has a schedule rather than a balance to guess one from.
    """

    asset_id = serializers.UUIDField()
    cost_account_id = serializers.UUIDField()
    depreciation_account_id = serializers.UUIDField()
    entry_cost = serializers.DecimalField(max_digits=20, decimal_places=4)
    accumulated_depreciation = serializers.DecimalField(
        max_digits=20, decimal_places=4, default=Decimal(0)
    )
    in_service_date = serializers.DateField()
    remaining_months = serializers.IntegerField(required=False, allow_null=True, min_value=0)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        # `opening_balance_asset_two_accounts` refuses this in the database, and
        # that is the barrier that holds against the importer. Saying it here
        # turns an integrity error with no code into a 400 with one (C10).
        if attrs["cost_account_id"] == attrs["depreciation_account_id"]:
            raise serializers.ValidationError(
                {
                    "depreciation_account_id": (
                        "cost and accumulated depreciation sit on two accounts; on one "
                        "they would net to a book value and lose both numbers"
                    )
                }
            )
        return attrs


class PayrollCumulativeRowSerializer(serializers.Serializer[dict[str, Any]]):
    """One year-to-date amount of one employee -- ADR-061.

    ``code`` is closed to the three keys of the cumulative method, and
    ``amount`` is a magnitude: the meaning is the code's, never the sign's. The
    window starts at ``from_date`` -- 1 January, or the hiring date for somebody
    who joined during the year (HG 697/2014 point 38) -- and it is stated, not
    assumed, because an exercise need not start in January either.
    """

    employee_id = serializers.UUIDField()
    code = serializers.ChoiceField(choices=list(CUMULATIVE_CODES))
    amount = serializers.DecimalField(max_digits=20, decimal_places=4, min_value=Decimal(0))
    from_date = serializers.DateField()


class AddRowsSerializer(serializers.Serializer[dict[str, Any]]):
    gl = GlRowSerializer(many=True, required=False)
    receivables = PartnerRowSerializer(many=True, required=False)
    payables = PartnerRowSerializer(many=True, required=False)
    inventory = InventoryRowSerializer(many=True, required=False)
    assets = AssetRowSerializer(many=True, required=False)
    payroll_cumulatives = PayrollCumulativeRowSerializer(many=True, required=False)


class BatchListView(APIView):
    """The company's batches, and the way to start one. Company in the path (`C8`).

    The listing is not a convenience. A batch is never deleted -- four states,
    three of which outlive the session that created them -- so a `draft`
    abandoned yesterday is still there. Without a way back to it, the next import
    starts from zero beside it, and the company ends up with two partial pictures
    of one opening position.
    """

    def get(self, request: Request, company_id: uuid.UUID) -> Response:
        functional_currency(company_id)
        return Response(batches_of(company_id))

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
                "inventory": [_inventory(row) for row in contents.inventory],
                "assets": [_asset(row) for row in contents.assets],
                "payroll_cumulatives": [_payroll(row) for row in contents.payroll],
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
            inventory=[InventoryRow(**row) for row in data.get("inventory", [])],
            assets=[AssetRow(**row) for row in data.get("assets", [])],
            payroll=[PayrollRow(**row) for row in data.get("payroll_cumulatives", [])],
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


def _inventory(row: Any) -> dict[str, Any]:
    return {
        "account_id": str(row.account_id),
        "item_id": str(row.item_id),
        "warehouse_id": str(row.warehouse_id) if row.warehouse_id else None,
        "lot": row.lot,
        "quantity": str(row.quantity),
        "uom_id": str(row.uom_id),
        "unit_cost": str(row.unit_cost) if row.unit_cost is not None else None,
        # The debit, under the name the caller gave it: the set has one side.
        "total_cost": str(row.debit),
        "currency": row.currency,
    }


def _asset(row: Any) -> dict[str, Any]:
    return {
        "asset_id": str(row.asset_id),
        "cost_account_id": str(row.cost_account_id),
        "depreciation_account_id": str(row.depreciation_account_id),
        "entry_cost": str(row.entry_cost),
        "accumulated_depreciation": str(row.accumulated_depreciation),
        "in_service_date": row.in_service_date.isoformat(),
        "remaining_months": row.remaining_months,
    }


def _payroll(row: Any) -> dict[str, Any]:
    return {
        "employee_id": str(row.employee_id),
        "code": row.code,
        "amount": str(row.amount),
        "from_date": row.from_date.isoformat(),
    }
