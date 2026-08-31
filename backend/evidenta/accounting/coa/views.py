"""HTTP for the chart of accounts -- `/api/v1/accounting/coa/`.

The version is in the path and the resource follows the module (C7). The tenant
is never here: it comes from the subdomain (C8), so no route below carries a
tenant identifier and no body is believed about one.

**The company is in the path, and that is not the same thing.** A company is a
resource inside the tenant, an account belongs to one, and a client that holds
three companies of a holding has to be able to say which one it is working in.
RLS still decides whether the caller may reach it: `rls.has_company_access` runs
on every row either way, so naming a company id grants nothing -- an inaccessible
one produces an empty chart and a 404 on write, never a 403 (IZ-04).

**No `Idempotency-Key`.** C9 requires one where there is a financial effect;
creating an account is not one. Nothing here reaches the ledger -- posting does,
and that endpoint will carry the header.

**Nothing here writes.** Every mutation is a call into `services`, where the
rules of Spec B section 2.4 live. A view that used a `ModelSerializer.save()`
would be a second way past them.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.accounting.coa.models import (
    CoaTemplate,
    CompanyAccount,
    CompanyChart,
    TemplateStatus,
)
from evidenta.accounting.coa.serializers import (
    AccountSerializer,
    ChartSerializer,
    CreateSubaccountSerializer,
    InstantiateChartSerializer,
    TemplateSerializer,
    UpdateAccountSerializer,
)
from evidenta.accounting.coa.services import accounts as account_services
from evidenta.accounting.coa.services.setup import set_up_chart
from evidenta.platform.api.errors import ApiError
from evidenta.platform.api.lookup import get_or_404


class InvalidDateError(ApiError):
    """`?on=` is not a date. A stable code, not DRF's field-error shape."""

    code = "coa.invalid_date"
    status = 400


def _validated(serializer_class: Any, data: Any) -> dict[str, Any]:
    serializer = serializer_class(data=data)
    serializer.is_valid(raise_exception=True)
    return dict(serializer.validated_data)


class TemplateListView(APIView):
    """Published chart versions, newest validity first.

    Only `published`. A draft is a version being prepared and instantiating one
    is refused by the service anyway -- listing them would put a choice on screen
    that the server will not honour.
    """

    def get(self, request: Request) -> Response:
        rows = CoaTemplate.objects.filter(status=TemplateStatus.PUBLISHED).order_by(
            "code", "-valid_from"
        )
        return Response(TemplateSerializer(rows, many=True).data)


class ChartView(APIView):
    """The company's chart: which version it was built on, and building it."""

    def get(self, request: Request, company_id: uuid.UUID) -> Response:
        chart = get_or_404(CompanyChart.objects.all(), company_id=company_id)
        return Response(ChartSerializer(chart).data)

    def post(self, request: Request, company_id: uuid.UUID) -> Response:
        """Set the company up to keep books: the chart **and** the role bindings.

        Until onboarding exists this is the only way a company gets a chart --
        `P-9` (ADR-040) is decided and unwritten, and when it lands it calls the
        same service in the same transaction rather than this endpoint.

        `set_up_chart` rather than `instantiate_chart`, and the difference is the
        defect it closes: the bindings had no caller outside the tests, so every
        company created through the product had a chart and not one role binding
        (ADR-073 section 10).
        """
        payload = _validated(InstantiateChartSerializer, request.data)
        setup = set_up_chart(company_id, payload["template_id"])
        chart = CompanyChart.objects.get(id=setup.chart_id)
        return Response(ChartSerializer(chart).data, status=201)


class AccountListView(APIView):
    def get(self, request: Request, company_id: uuid.UUID) -> Response:
        """The company's accounts, or those postable on a given date.

        `?on=YYYY-MM-DD` narrows to what a posting dated then may use: inside its
        validity window and not blocked. The date is always the caller's -- the
        server never substitutes today, because a recalculation of a closed
        period must see the chart as it was (R18).
        """
        on = request.query_params.get("on")
        if on is None:
            whole = CompanyAccount.objects.filter(company_id=company_id).order_by("account_code")
            return Response(AccountSerializer(whole, many=True).data)

        try:
            on_date = date.fromisoformat(on)
        except ValueError:
            raise InvalidDateError(f"{on!r} is not an ISO date") from None
        return Response(
            AccountSerializer(
                account_services.postable_accounts(company_id, on_date), many=True
            ).data
        )

    def post(self, request: Request, company_id: uuid.UUID) -> Response:
        payload = _validated(CreateSubaccountSerializer, request.data)
        parent_id = payload.pop("parent_id")

        # The parent is fetched under the company in the path, not trusted from
        # the body alone: without this, a body naming an accessible account of
        # *another* company would create a subaccount there while the URL said
        # otherwise. RLS would allow it -- the caller does have access to both.
        get_or_404(CompanyAccount.objects.filter(company_id=company_id), id=parent_id)

        account = account_services.create_subaccount(
            parent_id,
            payload.pop("account_code"),
            payload.pop("name_ro"),
            payload.pop("valid_from"),
            **payload,
        )
        return Response(AccountSerializer(account).data, status=201)


class AccountDetailView(APIView):
    def get(self, request: Request, account_id: uuid.UUID) -> Response:
        account = get_or_404(CompanyAccount.objects.all(), id=account_id)
        return Response(AccountSerializer(account).data)

    def patch(self, request: Request, account_id: uuid.UUID) -> Response:
        """Rename, block, close, declare slots -- each through its own service.

        Applied in a fixed order so a request carrying more than one is not
        order-dependent, and each leaves its own audit entry. A single "update"
        would leave one entry describing a diff, which is the thing an auditor
        cannot use.
        """
        payload = _validated(UpdateAccountSerializer, request.data)
        account = get_or_404(CompanyAccount.objects.all(), id=account_id)

        if "name_ro" in payload:
            account = account_services.rename_account(account.id, payload["name_ro"])
        if "is_blocked" in payload:
            account = account_services.set_blocked(account.id, payload["is_blocked"])
        if "valid_to" in payload:
            account = account_services.close_account(account.id, payload["valid_to"])
        if "dimension_slots" in payload:
            account = account_services.declare_dimension_slots(
                account.id, payload["dimension_slots"], payload.get("required_dimensions")
            )

        return Response(AccountSerializer(account).data)
