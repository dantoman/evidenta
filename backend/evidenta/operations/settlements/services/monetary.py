"""What is still open in foreign currency -- the settlement module's answer to the
revaluation's question (`A10`, ADR-097).

Registered as a provider with `accounting.currency.services.monetary_items` at
start-up (see `apps.py`), because `accounting` cannot import this module and the
open balances are this module's to know. The same figures the balances screen
shows, at a date: what a document was worth in its currency, less what was
settled against it on or before that day.

**Facts, not treatment.** Every open foreign-currency balance is reported with
its discriminators; which of them the standard recalculates is decided once, in
the revaluation service. One exclusion is applied here because it is this
module's knowledge and not the standard's arithmetic: an advance has no open
balance to revalue -- pct. 11 (wording in force from 2020) excludes advances
from the monetary items -- and the sale's nature is read from the sales module's
public view, never from its table (`D6`).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from django.db.models import F, Sum
from django.db.models.functions import Coalesce

from evidenta.accounting.currency.services.monetary_items import MonetaryItem
from evidenta.operations.purchases.services.documents import details_of as purchase_details
from evidenta.operations.sales.services.documents import details_of as sale_details
from evidenta.operations.settlements.models import Settlement, Side
from evidenta.platform.documents.services.lifecycle import posted_of_types
from evidenta.platform.documents.services.lines import totals_of_many
from evidenta.platform.tenancy.services.companies import functional_currency

SALE = "sales.document"
PURCHASE = "purchases.document"


def _settled_by(document_ids: list[uuid.UUID], as_of: date) -> dict[uuid.UUID, Decimal]:
    """Settled amounts in the document's currency, on or before the day, per document."""
    rows = (
        Settlement.objects.filter(settled_document_id__in=document_ids, settlement_date__lte=as_of)
        .values("settled_document_id")
        .annotate(total=Sum(Coalesce(F("amount_currency"), F("amount"))))
    )
    return {row["settled_document_id"]: Decimal(row["total"]) for row in rows}


def open_currency_items(company_id: uuid.UUID, as_of: date) -> tuple[MonetaryItem, ...]:
    """Posted invoices in a currency other than the company's, open on ``as_of``."""
    own = functional_currency(company_id)
    documents = [
        document
        for document in posted_of_types(company_id, (SALE, PURCHASE))
        if document.currency != own and document.accounting_date <= as_of
    ]
    if not documents:
        return ()
    ids = [document.id for document in documents]
    totals = totals_of_many(ids)
    settled = _settled_by(ids, as_of)
    sales = sale_details(d.id for d in documents if d.document_type == SALE)
    purchases = purchase_details(d.id for d in documents if d.document_type == PURCHASE)

    items: list[MonetaryItem] = []
    for document in documents:
        open_amount = totals[document.id].total - settled.get(document.id, Decimal(0))
        if open_amount <= 0 or document.partner_id is None:
            continue
        if document.document_type == SALE:
            sale = sales.get(document.id)
            if sale is None or sale.nature == "advance":
                continue
            resident, side = sale.partner_resident, Side.RECEIVABLE
        else:
            purchase = purchases.get(document.id)
            if purchase is None:
                continue
            resident, side = purchase.partner_resident, Side.PAYABLE
        denomination = document.contract_denomination
        if denomination is None:
            # A document in currency opened before the column existed. It cannot
            # be revalued without its discriminator, and a default here would be
            # the silent choice ADR-057 refuses; skipped and visible in the list
            # of open items, where the accountant sees it has no denomination.
            continue
        items.append(
            MonetaryItem(
                document_id=document.id,
                document_type=document.document_type,
                side=str(side),
                partner_id=document.partner_id,
                partner_resident=resident,
                contract_denomination=str(denomination),
                currency=document.currency,
                amount_currency=open_amount,
                document_rate=Decimal(document.exchange_rate),
            )
        )
    return tuple(items)
