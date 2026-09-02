"""The document journal (*jurnalul documentelor*) -- F1.8, the piece that waited.

The report was blocked by its own definition. ADR-053 calls these journals "per
document by definition", and until 2026-08-31 nothing in the product posted a
document -- so the report had nothing to list, and building it would have been
building against an empty table.

**What it is, and what it deliberately is not.** This lists a company's documents
of one family over a window, with the amounts the documents carry and the totals
computed on the server (`C19`). It is **not** the statutory VAT register: that has
a prescribed form in an act nobody here has read (`F2.X2 (c)`) and lives on the
VAT fiscal period, not on the accounting one. Since ADR-089 the VAT column here is
what the lines carry -- and, per month, it equals the turnover of the collected-VAT
account, which is the first half of the `F2.A6` done criterion. Calling this one
*Registrul de livrări* would still produce exactly the non-conforming artefact
`C33` is about.

**It reads no operations table.** The family is named by its *owner module*, and
`platform.documents.registry` answers which type codes that is -- so `accounting`
never learns that `sales` calls its document `sales.document`. The rows come from
the document core's own services, which every layer may use.

**Included by the accounting date**, the same column the trial balance sums, so a
journal's total and the register's turnover answer the same question. The document
date is carried too, because the two differ on purpose (ADR-039 §9) and a journal
that showed one of them would be read as showing the other.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from evidenta.masterdata.partners.services.directory import legal_names_for
from evidenta.platform.documents.registry import types_owned_by
from evidenta.platform.documents.services.lifecycle import posted_of_types
from evidenta.platform.documents.services.lines import totals_of


@dataclass(frozen=True, slots=True)
class JournalRow:
    document_id: uuid.UUID
    document_type: str
    formatted_number: str | None
    document_date: date
    accounting_date: date
    partner_id: uuid.UUID | None
    #: The **legal** name (`C39`). Empty when the row carries no counterparty
    #: or the reader cannot see it -- an empty cell says that honestly, and an
    #: identifier printed in its place would say nothing at all.
    partner_name: str
    currency: str
    net: Decimal
    vat: Decimal
    total: Decimal


@dataclass(frozen=True, slots=True)
class DocumentJournal:
    company_id: uuid.UUID
    owner: str
    date_from: date
    date_to: date
    rows: tuple[JournalRow, ...]
    #: Added on the server, never in the client (`C19`). Three totals rather than
    #: one, because a journal whose VAT column is empty says something -- that no
    #: document in the window carried any -- and a single total would hide it.
    total_net: Decimal
    total_vat: Decimal
    total_amount: Decimal


def document_journal(
    company_id: uuid.UUID,
    *,
    owner: str,
    date_from: date,
    date_to: date,
) -> DocumentJournal:
    """One family's posted documents in a window, with the server's totals."""
    types = types_owned_by(owner)
    documents = [
        document
        for document in posted_of_types(company_id, types)
        if date_from <= document.accounting_date <= date_to
    ]
    # One lookup for the whole window, not one per row.
    names = legal_names_for([d.partner_id for d in documents if d.partner_id is not None])

    rows: list[JournalRow] = []
    for document in documents:
        totals = totals_of(document.id)
        rows.append(
            JournalRow(
                document_id=document.id,
                document_type=document.document_type,
                formatted_number=document.formatted_number,
                document_date=document.document_date,
                accounting_date=document.accounting_date,
                partner_id=document.partner_id,
                partner_name=names.get(document.partner_id, "") if document.partner_id else "",
                currency=document.currency,
                net=totals.net,
                vat=totals.vat,
                total=totals.total,
            )
        )

    return DocumentJournal(
        company_id=company_id,
        owner=owner,
        date_from=date_from,
        date_to=date_to,
        rows=tuple(rows),
        total_net=sum((row.net for row in rows), Decimal(0)),
        total_vat=sum((row.vat for row in rows), Decimal(0)),
        total_amount=sum((row.total for row in rows), Decimal(0)),
    )
