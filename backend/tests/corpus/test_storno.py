"""Storno, against SNC "Politici contabile ..." pct. 33 and SNC "Venituri" pct. 17.

pct. 33 names two forms for cancelling an erroneous entry -- "prin stornare sau
prin înregistrare contabilă inversă conform politicilor contabile ale
entităţii". The engine's reversal is the inverse-entry form: the sides
swapped, never negated (ADR-006), with both links of `R14`. What the corpus
holds it to is the act's outcome: the erroneous entry cancelled and the correct
one made (pct. 33 (1)), an overstated amount reduced by the difference
(pct. 33 (2)), a return in the same period reversing the revenue and the cost
(SNC "Venituri" pct. 17, Exemplul 8).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from evidenta.accounting.ledger.services.account_ledger import account_ledger
from evidenta.platform.rls.context import tenant_context
from tests.corpus.book import YEAR_END, YEAR_START, Book, agree
from tests.corpus.citations import STORNO, case

pytestmark = pytest.mark.django_db(databases=["default", "migration", "refdata"])

JAN_15, JAN_20 = date(2026, 1, 15), date(2026, 1, 20)
JUN_10, JUL_10 = date(2026, 6, 10), date(2026, 7, 10)


@case(
    STORNO,
    cites=("SNC Politici contabile pct. 33", "Plan 221", "Plan 611", "Plan nomenclator 2211/2212"),
)
def test_pct_33_an_erroneous_correspondence_is_cancelled_by_the_inverse_entry_and_re_recorded(
    book: Book,
) -> None:
    """pct. 33 (1): a wrong correspondence -- a domestic customer booked on 2212 -- "se
    anulează înregistrarea eronată prin ... înregistrare contabilă inversă ... cu
    întocmirea concomitentă a înregistrării contabile corecte". The inverse entry
    carries both links (R14); 2212 ends at zero, 2211 and 6111 at the sale."""
    with tenant_context(book.context):
        wrong = book.note(
            [("2212", "36000.00", "0"), ("6111", "0", "36000.00")],
            on=JAN_15,
            description="Vînzarea produselor — client din ţară, cont greşit",
        )
        inverse = book.storno(wrong, on=JAN_20, reason="Corespondenţă eronată: 2212 în loc de 2211")
        right = book.note(
            [("2211", "36000.00", "0"), ("6111", "0", "36000.00")],
            on=JAN_20,
            description="Vînzarea produselor — client din ţară",
        )
        assert sorted(book.lines(inverse)) == sorted(
            [("2212", Decimal(0), Decimal("36000.00")), ("6111", Decimal("36000.00"), Decimal(0))]
        )
        assert book.lines(right) == [
            ("2211", Decimal("36000.00"), Decimal(0)),
            ("6111", Decimal(0), Decimal("36000.00")),
        ]
        sheet = account_ledger(book.company, book.account("2212"), YEAR_START, YEAR_END)
        by_entry = {row.journal_entry_id: row for row in sheet.rows}
        assert by_entry[wrong].reversed_by_entry_id == inverse
        assert by_entry[inverse].reverses_entry_id == wrong
        assert book.balance("2212") == 0
        assert book.balance("2211") == Decimal("36000.00")
        assert book.balance("6111") == Decimal("-36000.00")
        agree(book)


@case(STORNO, cites=("SNC Politici contabile pct. 33", "Plan 221", "Plan 611"))
def test_pct_33_an_overstated_amount_is_cancelled_only_for_the_difference(book: Book) -> None:
    """pct. 33 (2): "în cazul în care suma înregistrată eronat este mai mare decît suma
    corectă - diferenţa se anulează prin stornare sau prin înregistrare contabilă
    inversă". 36 000 booked for a 30 600 sale: the inverse entry for 5 400 leaves the
    receivable and the revenue at the correct amount."""
    with tenant_context(book.context):
        book.note(
            [("2211", "36000.00", "0"), ("6111", "0", "36000.00")],
            on=JAN_15,
            description="Vînzarea produselor — sumă înregistrată în plus",
        )
        difference = book.note(
            [("6111", "5400.00", "0"), ("2211", "0", "5400.00")],
            on=JAN_20,
            description="Anularea diferenţei înregistrate în plus (pct. 33 (2))",
        )
        assert book.lines(difference) == [
            ("6111", Decimal("5400.00"), Decimal(0)),
            ("2211", Decimal(0), Decimal("5400.00")),
        ]
        assert book.balance("2211") == Decimal("30600.00")
        assert book.balance("6111") == Decimal("-30600.00")
        agree(book)


@case(
    STORNO,
    cites=(
        "SNC Venituri pct. 17",
        "SNC Politici contabile pct. 33",
        "Plan 611",
        "Plan 221",
        "Plan 711",
        "Plan 216",
    ),
)
def test_exemplul_8_a_return_in_the_same_period_reverses_the_revenue_and_the_cost(
    book: Book,
) -> None:
    """Exemplul 8, July of the same year: "valoarea mobilei returnate ... 10800 lei (3600
    lei x 3 set.) - ca stornare a creanţelor şi a veniturilor curente; costul mobilei
    returnate - ca stornare a cheltuielilor curente (costului vînzărilor) şi a
    stocurilor" -- in the inverse-entry form (pct. 33). Revenue 25 200, cost 17 500."""
    with tenant_context(book.context):
        book.open_with({"216": ("100000", "0"), "311": ("0", "100000")})
        book.note(
            [("2211", "36000.00", "0"), ("6111", "0", "36000.00")],
            on=JUN_10,
            description="Vînzarea a 10 seturi de mobilă",
        )
        book.note(
            [("7111", "25000.00", "0"), ("216", "0", "25000.00")],
            on=JUN_10,
            description="Costul efectiv al mobilei vîndute",
        )
        returned = book.note(
            [("6111", "10800.00", "0"), ("2211", "0", "10800.00")],
            on=JUL_10,
            description="Returnarea a 3 seturi — stornarea creanţei şi a venitului",
        )
        cost_back = book.note(
            [("216", "7500.00", "0"), ("7111", "0", "7500.00")],
            on=JUL_10,
            description="Returnarea a 3 seturi — stornarea costului vînzărilor",
        )
        assert book.lines(returned) == [
            ("6111", Decimal("10800.00"), Decimal(0)),
            ("2211", Decimal(0), Decimal("10800.00")),
        ]
        assert book.lines(cost_back) == [
            ("216", Decimal("7500.00"), Decimal(0)),
            ("7111", Decimal(0), Decimal("7500.00")),
        ]
        assert book.balance("6111") == Decimal("-25200.00")
        assert book.balance("2211") == Decimal("25200.00")
        assert book.balance("7111") == Decimal("17500.00")
        assert book.balance("216") == Decimal("82500.00")
        agree(book)
