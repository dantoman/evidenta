"""Reading the ledger -- the trial balance, and only that so far.

`D3` is about who may import `accounting.ledger`, not about whether the ledger
may be read over HTTP. Nothing writes through here: the only way into the ledger
is an accounting event through the engine (R9), and this module has no endpoint
that could accept one.
"""

from __future__ import annotations

import uuid
from datetime import date

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.accounting.ledger.services.trial_balance import trial_balance
from evidenta.platform.api.errors import ApiError


class InvalidPeriodError(ApiError):
    """`?from=`/`?to=` missing or not a date. A stable code, not a field error."""

    code = "ledger.invalid_period"
    status = 400


def _day(request: Request, name: str) -> date:
    raw = request.query_params.get(name)
    if raw is None:
        raise InvalidPeriodError(f"{name} is required: a balance is always for a window")
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise InvalidPeriodError(f"{raw!r} is not an ISO date") from None


class TrialBalanceView(APIView):
    def get(self, request: Request, company_id: uuid.UUID) -> Response:
        """The trial balance over `[from, to]`, both ends inclusive.

        The dates are the caller's and are never defaulted to today: a balance
        whose window depends on when it was asked for is a balance two people
        cannot compare (R18 has the same reason on the parameter side).
        """
        start, end = _day(request, "from"), _day(request, "to")
        if end < start:
            raise InvalidPeriodError("the window ends before it starts")

        balance = trial_balance(company_id, start, end)
        return Response(
            {
                "start_date": str(balance.start_date),
                "end_date": str(balance.end_date),
                "rows": [
                    {
                        "account_id": str(row.account_id),
                        "account_code": row.account_code,
                        "name_ro": row.name_ro,
                        # Decimals as strings, all the way out. A float here
                        # would undo on the wire exactly what `numeric` protects
                        # in the database.
                        "opening": str(row.opening),
                        "debit": str(row.debit),
                        "credit": str(row.credit),
                        "closing": str(row.closing),
                    }
                    for row in balance.rows
                ],
                # Server-side totals (C19). The client never sums a column.
                "total_debit": str(balance.total_debit),
                "total_credit": str(balance.total_credit),
                "balanced": balance.balanced,
            }
        )
