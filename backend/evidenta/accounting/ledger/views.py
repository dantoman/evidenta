"""Reading the ledger -- the register and the trial balance.

`D3` is about who may import `accounting.ledger`, not about whether the ledger
may be read over HTTP. Nothing writes through here: the only way into the ledger
is an accounting event through the engine (R9), and this module has no endpoint
that could accept one -- correcting an entry included, which is a storno posted
through the engine like any other effect.

The register exists because of what the slice was missing rather than for
completeness: after posting a note there was no way to see what had been posted,
only the balance it moved. That also makes it the precondition for correction --
a storno needs an entry to name, and nothing showed one.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.accounting.coa.services.accounts import names_for
from evidenta.accounting.ledger.models import JournalEntry, JournalLine
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


#: A page of the register. Bounded because the ledger is the largest table in the
#: system and an unbounded read of it is a way to make the database do work from
#: outside; the window narrows it further, and both are stated in the answer so a
#: caller can see it was cut rather than guess.
PAGE = 200


class EntryListView(APIView):
    def get(self, request: Request, company_id: uuid.UUID) -> Response:
        """The entries of one company over `[from, to]`, newest accounting date first.

        Lines come with them, in one query rather than one per entry: an entry
        without its lines is not something an accountant can read, so a caller
        that had to fetch them separately would fetch them every time anyway.

        Account codes are asked of `coa` through its service (D6). A journal line
        carries **no foreign key** to the account (R21) -- the link is by id and
        points the other way -- so there is nothing for the database to join and
        the reader has to ask.
        """
        start, end = _day(request, "from"), _day(request, "to")
        if end < start:
            raise InvalidPeriodError("the window ends before it starts")

        entries = list(
            JournalEntry.objects.filter(
                company_id=company_id,
                accounting_date__gte=start,
                accounting_date__lte=end,
            ).order_by("-accounting_date", "-entry_number")[: PAGE + 1]
        )
        truncated = len(entries) > PAGE
        entries = entries[:PAGE]

        lines = list(
            JournalLine.objects.filter(
                journal_entry_id__in=[entry.id for entry in entries]
            ).order_by("line_number")
        )
        named = names_for(company_id, {line.account_id for line in lines})

        # Which of these entries has already been cancelled. Asked once, for the
        # page: an entry that has been reversed must not offer to be reversed
        # again, and the service refuses a second one anyway -- this is so the
        # screen can say so before the person tries.
        reversals = dict(
            JournalEntry.objects.filter(
                company_id=company_id, reverses_entry_id__in=[entry.id for entry in entries]
            ).values_list("reverses_entry_id", "id")
        )

        by_entry: dict[uuid.UUID, list[dict[str, Any]]] = {entry.id: [] for entry in entries}
        for line in lines:
            code, name = named.get(line.account_id, (str(line.account_id), ""))
            by_entry[line.journal_entry_id].append(
                {
                    "line_number": line.line_number,
                    "account_id": str(line.account_id),
                    "account_code": code,
                    "name_ro": name,
                    "debit": str(line.debit),
                    "credit": str(line.credit),
                    "description": line.description,
                }
            )

        return Response(
            {
                "start_date": str(start),
                "end_date": str(end),
                # Said out loud rather than silently cut: a list that stops at
                # 200 and does not say so reads as "that is all there is".
                "truncated": truncated,
                "entries": [
                    {
                        "id": str(entry.id),
                        "entry_number": entry.entry_number,
                        "accounting_date": str(entry.accounting_date),
                        "description": entry.description,
                        "status": entry.status,
                        "entry_type": entry.entry_type,
                        "total_debit": str(entry.total_debit),
                        "total_credit": str(entry.total_credit),
                        # Both halves of R14, so a reader can navigate a
                        # correction in either direction: what this entry cancels,
                        # and -- through the reverse lookup below -- whether it has
                        # itself been cancelled.
                        "reverses_entry_id": (
                            str(entry.reverses_entry_id) if entry.reverses_entry_id else None
                        ),
                        "reversed_by_entry_id": (
                            str(reversals[entry.id]) if entry.id in reversals else None
                        ),
                        "accounting_event_id": str(entry.accounting_event_id),
                        "lines": by_entry[entry.id],
                    }
                    for entry in entries
                ],
            }
        )
