"""Opening and converting sales-side documents.

Each function does two things and no more: it asks the document core for a
header, and it writes the row that carries what is specific to the type. Both in
one transaction, because a header with no extension row is a document whose type
the schema cannot answer for.

Everything else -- numbering, validation, cancellation, history -- is the core's,
and is not re-implemented here. That is the whole reason the core exists: four
copies of "what state is this in" become four answers within a year.

**Identifiers cross the seam, not rows.** Every function here returns the
document's id, and the core's services take one. A module that passed a
`Document` around would have to import the document core's models to say so in a
signature, which is `D6` -- and the rule is not about the import, it is about
what having the class lets you do next.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from django.db import transaction

from evidenta.operations.sales.models import (
    CustomerOrder,
    ProformaDocument,
    SaleNature,
    SalesDocument,
)
from evidenta.operations.sales.types import CUSTOMER_ORDER, PROFORMA, SALES_DOCUMENT
from evidenta.platform.documents.services.conversion import convert
from evidenta.platform.documents.services.lifecycle import open_draft


@transaction.atomic
def open_sale(
    *,
    company_id: uuid.UUID,
    partner_id: uuid.UUID,
    document_date: date,
    nature: str = SaleNature.DELIVERY,
    accounting_date: date | None = None,
    currency: str | None = None,
    exchange_rate: Decimal | None = None,
    external_number: str | None = None,
    notes: str | None = None,
) -> uuid.UUID:
    """Start a sale as a draft. Delivery or advance, one type either way."""
    document = open_draft(
        company_id=company_id,
        document_type=SALES_DOCUMENT,
        document_date=document_date,
        accounting_date=accounting_date,
        partner_id=partner_id,
        currency=currency,
        exchange_rate=exchange_rate,
        external_number=external_number,
        notes=notes,
    )
    SalesDocument.objects.create(
        document=document,
        tenant_id=document.tenant_id,
        company_id=document.company_id,
        nature=nature,
    )
    return document.id


@transaction.atomic
def open_proforma(
    *,
    company_id: uuid.UUID,
    partner_id: uuid.UUID,
    document_date: date,
    valid_until: date | None = None,
    currency: str | None = None,
    exchange_rate: Decimal | None = None,
    notes: str | None = None,
) -> uuid.UUID:
    document = open_draft(
        company_id=company_id,
        document_type=PROFORMA,
        document_date=document_date,
        partner_id=partner_id,
        currency=currency,
        exchange_rate=exchange_rate,
        notes=notes,
    )
    ProformaDocument.objects.create(
        document=document,
        tenant_id=document.tenant_id,
        company_id=document.company_id,
        valid_until=valid_until,
    )
    return document.id


@transaction.atomic
def open_customer_order(
    *,
    company_id: uuid.UUID,
    partner_id: uuid.UUID,
    document_date: date,
    requested_delivery_date: date | None = None,
    currency: str | None = None,
    exchange_rate: Decimal | None = None,
    notes: str | None = None,
) -> uuid.UUID:
    document = open_draft(
        company_id=company_id,
        document_type=CUSTOMER_ORDER,
        document_date=document_date,
        partner_id=partner_id,
        currency=currency,
        exchange_rate=exchange_rate,
        notes=notes,
    )
    CustomerOrder.objects.create(
        document=document,
        tenant_id=document.tenant_id,
        company_id=document.company_id,
        requested_delivery_date=requested_delivery_date,
    )
    return document.id


@transaction.atomic
def convert_to_sale(
    source_id: uuid.UUID,
    *,
    document_date: date,
    nature: str = SaleNature.DELIVERY,
    accounting_date: date | None = None,
    exchange_rate: Decimal | None = None,
) -> uuid.UUID:
    """Turn a proforma or a customer order into a sale, as a draft.

    Which sources are allowed is declared by the type, not decided here -- the
    core refuses a route the registry does not list. The positions come across
    with `source_line_id` on each one, so what was offered or ordered can be
    compared to what was invoiced without anybody re-keying either.
    """
    sale = convert(
        source_id,
        target_type=SALES_DOCUMENT,
        document_date=document_date,
        accounting_date=accounting_date,
        exchange_rate=exchange_rate,
    )
    SalesDocument.objects.create(
        document=sale,
        tenant_id=sale.tenant_id,
        company_id=sale.company_id,
        nature=nature,
    )
    return sale.id
