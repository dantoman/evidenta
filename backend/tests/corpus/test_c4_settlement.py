"""C4 -- the difference a settlement realises, against SNC "Diferenţe de curs
valutar şi de sumă" and the Plan's account norms.

The act carries three worked examples the handler can be held to: Exemplul 1
(a payable in dollars settled at a lower rate), Exemplul 2 (a receivable in
euro settled at a lower rate) and Exemplul 5 (a contract in euro between two
residents, paid in lei at the rate of the payment date -- a *sum* difference,
on the other pair of accounts). The rest of the cases take the points that
say when no difference arises at all (pct. 21, 23) and the bank spread the
nomenclature names (6127 / 7147).

Exemplul 2's figure is two terms; the corpus reproduces the settlement term
and reports the advance term (README, "Divergențe raportate").
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from evidenta.accounting.ledger.models import JournalEntry
from evidenta.accounting.posting.services.settlement import (
    CONVENTIONAL_UNITS,
    DELIVERY_DATE,
    FIXED,
    FOREIGN_CURRENCY,
    PAYABLE,
    PAYMENT_DATE,
    RECEIVABLE,
    SettlementFact,
    SettlementResult,
    post_settlement_differences,
)
from evidenta.platform.rls.context import tenant_context
from tests.corpus.book import MDL, SNAPSHOT, Book, agree
from tests.corpus.citations import SETTLEMENT, case

pytestmark = pytest.mark.django_db(databases=["default", "migration", "refdata"])

SETTLED = date(2026, 1, 20)


def fact(**overrides: Any) -> SettlementFact:
    base: dict[str, Any] = {
        "settlement_id": uuid.uuid4(),
        "document_id": uuid.uuid4(),
        "document_type": "sales.document",
        "side": RECEIVABLE,
        "currency": "USD",
        "amount_currency": Decimal(1000),
        "issue_rate": Decimal("17.5000"),
        "settlement_rate": Decimal("17.6200"),
        "settlement_date": SETTLED,
        "rate_term": PAYMENT_DATE,
        "partner_resident": False,
        "contract_denomination": FOREIGN_CURRENCY,
        "settles_advance": False,
    }
    base.update(overrides)
    return SettlementFact(**base)


def settle(book: Book, the_fact: SettlementFact) -> SettlementResult:
    return post_settlement_differences(
        tenant_id=book.tenant,
        company_id=book.company,
        functional_currency=MDL,
        fact=the_fact,
        actor_user_id=book.user,
        request_id="corpus",
        capability_snapshot=dict(SNAPSHOT),
    )


# --- exchange differences: the act's examples ----------------------------------------


@case(
    SETTLEMENT,
    cites=(
        "SNC Diferenţe de curs pct. 8",
        "SNC Diferenţe de curs pct. 9",
        "Plan 521",
        "Plan 622",
        "Plan nomenclator 5211/5212",
        "Plan nomenclator 6226/7224",
    ),
)
def test_exemplul_1_a_payable_in_dollars_settled_at_a_lower_rate_is_favourable(
    book: Book,
) -> None:
    """Exemplul 1: 10 000 USD recognised at 11,5525, paid at 11,3378 -- "diferenţa de
    curs valutar favorabilă în suma de 2147 lei ... ca diminuare a datoriilor curente şi
    majorare a veniturilor curente" (pct. 9 (2)): Dt 5212 / Ct 6226."""
    with tenant_context(book.context):
        result = settle(
            book,
            fact(
                side=PAYABLE,
                document_type="purchases.document",
                amount_currency=Decimal(10000),
                issue_rate=Decimal("11.5525"),
                settlement_rate=Decimal("11.3378"),
            ),
        )
        assert result.journal_entry_id is not None
        assert book.correspondences(result.journal_entry_id) == [
            ("5212", "6226", Decimal("2147.00")),
        ]
        assert book.balance("6226") == Decimal("-2147.00")
        agree(book)


@case(
    SETTLEMENT,
    cites=(
        "SNC Diferenţe de curs pct. 8",
        "SNC Diferenţe de curs pct. 10",
        "Plan 221",
        "Plan 722",
        "Plan nomenclator 2211/2212",
        "Plan nomenclator 6226/7224",
    ),
)
def test_exemplul_2_a_receivable_in_euro_settled_at_a_lower_rate_is_unfavourable(
    book: Book,
) -> None:
    """Exemplul 2, the settlement term: 30 000 EUR delivered at 15,3845, collected at
    15,3136 -- 30 000 x (15,3136 - 15,3845) = -2 127 lei, "ca majorare a cheltuielilor
    curente şi diminuare a creanţelor curente" (pct. 10 (1)): Dt 7224 / Ct 2212. The
    act's 2 910 also carries 783 lei on the advance offset; see the README."""
    with tenant_context(book.context):
        result = settle(
            book,
            fact(
                currency="EUR",
                amount_currency=Decimal(30000),
                issue_rate=Decimal("15.3845"),
                settlement_rate=Decimal("15.3136"),
            ),
        )
        assert result.journal_entry_id is not None
        assert book.correspondences(result.journal_entry_id) == [
            ("7224", "2212", Decimal("2127.00")),
        ]
        agree(book)


@case(SETTLEMENT, cites=("SNC Diferenţe de curs pct. 9", "Plan 221", "Plan 622"))
def test_a_receivable_from_abroad_settled_at_a_higher_rate_is_favourable(book: Book) -> None:
    """pct. 9 (1): "în cazul creşterii cursului valutar - ca majorare concomitentă a
    numerarului, creanţelor curente ... şi veniturilor curente": 1 000 USD, 17,50 →
    17,62, Dt 2212 / Ct 6226 for 120,00."""
    with tenant_context(book.context):
        result = settle(book, fact())
        assert result.journal_entry_id is not None
        assert book.correspondences(result.journal_entry_id) == [
            ("2212", "6226", Decimal("120.00")),
        ]
        agree(book)


@case(SETTLEMENT, cites=("SNC Diferenţe de curs pct. 10", "Plan 521", "Plan 722"))
def test_a_payable_abroad_settled_at_a_higher_rate_is_unfavourable(book: Book) -> None:
    """pct. 10 (2): "în cazul creşterii cursului valutar - ca majorare concomitentă a
    cheltuielilor şi datoriilor curente": Dt 7224 / Ct 5212 for 120,00."""
    with tenant_context(book.context):
        result = settle(book, fact(side=PAYABLE, document_type="purchases.document"))
        assert result.journal_entry_id is not None
        assert book.correspondences(result.journal_entry_id) == [
            ("7224", "5212", Decimal("120.00")),
        ]
        agree(book)


# --- sum differences: residents, conventional units ----------------------------------


@case(
    SETTLEMENT,
    cites=(
        "SNC Diferenţe de curs pct. 17",
        "SNC Diferenţe de curs pct. 19",
        "SNC Diferenţe de curs pct. 20",
        "Plan 221",
        "Plan 622",
        "Plan nomenclator 6227/7225",
    ),
)
def test_exemplul_5_the_seller_between_residents_books_a_favourable_sum_difference(
    book: Book,
) -> None:
    """Exemplul 5, the seller: a contract "exprimată în euro" between two residents,
    paid in lei at the rate of the payment date (pct. 19 (1)), 15,1220 → 15,3252 --
    "diferenţa de sumă favorabilă ... 1016 lei ... ca majorare concomitentă a creanţelor
    şi veniturilor curente" (pct. 20 (1)): Dt 2211 / Ct 6227 -- the sum pair, because the
    parties are residents (pct. 17), whatever the contract is denominated in."""
    with tenant_context(book.context):
        result = settle(
            book,
            fact(
                currency="EUR",
                amount_currency=Decimal(5000),
                issue_rate=Decimal("15.1220"),
                settlement_rate=Decimal("15.3252"),
                partner_resident=True,
                contract_denomination=FOREIGN_CURRENCY,
            ),
        )
        assert result.journal_entry_id is not None
        assert book.correspondences(result.journal_entry_id) == [
            ("2211", "6227", Decimal("1016.00")),
        ]
        assert book.balance("6226") == 0
        agree(book)


@case(
    SETTLEMENT,
    cites=("SNC Diferenţe de curs pct. 20", "Plan 521", "Plan 722", "Plan nomenclator 6227/7225"),
)
def test_exemplul_5_the_buyer_between_residents_books_an_unfavourable_sum_difference(
    book: Book,
) -> None:
    """Exemplul 5, the buyer: the same 1 016 lei "ca majorarea concomitentă a
    cheltuielilor şi datoriilor curente" (pct. 20 (2)): Dt 7225 / Ct 5211."""
    with tenant_context(book.context):
        result = settle(
            book,
            fact(
                side=PAYABLE,
                document_type="purchases.document",
                currency="EUR",
                amount_currency=Decimal(5000),
                issue_rate=Decimal("15.1220"),
                settlement_rate=Decimal("15.3252"),
                partner_resident=True,
                contract_denomination=FOREIGN_CURRENCY,
            ),
        )
        assert result.journal_entry_id is not None
        assert book.correspondences(result.journal_entry_id) == [
            ("7225", "5211", Decimal("1016.00")),
        ]
        agree(book)


@case(SETTLEMENT, cites=("SNC Diferenţe de curs pct. 19", "SNC Diferenţe de curs pct. 21"))
@pytest.mark.parametrize("term", [DELIVERY_DATE, FIXED])
def test_at_the_delivery_date_rate_or_a_fixed_rate_no_sum_difference_arises(
    book: Book, term: str
) -> None:
    """pct. 21: at the delivery-date rate or a rate the parties fixed, "diferenţe de
    sumă nu apar, deoarece vînzătorul şi cumpărătorul recunosc creanţele şi datoriile în
    baza aceluiaşi curs de schimb" -- the event is recorded, no entry is written."""
    with tenant_context(book.context):
        result = settle(
            book,
            fact(
                currency="EUR",
                amount_currency=Decimal(5000),
                issue_rate=Decimal("15.1220"),
                settlement_rate=Decimal("15.3252"),
                rate_term=term,
                partner_resident=True,
                contract_denomination=CONVENTIONAL_UNITS,
            ),
        )
        assert result.journal_entry_id is None
        assert not JournalEntry.objects.filter(
            accounting_event_id=result.accounting_event_id
        ).exists()
        assert book.balance("6227") == 0 and book.balance("7225") == 0
        agree(book)


@case(SETTLEMENT, cites=("SNC Diferenţe de curs pct. 23",))
def test_an_advance_between_residents_keeps_the_rate_of_the_day_it_was_paid(book: Book) -> None:
    """pct. 23: the lei equivalent of an advance "se determină prin aplicarea cursului de
    schimb la data plăţii acestuia şi ulterior nu se recalculează" -- settling against
    the advance produces no difference, whatever the rates."""
    with tenant_context(book.context):
        result = settle(
            book,
            fact(
                currency="EUR",
                amount_currency=Decimal(5000),
                issue_rate=Decimal("15.1220"),
                settlement_rate=Decimal("15.3252"),
                partner_resident=True,
                contract_denomination=CONVENTIONAL_UNITS,
                settles_advance=True,
            ),
        )
        assert result.journal_entry_id is None
        agree(book)


# --- the bank's rate against the official one ----------------------------------------


@case(
    SETTLEMENT,
    cites=("Plan nomenclator 6127/7147", "Plan 612", "Plan 714", "Plan 242"),
)
def test_the_spread_between_the_official_rate_and_the_banks_lands_in_the_operating_result(
    book: Book,
) -> None:
    """The nomenclature names the accounts: 6127 "Venituri aferente diferenţelor
    favorabile dintre cursul oficial al BNM şi cursul de cumpărare-vînzare a valutei
    străine", 7147 its unfavourable twin -- under 612 and 714, the operating result, not
    under 622 / 722. The counterpart is the lei account the conversion touched: Plan 612
    lists 242 on its debit side, Plan 714 lists 242 on its credit side. 1 000 USD sold
    to the bank at 17,45 against an official 17,50 is 50,00 lost; at 17,55, 50,00 gained."""
    with tenant_context(book.context):
        official = Decimal("17.5000")
        sold_low = settle(
            book, fact(side=RECEIVABLE, settlement_rate=official, bank_rate=Decimal("17.4500"))
        )
        sold_high = settle(
            book, fact(side=RECEIVABLE, settlement_rate=official, bank_rate=Decimal("17.5500"))
        )
        # Buying currency to settle a payable: a higher bank rate costs more lei.
        bought_high = settle(
            book,
            fact(
                side=PAYABLE,
                document_type="purchases.document",
                settlement_rate=official,
                bank_rate=Decimal("17.5500"),
            ),
        )
        bought_low = settle(
            book,
            fact(
                side=PAYABLE,
                document_type="purchases.document",
                settlement_rate=official,
                bank_rate=Decimal("17.4500"),
            ),
        )
        entries = [r.journal_entry_id for r in (sold_low, sold_high, bought_high, bought_low)]
        assert all(entry is not None for entry in entries)
        loss, gain = [("7147", "242", Decimal("50.00"))], [("242", "6127", Decimal("50.00"))]
        posted = [book.correspondences(entry) for entry in entries if entry is not None]
        assert posted == [loss, gain, loss, gain]
        assert book.balance("6226") == 0 and book.balance("7224") == 0
        agree(book)
