"""The manual note, against the Plan's correspondences.

A manual note is the accountant choosing the correspondence; what the corpus
can hold it to is that the engine writes the lines as the Plan's norms name
them -- the sale on 221 against 611 and its cost on 711 against 216 (SNC
"Venituri", Exemplul 8), the VAT on 221 against 534, the receipt on 242
against 221, the supplier paid from 242 against 521, the income tax on 731
against 534 -- and that every report reads them back the same.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from evidenta.platform.rls.context import tenant_context
from tests.corpus.book import Book, agree
from tests.corpus.citations import MANUAL_NOTE, case

pytestmark = pytest.mark.django_db(databases=["default", "migration", "refdata"])

JUN_10 = date(2026, 6, 10)


@case(
    MANUAL_NOTE,
    cites=(
        "SNC Venituri pct. 17",
        "Plan 221",
        "Plan 611",
        "Plan 711",
        "Plan 216",
        "Plan nomenclator 6111/7111",
    ),
)
def test_exemplul_8_a_sale_of_products_is_a_receivable_against_revenue_and_a_cost_out_of_stock(
    book: Book,
) -> None:
    """Exemplul 8, June: "veniturile din vînzarea mobilei în sumă de 36000 lei ... ca
    majorare concomitentă a creanţelor şi veniturilor curente" -- Dt 2211 / Ct 6111
    (Plan 221: credit 611; Plan 611: debit 221); "costul efectiv ... 25000 lei ... ca
    majorare a cheltuielilor curente (costului vînzărilor) şi diminuare a stocurilor" --
    Dt 7111 / Ct 216 (Plan 711: credit 216; Plan 216: debit 711)."""
    with tenant_context(book.context):
        book.open_with({"216": ("100000", "0"), "311": ("0", "100000")})
        sale = book.note(
            [("2211", "36000.00", "0"), ("6111", "0", "36000.00")],
            on=JUN_10,
            description="Vînzarea a 10 seturi de mobilă, 3600 lei setul",
        )
        cost = book.note(
            [("7111", "25000.00", "0"), ("216", "0", "25000.00")],
            on=JUN_10,
            description="Costul efectiv al mobilei vîndute, 2500 lei setul",
        )
        assert book.lines(sale) == [
            ("2211", Decimal("36000.00"), Decimal(0)),
            ("6111", Decimal(0), Decimal("36000.00")),
        ]
        assert book.lines(cost) == [
            ("7111", Decimal("25000.00"), Decimal(0)),
            ("216", Decimal(0), Decimal("25000.00")),
        ]
        assert book.balance("2211") == Decimal("36000.00")
        assert book.balance("6111") == Decimal("-36000.00")
        assert book.balance("7111") == Decimal("25000.00")
        assert book.balance("216") == Decimal("75000.00")
        agree(book)


@case(MANUAL_NOTE, cites=("Plan 221", "Plan 534", "Plan nomenclator 5341/5344"))
def test_the_vat_on_a_sale_is_a_receivable_against_the_budget(book: Book) -> None:
    """Plan 221: debit "în corespondenţă cu creditul conturilor: 331, 534 ..."; Plan 534:
    credit "în corespondenţă cu debitul conturilor: 221 ...". The amount is the one the
    document carries; the corpus computes no VAT (the rate is `vat.*` data, `R15`)."""
    with tenant_context(book.context):
        entry = book.note(
            [("2211", "7200.00", "0"), ("5344", "0", "7200.00")],
            on=JUN_10,
            description="TVA aferentă vînzării, înscrisă pe factura fiscală",
        )
        assert book.lines(entry) == [
            ("2211", Decimal("7200.00"), Decimal(0)),
            ("5344", Decimal(0), Decimal("7200.00")),
        ]
        assert book.balance("5344") == Decimal("-7200.00")
        agree(book)


@case(MANUAL_NOTE, cites=("Plan 242", "Plan 221"))
def test_a_receipt_from_a_customer_moves_the_receivable_to_the_bank(book: Book) -> None:
    """Plan 242: debit "încasarea numerarului ... în corespondenţă cu creditul conturilor:
    ... 221 ..."; Plan 221: credit "stingerea/diminuarea creanţelor ... cu debitul
    conturilor: ... 242 ...". After the receipt the receivable is at zero."""
    with tenant_context(book.context):
        book.note(
            [("2211", "36000.00", "0"), ("6111", "0", "36000.00")],
            on=JUN_10,
            description="Vînzarea produselor",
        )
        receipt = book.note(
            [("242", "36000.00", "0"), ("2211", "0", "36000.00")],
            on=date(2026, 6, 20),
            description="Încasarea creanţei în contul curent",
        )
        assert book.lines(receipt) == [
            ("242", Decimal("36000.00"), Decimal(0)),
            ("2211", Decimal(0), Decimal("36000.00")),
        ]
        assert book.balance("2211") == 0
        assert book.balance("242") == Decimal("36000.00")
        agree(book)


@case(MANUAL_NOTE, cites=("Plan 521", "Plan 242"))
def test_paying_a_supplier_settles_the_payable_from_the_bank(book: Book) -> None:
    """Plan 521: debit "stingerea/diminuarea datoriilor comerciale ... cu creditul
    conturilor: ... 242 ..."; Plan 242: credit "utilizarea numerarului ... cu debitul
    conturilor: ... 521 ..."."""
    with tenant_context(book.context):
        book.open_with({"242": ("100000", "0"), "5211": ("0", "20000"), "311": ("0", "80000")})
        payment = book.note(
            [("5211", "20000.00", "0"), ("242", "0", "20000.00")],
            on=JUN_10,
            description="Achitarea furnizorului din contul curent",
        )
        assert book.lines(payment) == [
            ("5211", Decimal("20000.00"), Decimal(0)),
            ("242", Decimal(0), Decimal("20000.00")),
        ]
        assert book.balance("5211") == 0
        assert book.balance("242") == Decimal("80000.00")
        agree(book)


@case(MANUAL_NOTE, cites=("Plan 731", "Plan nomenclator 5341/5344"))
def test_the_income_tax_expense_is_recognised_against_the_budget(book: Book) -> None:
    """Plan 731: debit "recunoaşterea cheltuielilor privind impozitul pe venit ... în
    corespondenţă cu creditul conturilor: 428, 534"; 5341 is the sub-account the
    nomenclature names for it. A booked amount, not a computed tax."""
    with tenant_context(book.context):
        entry = book.note(
            [("731", "9600.00", "0"), ("5341", "0", "9600.00")],
            on=date(2026, 12, 20),
            description="Cheltuieli privind impozitul pe venit",
        )
        assert book.lines(entry) == [
            ("731", Decimal("9600.00"), Decimal(0)),
            ("5341", Decimal(0), Decimal("9600.00")),
        ]
        assert book.balance("731") == Decimal("9600.00")
        assert book.balance("5341") == Decimal("-9600.00")
        agree(book)
