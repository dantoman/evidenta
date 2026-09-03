"""The role bindings over HTTP -- `/api/v1/accounting/slots/`.

What the panel could only report, this lets a person change. "Planul companiei
nu are un cont de casa legat" was a sentence with no door behind it: the binding
lived in a table nothing exposed, and the only writer was a management command.

**Two routes, and the second is a rebinding, never an edit.** `PUT` on a role does
not update the binding in force; it closes it on the date given and opens a new
one there (`R18`). The service says why in its own words; what the endpoint adds
is that the date is stated by the caller, never defaulted to today -- a rebinding
dated by the clock is one two people cannot reproduce.

The company is in the path, as it is for the periods and the chart, and RLS still
decides whether this context may reach it: another tenant's company is a 404 that
says nothing (IZ-04), on both routes. The tenant is never in the path (`C8`).

No `Idempotency-Key` (`C9`): a rebinding has no financial effect of its own. What
it changes is what the *next* posting resolves to, and that posting carries the
key.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.accounting.slots.models import AccountRoleBinding
from evidenta.accounting.slots.services.binding import rebind_role, role_overview
from evidenta.platform.api.errors import ApiError
from evidenta.platform.api.lookup import NotFoundError
from evidenta.platform.tenancy.services.access import company_visible_in_context


class InvalidDateError(ApiError):
    """`?on=` is not a date. A stable code, not DRF's field-error shape."""

    code = "slots.invalid_date"
    status = 400


class RebindRoleSerializer(serializers.Serializer[dict[str, Any]]):
    """The account, and the day the role starts meaning it.

    Both required. A rebinding without a date would have to pick one, and
    "today" is the wrong answer for the accountant who is correcting the setup
    of a company that started keeping books here three months ago.
    """

    account_id = serializers.UUIDField()
    valid_from = serializers.DateField()


def _on(request: Request) -> date:
    """The date the overview is read at. Today when absent: the screen always
    sends one, and a script reading the current state means now."""
    raw = request.query_params.get("on")
    if raw is None:
        return date.today()
    try:
        return date.fromisoformat(str(raw))
    except ValueError:
        raise InvalidDateError(f"`on` must be a date (YYYY-MM-DD), not {raw!r}") from None


def _rendered(binding: AccountRoleBinding) -> dict[str, Any]:
    return {
        "id": str(binding.id),
        "role": binding.role,
        "account_id": str(binding.account_id),
        "account_code": binding.account.account_code,
        "name_ro": binding.account.name_ro,
        "valid_from": binding.valid_from.isoformat(),
        "valid_to": binding.valid_to.isoformat() if binding.valid_to else None,
        "source": binding.source,
    }


class RoleBindingListView(APIView):
    """Every role of the catalogue, with the account it resolves to on `?on=`.

    Unbound roles are rows too, with the code the plan imposes beside the empty
    binding -- the screen exists for exactly those rows.
    """

    def get(self, request: Request, company_id: uuid.UUID) -> Response:
        on = _on(request)
        if not company_visible_in_context(company_id):
            raise NotFoundError(f"company {company_id} is not visible in this context")
        return Response(role_overview(company_id, on))


class RoleBindingView(APIView):
    def put(self, request: Request, company_id: uuid.UUID, role: str) -> Response:
        payload = RebindRoleSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        binding = rebind_role(
            company_id=company_id,
            role=role,
            account_id=data["account_id"],
            valid_from=data["valid_from"],
        )
        return Response(_rendered(binding), status=200)
