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

from django.http import HttpResponse
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.accounting.coa.services.accounts import names_for
from evidenta.accounting.ledger.errors import InvalidPeriodError
from evidenta.accounting.ledger.models import JournalEntry, JournalLine
from evidenta.accounting.ledger.services import export
from evidenta.accounting.ledger.services.account_ledger import account_ledger
from evidenta.accounting.ledger.services.correspondence import correspondence
from evidenta.accounting.ledger.services.detail import entry_detail
from evidenta.accounting.ledger.services.document_journal import document_journal
from evidenta.accounting.ledger.services.general_ledger import general_ledger
from evidenta.accounting.ledger.services.trial_balance import trial_balance
from evidenta.platform.api.errors import ApiError
from evidenta.platform.api.lookup import NotFoundError


class UnknownFormatError(ApiError):
    """`?export=` names something this endpoint does not produce."""

    code = "ledger.unknown_format"
    status = 400


#: The query parameter, and it is not `format`: DRF reserves `?format=` for its
#: own renderer negotiation (`URL_FORMAT_OVERRIDE`), and answers 404 for a value
#: no renderer claims -- measured, on the first request that tried `format=csv`.
EXPORT_PARAMETER = "export"


def _wants_csv(request: Request) -> bool:
    """`?export=csv` -- the same data the screen shows, as a file (C20).

    Only CSV. Excel and PDF need a library or a pipeline nobody has chosen
    (`OD-74`), and an endpoint that accepted `xlsx` and answered CSV would be
    lying in the file name.
    """
    wanted = request.query_params.get(EXPORT_PARAMETER)
    if wanted is None:
        return False
    if wanted == "csv":
        return True
    raise UnknownFormatError(f"{wanted!r} is not a format this report is produced in")


def _csv(body: bytes, filename: str) -> HttpResponse:
    response = HttpResponse(body, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _window(request: Request) -> tuple[date, date]:
    start, end = _day(request, "from"), _day(request, "to")
    if end < start:
        raise InvalidPeriodError("the window ends before it starts")
    return start, end


def _day(request: Request, name: str) -> date:
    raw = request.query_params.get(name)
    if raw is None:
        raise InvalidPeriodError(f"{name} is required: a balance is always for a window")
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise InvalidPeriodError(f"{raw!r} is not an ISO date") from None


class TrialBalanceView(APIView):
    def get(self, request: Request, company_id: uuid.UUID) -> HttpResponse:
        """The trial balance over `[from, to]`, both ends inclusive.

        The dates are the caller's and are never defaulted to today: a balance
        whose window depends on when it was asked for is a balance two people
        cannot compare (R18 has the same reason on the parameter side).
        """
        start, end = _window(request)

        balance = trial_balance(company_id, start, end)
        if _wants_csv(request):
            return _csv(export.trial_balance_csv(balance), f"balanta-{start}-{end}.csv")
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


def _decimal(value: Any) -> str | None:
    """Decimals as strings on the wire; None stays None."""
    return None if value is None else str(value)


class AccountLedgerView(APIView):
    def get(self, request: Request, company_id: uuid.UUID, account_id: uuid.UUID) -> HttpResponse:
        """The account ledger over `[from, to]` -- one row per document (ADR-053).

        Every figure is the server's: opening, the running balance after each
        row, the totals and the closing (C19). `truncated` says when the rows
        were cut; the totals are over the whole window regardless.
        """
        start, end = _window(request)
        ledger = account_ledger(company_id, account_id, start, end)
        if _wants_csv(request):
            return _csv(
                export.account_ledger_csv(ledger),
                f"fisa-cont-{ledger.account_code}-{start}-{end}.csv",
            )
        return Response(
            {
                "account_id": str(ledger.account_id),
                "account_code": ledger.account_code,
                "name_ro": ledger.name_ro,
                "start_date": str(ledger.start_date),
                "end_date": str(ledger.end_date),
                "opening": str(ledger.opening),
                "truncated": ledger.truncated,
                "rows": [
                    {
                        "journal_entry_id": str(row.journal_entry_id),
                        "entry_number": row.entry_number,
                        "accounting_date": str(row.accounting_date),
                        "document_date": str(row.document_date),
                        "entry_type": row.entry_type,
                        "description": row.description,
                        "debit": str(row.debit),
                        "credit": str(row.credit),
                        "balance": str(row.balance),
                        "has_formulas": row.has_formulas,
                        "reverses_entry_id": _decimal(row.reverses_entry_id),
                        "reversed_by_entry_id": _decimal(row.reversed_by_entry_id),
                        "correspondents": [
                            {
                                "account_id": str(c.account_id),
                                "account_code": c.account_code,
                                "debit": str(c.debit),
                                "credit": str(c.credit),
                            }
                            for c in row.correspondents
                        ],
                    }
                    for row in ledger.rows
                ],
                "total_debit": str(ledger.total_debit),
                "total_credit": str(ledger.total_credit),
                "closing": str(ledger.closing),
            }
        )


class GeneralLedgerView(APIView):
    def get(self, request: Request, company_id: uuid.UUID, account_id: uuid.UUID) -> HttpResponse:
        """The Cartea Mare of one account over `[from, to]`, month by month."""
        start, end = _window(request)
        ledger = general_ledger(company_id, account_id, start, end)
        if _wants_csv(request):
            return _csv(
                export.general_ledger_csv(ledger),
                f"cartea-mare-{ledger.account_code}-{start}-{end}.csv",
            )

        def turnovers(items: Any) -> list[dict[str, str]]:
            return [
                {
                    "account_id": str(t.account_id),
                    "account_code": t.account_code,
                    "amount": str(t.amount),
                }
                for t in items
            ]

        return Response(
            {
                "account_id": str(ledger.account_id),
                "account_code": ledger.account_code,
                "name_ro": ledger.name_ro,
                "start_date": str(ledger.start_date),
                "end_date": str(ledger.end_date),
                "opening": str(ledger.opening),
                "months": [
                    {
                        "period_id": str(month.period_id),
                        "period_no": month.period_no,
                        "start_date": str(month.start_date),
                        "end_date": str(month.end_date),
                        "opening": str(month.opening),
                        "debit": str(month.debit),
                        "credit": str(month.credit),
                        "closing": str(month.closing),
                        "debit_by": turnovers(month.debit_by),
                        "credit_by": turnovers(month.credit_by),
                        "debit_unassigned": str(month.debit_unassigned),
                        "credit_unassigned": str(month.credit_unassigned),
                    }
                    for month in ledger.months
                ],
                "total_debit": str(ledger.total_debit),
                "total_credit": str(ledger.total_credit),
                "closing": str(ledger.closing),
            }
        )


class DocumentJournalView(APIView):
    """One family's posted documents over a window -- F1.8.

    The family is a path segment and it is the **owner module's name**, not a list
    of type codes: the reader asks for "the sales journal", and which document
    types that means is the registry's answer, not the caller's.
    """

    def get(self, request: Request, company_id: uuid.UUID, owner: str) -> HttpResponse:
        start, end = _window(request)
        report = document_journal(company_id, owner=owner, date_from=start, date_to=end)
        if _wants_csv(request):
            return _csv(export.document_journal_csv(report), f"jurnal-{owner}-{start}-{end}.csv")
        return Response(
            {
                "owner": report.owner,
                "start_date": str(report.date_from),
                "end_date": str(report.date_to),
                "rows": [
                    {
                        "document_id": str(row.document_id),
                        "document_type": row.document_type,
                        "formatted_number": row.formatted_number,
                        "document_date": str(row.document_date),
                        "accounting_date": str(row.accounting_date),
                        "partner_name": row.partner_name,
                        "currency": row.currency,
                        "net": str(row.net),
                        "vat": str(row.vat),
                        "total": str(row.total),
                    }
                    for row in report.rows
                ],
                "totals": {
                    "net": str(report.total_net),
                    "vat": str(report.total_vat),
                    "total": str(report.total_amount),
                },
            }
        )


class CorrespondenceView(APIView):
    def get(self, request: Request, company_id: uuid.UUID) -> HttpResponse:
        """Turnover by (debit account, credit account) over `[from, to]`."""
        start, end = _window(request)
        report = correspondence(company_id, start, end)
        if _wants_csv(request):
            return _csv(
                export.correspondence_csv(report), f"rulaje-corespondente-{start}-{end}.csv"
            )
        return Response(
            {
                "start_date": str(report.start_date),
                "end_date": str(report.end_date),
                "cells": [
                    {
                        "debit_account_id": str(cell.debit_account_id),
                        "debit_code": cell.debit_code,
                        "credit_account_id": str(cell.credit_account_id),
                        "credit_code": cell.credit_code,
                        "amount": str(cell.amount),
                    }
                    for cell in report.cells
                ],
                "debit_totals": [
                    {
                        "account_id": str(t.account_id),
                        "account_code": t.account_code,
                        "amount": str(t.amount),
                    }
                    for t in report.debit_totals
                ],
                "credit_totals": [
                    {
                        "account_id": str(t.account_id),
                        "account_code": t.account_code,
                        "amount": str(t.amount),
                    }
                    for t in report.credit_totals
                ],
                "total": str(report.total),
                "lines_total": str(report.lines_total),
                "unassigned": str(report.unassigned),
            }
        )


class EntryDetailView(APIView):
    def get(self, request: Request, entry_id: uuid.UUID) -> Response:
        """One entry, whole: header and stamps, formulas, lines, origin (R13).

        404 with `api.not_found` for an entry this context cannot see -- absent,
        not forbidden (IZ-04), the same answer every other lookup gives.
        """
        detail = entry_detail(entry_id)
        if detail is None:
            raise NotFoundError(f"entry {entry_id} is not visible in this context")
        return Response(
            {
                "id": str(detail.id),
                "company_id": str(detail.company_id),
                "entry_number": detail.entry_number,
                "accounting_date": str(detail.accounting_date),
                "entry_type": detail.entry_type,
                "status": detail.status,
                "description": detail.description,
                "total_debit": str(detail.total_debit),
                "total_credit": str(detail.total_credit),
                "posted_at": detail.posted_at.isoformat() if detail.posted_at else None,
                "reverses_entry_id": _decimal(detail.reverses_entry_id),
                "reversed_by_entry_id": _decimal(detail.reversed_by_entry_id),
                "rule_ref": detail.rule_ref,
                "chart": detail.chart,
                "fiscal_effective_date": _decimal(detail.fiscal_effective_date),
                "lines": [
                    {
                        "line_number": line.line_number,
                        "account_id": str(line.account_id),
                        "account_code": line.account_code,
                        "name_ro": line.name_ro,
                        "debit": str(line.debit),
                        "credit": str(line.credit),
                        "currency": line.currency,
                        "amount_currency": str(line.amount_currency),
                        "exchange_rate": str(line.exchange_rate),
                        "document_date": str(line.document_date),
                        "rate_date": str(line.rate_date),
                        "description": line.description,
                        "dimensions": {name: str(value) for name, value in line.dimensions},
                    }
                    for line in detail.lines
                ],
                "formulas": [
                    {
                        "formula_number": formula.formula_number,
                        "debit_account_id": str(formula.debit_account_id),
                        "debit_code": formula.debit_code,
                        "credit_account_id": str(formula.credit_account_id),
                        "credit_code": formula.credit_code,
                        "amount": str(formula.amount),
                        "currency": formula.currency,
                        "amount_currency": str(formula.amount_currency),
                        "exchange_rate": str(formula.exchange_rate),
                        "vat_rate": _decimal(formula.vat_rate),
                        "vat_rate_key": formula.vat_rate_key,
                        "description": formula.description,
                        "slots": {name: str(value) for name, value in formula.slots},
                    }
                    for formula in detail.formulas
                ],
                "origin": (
                    {
                        "accounting_event_id": str(detail.origin.accounting_event_id),
                        "event_type": detail.origin.event_type,
                        "source_module": detail.origin.source_module,
                        "source_document_type": detail.origin.source_document_type,
                        "source_document_id": str(detail.origin.source_document_id),
                        "occurred_at": detail.origin.occurred_at.isoformat(),
                    }
                    if detail.origin
                    else None
                ),
            }
        )
