"""The VAT registers on the VAT fiscal period -- `F2.A6`, second slice (ADR-090).

Two registers, one shape: what a company delivered and what it procured in one
VAT fiscal period, document by document, split by VAT treatment, with the
totals the declaration will read. Built **on the VAT period** (`VatPeriod`,
ADR-039 §7), never on the accounting month: the two coincide in most months and
part ways at a cancellation, and a register keyed on the wrong container is
unreportable exactly then.

**What it is not, said here and on the screen.** Codul fiscal art. 118 prescribes
registers of deliveries and of procurements; their prescribed form has not been
read (`F2.X2 (c)`, the text is behind a paywall). This is the register of the
company's documents with their VAT, on the fiscal period, with every figure the
prescribed one asks for that this system holds. Calling it *Registrul de
livrări* before the form is read would produce the non-conforming artefact `C33`
is about, so the export's filename says which side and the screen says what it
is.

**It reads no other module's table.** Documents come through the document core's
listing primitives, the sales-side and purchase-side facts through each module's
public batch view, partner names through `masterdata.partners`, and whether a
purchase's VAT was deductible through the **event the engine recorded** --
`accounting.events`, the one accounting surface an operational module may read
(`D3`). Re-deriving deductibility from today's registration table would be a
second implementation of the rule, and one that moves when a registration is
corrected; the event is stamped with the status it was read from (ADR-088).

**Signs.** A credit note enters the register of deliveries with negative
figures: the register's VAT total then equals the collected-VAT account's net
turnover for the month, which is the criterion `F2.A6` sets. A document that
mixes rates appears once per rate in the export and once with its slices in the
API, so the totals by rate add up without a second grouping on the client.

**Posted, and the validated-but-unposted counted beside them.** A validated
invoice is a numbered legal document whether or not its posting succeeded. The
rows are the posted ones -- what the ledger holds -- and the register says how
many issued documents of the period are not in it yet, so "the register agrees
with the ledger" cannot be mistaken for "every issued invoice is in the
register".
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from evidenta.accounting.events.services.lineage import posted_payloads_of
from evidenta.accounting.periods.services.vat import vat_period_for
from evidenta.masterdata.partners.services.directory import legal_names_for
from evidenta.operations.purchases.services.documents import details_of as purchase_details_of
from evidenta.operations.sales.services.documents import details_of as sale_details_of
from evidenta.platform.api.errors import ApiError
from evidenta.platform.documents.registry import types_owned_by
from evidenta.platform.documents.services.csv import csv_document
from evidenta.platform.documents.services.lifecycle import (
    confirmed_of_types,
    posted_of_types,
)
from evidenta.platform.documents.services.lines import VatSlice, vat_breakdown_of_many

SALES = "sales"
PURCHASES = "purchases"
SIDES = (SALES, PURCHASES)

#: The document type a purchase posts under -- the key the events were recorded
#: with. Named here rather than imported from `purchases`: it is the vocabulary
#: of the event registry (ADR-038), and the register reads events.
PURCHASE_DOCUMENT_TYPE = "purchases.document"

#: The nature that reverses a delivery in the register of deliveries.
CREDIT_NOTE = "return"


class UnknownRegisterSideError(ApiError):
    code = "tax.unknown_register_side"
    status = 400


class _DocumentLike(Protocol):
    """The columns of the core's document this register reads.

    A protocol rather than the model: `D6` keeps another module's `models` out
    of a service, and what the register needs is six columns, not a table.
    """

    id: uuid.UUID
    document_type: str
    formatted_number: str | None
    document_date: date
    accounting_date: date
    partner_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class RegisterSlice:
    """The part of one document that shares a VAT treatment, signed."""

    vat_regime_code: str
    vat_rate_key: str | None
    vat_rate: Decimal
    net: Decimal
    vat: Decimal


@dataclass(frozen=True, slots=True)
class RegisterRow:
    document_id: uuid.UUID
    document_type: str
    formatted_number: str | None
    document_date: date
    accounting_date: date
    partner_id: uuid.UUID | None
    partner_name: str
    #: `invoice`, `credit_note` or `supplier_invoice` -- what the row is, so the
    #: sign of its figures is explained rather than guessed.
    kind: str
    supplier_document_number: str | None
    supplier_document_date: date | None
    #: Purchases only: whether the VAT was taken to 2252 (`True`), borne in the
    #: cost (`False`), or posted before the engine recorded the answer (`None`).
    deductible: bool | None
    slices: tuple[RegisterSlice, ...]
    net: Decimal
    vat: Decimal
    total: Decimal


@dataclass(frozen=True, slots=True)
class RegimeTotal:
    vat_regime_code: str
    vat_rate_key: str | None
    vat_rate: Decimal
    net: Decimal
    vat: Decimal


@dataclass(frozen=True, slots=True)
class VatRegister:
    company_id: uuid.UUID
    side: str
    period_id: uuid.UUID
    start_date: date
    end_date: date
    kind: str
    rows: tuple[RegisterRow, ...]
    by_regime: tuple[RegimeTotal, ...]
    total_net: Decimal
    total_vat: Decimal
    total_amount: Decimal
    #: Purchases only: the VAT that sits in cost rather than in 2252. The
    #: deductible-VAT account's turnover is `total_vat - non_deductible_vat`.
    non_deductible_vat: Decimal
    #: Validated documents of the period that have not reached the ledger.
    unposted: int


def vat_register(company_id: uuid.UUID, *, side: str, on: date) -> VatRegister:
    """The register of one side, for the VAT fiscal period covering ``on``.

    ``on`` names a day and the period is looked up, never invented: a company
    without a VAT period over that day is not registered over it, or has not
    opened its periods, and `vat_period_for` says which in its refusal.

    Documents are placed by their **document date** -- the date the invoice
    bears, which is the date the register of deliveries carries -- rather than
    by the accounting date. The two differ on purpose (ADR-039 §9), and a
    register keyed on the posting date would move an invoice to the month
    somebody typed it in. Recorded as a choice in ADR-090, with its trigger.
    """
    if side not in SIDES:
        raise UnknownRegisterSideError(f"{side!r} is not a register side; {list(SIDES)} are")

    period = vat_period_for(company_id, on)
    types = types_owned_by(side)

    def in_period(document_date: date) -> bool:
        return period.start_date <= document_date <= period.end_date

    posted = [d for d in posted_of_types(company_id, types) if in_period(d.document_date)]
    unposted = sum(1 for d in confirmed_of_types(company_id, types) if in_period(d.document_date))

    ids = [document.id for document in posted]
    names = legal_names_for([d.partner_id for d in posted if d.partner_id is not None])
    breakdown = vat_breakdown_of_many(ids)

    rows: list[RegisterRow] = []
    if side == SALES:
        sales = sale_details_of(ids)
        for document in posted:
            sale = sales.get(document.id)
            credit_note = sale is not None and sale.nature == CREDIT_NOTE
            sign = Decimal(-1) if credit_note else Decimal(1)
            rows.append(
                _row(
                    document,
                    names,
                    kind="credit_note" if credit_note else "invoice",
                    sign=sign,
                    slices=breakdown[document.id],
                    supplier_document_number=None,
                    supplier_document_date=None,
                    deductible=None,
                )
            )
    else:
        purchases = purchase_details_of(ids)
        payloads = posted_payloads_of(PURCHASE_DOCUMENT_TYPE, ids)
        for document in posted:
            purchase = purchases.get(document.id)
            recorded = payloads.get(document.id, {}).get("vat_deductible")
            rows.append(
                _row(
                    document,
                    names,
                    kind="supplier_invoice",
                    sign=Decimal(1),
                    slices=breakdown[document.id],
                    supplier_document_number=(
                        purchase.supplier_document_number if purchase is not None else None
                    ),
                    supplier_document_date=(
                        purchase.supplier_document_date if purchase is not None else None
                    ),
                    deductible=recorded if isinstance(recorded, bool) else None,
                )
            )

    rows.sort(key=lambda row: (row.document_date, row.formatted_number or ""))

    return VatRegister(
        company_id=company_id,
        side=side,
        period_id=period.id,
        start_date=period.start_date,
        end_date=period.end_date,
        kind=str(period.kind),
        rows=tuple(rows),
        by_regime=_by_regime(rows),
        total_net=sum((row.net for row in rows), Decimal(0)),
        total_vat=sum((row.vat for row in rows), Decimal(0)),
        total_amount=sum((row.total for row in rows), Decimal(0)),
        non_deductible_vat=sum((row.vat for row in rows if row.deductible is False), Decimal(0)),
        unposted=unposted,
    )


def _row(
    document: _DocumentLike,
    names: dict[uuid.UUID, str],
    *,
    kind: str,
    sign: Decimal,
    slices: Sequence[VatSlice],
    supplier_document_number: str | None,
    supplier_document_date: date | None,
    deductible: bool | None,
) -> RegisterRow:
    signed = tuple(
        RegisterSlice(
            vat_regime_code=piece.vat_regime_code,
            vat_rate_key=piece.vat_rate_key,
            vat_rate=piece.vat_rate,
            net=sign * piece.net,
            vat=sign * piece.vat,
        )
        for piece in slices
    )
    net = sum((piece.net for piece in signed), Decimal(0))
    vat = sum((piece.vat for piece in signed), Decimal(0))
    partner_id = document.partner_id
    return RegisterRow(
        document_id=document.id,
        document_type=str(document.document_type),
        formatted_number=document.formatted_number,
        document_date=document.document_date,
        accounting_date=document.accounting_date,
        partner_id=partner_id,
        partner_name=names.get(partner_id, "") if partner_id is not None else "",
        kind=kind,
        supplier_document_number=supplier_document_number,
        supplier_document_date=supplier_document_date,
        deductible=deductible,
        slices=signed,
        net=net,
        vat=vat,
        total=net + vat,
    )


def _by_regime(rows: Iterable[RegisterRow]) -> tuple[RegimeTotal, ...]:
    """The totals the declaration reads: per treatment and rate, signed sums."""
    folded: dict[tuple[str, str | None, Decimal], RegimeTotal] = {}
    for row in rows:
        for piece in row.slices:
            key = (piece.vat_regime_code, piece.vat_rate_key, piece.vat_rate)
            current = folded.get(key)
            folded[key] = RegimeTotal(
                vat_regime_code=piece.vat_regime_code,
                vat_rate_key=piece.vat_rate_key,
                vat_rate=piece.vat_rate,
                net=(current.net if current else Decimal(0)) + piece.net,
                vat=(current.vat if current else Decimal(0)) + piece.vat,
            )
    return tuple(
        sorted(folded.values(), key=lambda total: (-total.vat_rate, total.vat_regime_code))
    )


# --- export --------------------------------------------------------------------

#: What a row is called in the export -- Romanian, as everything in a register
#: (`C33`), and from here rather than from the interface's resource file.
KIND_RO = {
    "invoice": "Factură",
    "credit_note": "Notă de credit",
    "supplier_invoice": "Factură primită",
}


def vat_register_csv(register: VatRegister) -> bytes:
    """The register, one line per document and VAT treatment, totals at the end.

    A document with two rates is two lines with the same number: that is how a
    register is read, and how its totals by rate are checked by hand. The
    counterparty column carries the legal name (`C39`).
    """
    headers: tuple[str, ...]
    lines: list[Sequence[object]]
    blank: tuple[object, ...]
    if register.side == SALES:
        headers = (
            "Data documentului",
            "Număr",
            "Cumpărător",
            "Fel",
            "Regim TVA",
            "Cota",
            "Fără TVA",
            "TVA",
            "Total",
        )
        lines = [
            (
                row.document_date,
                row.formatted_number,
                row.partner_name,
                KIND_RO.get(row.kind, row.kind),
                piece.vat_regime_code,
                piece.vat_rate,
                piece.net,
                piece.vat,
                piece.net + piece.vat,
            )
            for row in register.rows
            for piece in row.slices
        ]
        blank = ("", "", "", "")
    else:
        headers = (
            "Data înregistrării",
            "Numărul nostru",
            "Numărul furnizorului",
            "Data furnizorului",
            "Furnizor",
            "Deductibil",
            "Regim TVA",
            "Cota",
            "Fără TVA",
            "TVA",
            "Total",
        )
        lines = [
            (
                row.document_date,
                row.formatted_number,
                row.supplier_document_number,
                row.supplier_document_date,
                row.partner_name,
                _deductible_ro(row.deductible),
                piece.vat_regime_code,
                piece.vat_rate,
                piece.net,
                piece.vat,
                piece.net + piece.vat,
            )
            for row in register.rows
            for piece in row.slices
        ]
        blank = ("", "", "", "", "", "")

    totals: list[Sequence[object]] = [
        (
            *blank,
            f"Total {total.vat_regime_code}",
            total.vat_rate,
            total.net,
            total.vat,
            total.net + total.vat,
        )
        for total in register.by_regime
    ]
    totals.append(
        (*blank, "Total", "", register.total_net, register.total_vat, register.total_amount)
    )
    return csv_document(headers, [*lines, *totals])


def _deductible_ro(value: bool | None) -> str:
    if value is None:
        return ""
    return "da" if value else "nu"
