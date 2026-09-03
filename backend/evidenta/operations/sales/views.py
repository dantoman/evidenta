"""Sales invoices over HTTP -- open a draft, price it, issue it.

**Issuing is one call**, and that is the design rather than a shortcut: validating
without posting leaves a numbered document with no accounting effect, and two
calls that must happen in order are two chances to make only the first. The
service does both in the order the acts impose.

**`Idempotency-Key` is not read here** (`C9`) and the reason is worth stating: the
key that matters is on the accounting event, keyed by the document (`R19`,
ADR-073 §8). A second issue of the same invoice returns the first result, which
is what the header would have bought -- so a header would be a second mechanism
for a property the event already has.

**The two discriminators are required by the serializer**, not defaulted. What is
sold and whether the counterparty is a resident each select an account, and
neither can be derived from anything this system holds.

**A draft is rewritten in full or thrown away** (by the owner's instruction,
2026-09-02: an invoice may sit as a draft, be edited, and be issued later). `PUT`
on the document takes the body creation takes -- header and positions together,
in the one transaction the request already is (`R3`), so a refused line leaves
the draft as it was rather than half-changed. `DELETE` is for a draft only;
past draft both are refused with `documents.not_editable`, by the service and
by the trigger under it, and the correction is a reversal.

**The savepoint around header-then-lines is not redundant.** The request runs in
a transaction (`R3`), but a refusal raised by a service is rendered as a
response *inside* it -- by DRF's handler here, by `ApiErrorMiddleware` for plain
views -- so the request ends normally and commits whatever was written before
the refusal. Measured: without the block, a rewrite whose second line is refused
kept its new header over its old positions. The block makes the refusal undo the
step before it; whether every refused request should roll back is a platform
question, noted in `PROGRESS.md`.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.http import HttpResponse
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from evidenta.operations.sales.models import RevenueKind, SaleNature, SalesDocument
from evidenta.operations.sales.services.documents import delete_sale, open_sale, replace_sale
from evidenta.operations.sales.services.issuing import issue_and_post
from evidenta.operations.sales.services.lines import Position, write_lines
from evidenta.operations.sales.services.printing import invoice_printable
from evidenta.platform.capabilities.services.profile import active_profile
from evidenta.platform.documents.errors import DocumentNotFoundError
from evidenta.platform.documents.printing import pdf_response
from evidenta.platform.documents.services.lifecycle import get_document
from evidenta.platform.documents.services.lines import (
    DocumentTotals,
    PositionView,
    lines_of,
    totals_of,
    totals_of_many,
)
from evidenta.platform.rls.context import MissingTenantContextError, current_context


class LineSerializer(serializers.Serializer[dict[str, Any]]):
    description = serializers.CharField()
    quantity = serializers.DecimalField(max_digits=20, decimal_places=6)
    unit_price = serializers.DecimalField(max_digits=20, decimal_places=4)
    #: Stated on every line, never defaulted (ADR-089): a line issued under a
    #: treatment nobody chose is a VAT amount nobody chose. The service decides
    #: whether the company may state it on the document's date.
    vat_regime_code = serializers.CharField(max_length=64)


class SaleSerializer(serializers.Serializer[dict[str, Any]]):
    partner_id = serializers.UUIDField()
    document_date = serializers.DateField()
    accounting_date = serializers.DateField(required=False, allow_null=True)
    #: Required over the wire although the service defaults it, and the asymmetry
    #: is deliberate: forgetting the field would make a credit note an invoice,
    #: which recognises revenue instead of a return. The service's default serves
    #: callers inside the process, which state the nature by choosing the function
    #: they call; an HTTP body states it or is refused (ADR-073 §7).
    nature = serializers.ChoiceField(choices=SaleNature.values)
    #: No default on either: both select an account, and neither is derivable.
    revenue_kind = serializers.ChoiceField(choices=RevenueKind.values)
    partner_resident = serializers.BooleanField()
    #: The document's currency, the company's own when absent. In another
    #: currency the denomination is required and the rate is the official rate
    #: of the invoice's date, resolved by the service (ADR-097); neither is
    #: rewritten on a draft -- a draft in the wrong currency is deleted.
    currency = serializers.CharField(
        max_length=3, required=False, allow_blank=True, allow_null=True
    )
    contract_denomination = serializers.ChoiceField(
        choices=["foreign_currency", "conventional_units"],
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    external_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    lines = LineSerializer(many=True)


class LinesSerializer(serializers.Serializer[dict[str, Any]]):
    lines = LineSerializer(many=True)


class SalesListView(APIView):
    def get(self, request: Request, company_id: uuid.UUID) -> Response:
        rows = list(
            SalesDocument.objects.filter(company_id=company_id)
            .select_related("document")
            .order_by("-document__document_date", "-document__created_at")
        )
        # The register shows each invoice's total, and the screen adds nothing
        # up (`C19`): the figure travels with the row, summed once for the list.
        totals = totals_of_many(row.document_id for row in rows)
        return Response([_rendered(row, totals[row.document_id]) for row in rows])

    def post(self, request: Request, company_id: uuid.UUID) -> Response:
        payload = SaleSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)

        with transaction.atomic():
            document_id = open_sale(company_id=company_id, **_header(data), **_currency(data))
            _write_lines(document_id, data["lines"])
        return Response(_detail(document_id), status=201)


class SalesDetailView(APIView):
    def get(self, request: Request, document_id: uuid.UUID) -> Response:
        return Response(_detail(document_id))

    def put(self, request: Request, document_id: uuid.UUID) -> Response:
        """Rewrite a draft in full: the same body as creation, on the same document."""
        payload = SaleSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        with transaction.atomic():
            replace_sale(document_id, **_header(data))
            # After the header, on purpose: the positions are priced on the date
            # the header now bears, and admitted under the status on that day.
            _write_lines(document_id, data["lines"])
        return Response(_detail(document_id))

    def delete(self, request: Request, document_id: uuid.UUID) -> Response:
        delete_sale(document_id)
        return Response(status=204)


class SalesLinesView(APIView):
    def put(self, request: Request, document_id: uuid.UUID) -> Response:
        payload = LinesSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        _write_lines(document_id, list(payload.validated_data["lines"]))
        return Response(_detail(document_id))


class SalesIssuanceView(APIView):
    """Validate and post, in that order, in one call."""

    def post(self, request: Request, document_id: uuid.UUID) -> Response:
        context = _context()
        document = get_document(document_id)
        result = issue_and_post(
            document_id=document_id,
            actor_user_id=context.user_id,
            request_id=context.request_id,
            capability_snapshot=active_profile(
                document.company_id, document.accounting_date
            ).as_snapshot(),
        )
        payload = _detail(document_id)
        payload["posting"] = {
            "accounting_event_id": str(result.accounting_event_id),
            "journal_entry_id": (str(result.journal_entry_id) if result.journal_entry_id else None),
            "posted_now": result.posted_now,
        }
        return Response(payload)


class SalesInvoicePdfView(APIView):
    """The fiscal invoice as PDF -- `C22`, ADR-095.

    A plain GET the browser opens from a link: inline, named by the number.
    Only a validated or posted invoice has a number to print; a draft is refused
    with `sales.not_printable`. Absent and not-visible are one answer, 404.
    """

    def get(self, request: Request, document_id: uuid.UUID) -> HttpResponse:
        return pdf_response(invoice_printable(document_id))


def _currency(data: dict[str, Any]) -> dict[str, Any]:
    """The currency and its denomination, read once, for creation only: the
    header's currency is fixed when the draft opens (ADR-097)."""
    return {
        "currency": (data.get("currency") or "").strip().upper() or None,
        "contract_denomination": data.get("contract_denomination") or None,
    }


def _header(data: dict[str, Any]) -> dict[str, Any]:
    """The validated body, as the two header services take it. One reading of
    the body for both routes, so creating and rewriting cannot disagree on what a
    blank `external_number` means."""
    return {
        "partner_id": data["partner_id"],
        "document_date": data["document_date"],
        "accounting_date": data.get("accounting_date"),
        "nature": data["nature"],
        "revenue_kind": data["revenue_kind"],
        "partner_resident": data["partner_resident"],
        "external_number": data.get("external_number") or None,
        "notes": data.get("notes") or None,
    }


def _write_lines(document_id: uuid.UUID, lines: list[dict[str, Any]]) -> None:
    write_lines(
        document_id,
        [
            Position(
                description=line["description"],
                quantity=Decimal(line["quantity"]),
                unit_price=Decimal(line["unit_price"]),
                vat_regime_code=line["vat_regime_code"],
            )
            for line in lines
        ],
    )


def _detail(document_id: uuid.UUID) -> dict[str, Any]:
    row = SalesDocument.objects.filter(document_id=document_id).select_related("document").first()
    if row is None:
        # Absent and not-visible are one answer, 404 (IZ-04): a 403 here would
        # say "exists, not yours" over a range of identifiers.
        raise DocumentNotFoundError(f"document {document_id} is not a sale visible in this context")
    payload = _rendered(row, totals_of(document_id))
    # The positions travel with the detail only: the register is a list of
    # totals, and the form that edits a draft needs what was typed, not only
    # what was derived from it.
    payload["lines"] = [_line(line) for line in lines_of(document_id)]
    return payload


def _line(line: PositionView) -> dict[str, Any]:
    return {
        "line_no": line.line_no,
        "description": line.description,
        # Quantity and price go back to be edited, so the storage scale comes
        # off: `3.000000` is what the column holds, `3` is what was typed. The
        # amounts keep their scale -- they are money, and shown as such.
        "quantity": _entered(line.quantity),
        "unit_price": _entered(line.unit_price),
        "vat_regime_code": line.vat_regime_code,
        "net_amount": str(line.net_amount),
        "vat_amount": str(line.vat_amount),
        "total_amount": str(line.total_amount),
    }


def _entered(value: Decimal) -> str:
    # `format(..., "f")` rather than `str(...)`: `normalize()` writes 100 as
    # `1E+2`, which is not what anybody typed either.
    return format(value.normalize(), "f")


def _rendered(row: SalesDocument, totals: DocumentTotals) -> dict[str, Any]:
    document = row.document
    return {
        "id": str(document.id),
        "formatted_number": document.formatted_number,
        "document_date": str(document.document_date),
        "accounting_date": str(document.accounting_date),
        "state": document.state,
        "partner_id": str(document.partner_id) if document.partner_id else None,
        "currency": document.currency,
        "exchange_rate": str(document.exchange_rate),
        "contract_denomination": document.contract_denomination,
        "nature": row.nature,
        "revenue_kind": row.revenue_kind,
        "partner_resident": row.partner_resident,
        "totals": {
            "net": str(totals.net),
            "vat": str(totals.vat),
            "total": str(totals.total),
        },
    }


def _context() -> Any:
    context = current_context()
    if context is None:
        raise MissingTenantContextError("no tenant context on this request")
    return context
