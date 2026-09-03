"""What is open in foreign currency on a day -- the input of a revaluation.

`accounting` cannot ask `operations` (the graph runs one way, CLAUDE.md section
3), and the open balances of invoices are the settlement module's to know. So the
question is asked the way the Posting Engine asks for handlers (ADR-038): the
module that knows **registers** a provider here at start-up, and the revaluation
service calls every provider it finds. Today there is one -- receivables and
payables from `operations/settlements`. Cash and bank in foreign currency will
register a second when the treasury holds currency (step 5c); none exists yet,
and the revaluation says so rather than assuming zero.

**A provider states facts, not treatment.** It reports every open foreign-currency
balance with its discriminators; whether an item is *recalculated* at the
reporting date is the standard's rule -- SNC "Diferenţe de curs valutar şi de
sumă" pct. 11 for monetary items in foreign currency, pct. 22 for contracts
between residents, which are not -- and the rule is applied in one place, the
revaluation service, not in each provider.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

RECEIVABLE = "receivable"
PAYABLE = "payable"


@dataclass(frozen=True, slots=True)
class MonetaryItem:
    """One open balance in a currency other than the functional one.

    ``document_rate`` is the rate the balance was **recognised** at -- the
    header's. What it is *carried* at on the day of the revaluation may differ,
    once an earlier revaluation restated it (pct. 15), and that is the
    revaluation service's question, not the provider's.
    """

    document_id: uuid.UUID
    document_type: str
    side: str
    partner_id: uuid.UUID
    partner_resident: bool
    contract_denomination: str
    currency: str
    amount_currency: Decimal
    document_rate: Decimal


Provider = Callable[[uuid.UUID, date], Sequence[MonetaryItem]]

PROVIDERS: dict[str, Provider] = {}


def register_provider(name: str, provider: Provider) -> None:
    """Called from a module's `AppConfig.ready()`, once per process.

    Re-registering the same name replaces rather than duplicates: `ready()` runs
    once per interpreter, but a test that reloads an app must not end up with the
    same balances counted twice.
    """
    PROVIDERS[name] = provider


def open_monetary_items(company_id: uuid.UUID, as_of: date) -> tuple[MonetaryItem, ...]:
    """Every open foreign-currency balance the registered providers know of."""
    items: list[MonetaryItem] = []
    for name in sorted(PROVIDERS):
        items.extend(PROVIDERS[name](company_id, as_of))
    return tuple(items)
