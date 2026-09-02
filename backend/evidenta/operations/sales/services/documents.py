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
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction

from evidenta.operations.sales.models import (
    CustomerOrder,
    ProformaDocument,
    RevenueKind,
    SaleNature,
    SalesDocument,
)
from evidenta.operations.sales.types import CUSTOMER_ORDER, PROFORMA, SALES_DOCUMENT
from evidenta.platform.api.errors import ApiError
from evidenta.platform.documents.services.conversion import convert
from evidenta.platform.documents.services.lifecycle import open_draft


class SaleMalformedError(ApiError):
    code = "sales.malformed"
    status = 422


@transaction.atomic
def open_sale(
    *,
    company_id: uuid.UUID,
    partner_id: uuid.UUID,
    document_date: date,
    revenue_kind: str,
    partner_resident: bool,
    nature: str = SaleNature.DELIVERY,
    accounting_date: date | None = None,
    currency: str | None = None,
    exchange_rate: Decimal | None = None,
    external_number: str | None = None,
    notes: str | None = None,
    rate_term: str = "payment_date",
) -> uuid.UUID:
    """Start a sale as a draft. Delivery or advance, one type either way.

    `revenue_kind` and `partner_resident` are required and have no defaults
    (ADR-073 sections 2 and 3). Both select an account at posting time, and
    neither can be derived: `partner` carries no residence, and what is being sold
    is not a property of the counterparty. A default would answer both questions
    in the direction that looks harmless -- services, resident -- and be wrong
    silently.
    """
    if revenue_kind not in RevenueKind.values:
        raise SaleMalformedError(
            f"{revenue_kind!r} is not what a sale can recognise; the three are "
            f"{', '.join(RevenueKind.values)}"
        )
    if not isinstance(partner_resident, bool):
        raise SaleMalformedError(
            "a sale says whether the counterparty is a resident: the receivable "
            "account differs, and nothing in the partner card answers it"
        )
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
        rate_term=rate_term,
    )
    SalesDocument.objects.create(
        document=document,
        tenant_id=document.tenant_id,
        company_id=document.company_id,
        nature=nature,
        revenue_kind=revenue_kind,
        partner_resident=partner_resident,
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
    rate_term: str = "payment_date",
) -> uuid.UUID:
    document = open_draft(
        company_id=company_id,
        document_type=PROFORMA,
        document_date=document_date,
        partner_id=partner_id,
        currency=currency,
        exchange_rate=exchange_rate,
        notes=notes,
        rate_term=rate_term,
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
    rate_term: str = "payment_date",
) -> uuid.UUID:
    document = open_draft(
        company_id=company_id,
        document_type=CUSTOMER_ORDER,
        document_date=document_date,
        partner_id=partner_id,
        currency=currency,
        exchange_rate=exchange_rate,
        notes=notes,
        rate_term=rate_term,
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
    revenue_kind: str,
    partner_resident: bool,
    nature: str = SaleNature.DELIVERY,
    accounting_date: date | None = None,
    exchange_rate: Decimal | None = None,
) -> uuid.UUID:
    """Turn a proforma or a customer order into a sale, as a draft.

    The two discriminators are asked for here as well, and a proforma cannot
    supply them: an offer says what is offered and at what price, not which
    revenue account recognises it or whether the customer is a resident. Carrying
    them over from a source that does not have them would be inventing them.

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
        revenue_kind=revenue_kind,
        partner_resident=partner_resident,
    )
    return sale.id


@dataclass(frozen=True, slots=True)
class SaleView:
    """What another module may know about a sale without reading its table."""

    nature: str
    revenue_kind: str
    partner_resident: bool


def details_of(document_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, SaleView]:
    """The sales-side facts of many documents at once, for a register.

    Public for the reason `residence_of` is, and batched because a register
    lists a month: one query for the window, not one per row. Ids that are not
    sales are absent from the answer rather than refused -- a register asks
    about a family and reads what the family has.
    """
    rows = SalesDocument.objects.filter(document_id__in=list(document_ids)).values(
        "document_id", "nature", "revenue_kind", "partner_resident"
    )
    return {
        row["document_id"]: SaleView(
            nature=str(row["nature"]),
            revenue_kind=str(row["revenue_kind"]),
            partner_resident=bool(row["partner_resident"]),
        )
        for row in rows
    }


def residence_of(document_id: uuid.UUID) -> bool:
    """Whether the customer on this invoice was recorded as a resident.

    Public because settlement needs it and must not read this table (`D6`), and
    because it must not ask the question a second time: residence was already
    required once, from the person who knew (ADR-073 §2). Asking again would
    invite two answers about one invoice.
    """
    resident = (
        SalesDocument.objects.filter(document_id=document_id)
        .values_list("partner_resident", flat=True)
        .first()
    )
    if resident is None:
        raise SaleMalformedError(f"document {document_id} is not a sale")
    return bool(resident)
