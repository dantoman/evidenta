"""Opening balances, against the side the Plan names for each account's balance.

The Plan says of every balance-sheet account which side its balance sits on --
"Soldul contului 242 ... este debitor", "Soldul contului 311 ... este creditor"
-- and, in chapter I, that classes 1-8 "funcţionează în partidă dublă". An
opening batch has to land each balance on that side and leave the technical
counterpart at zero.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from evidenta.accounting.ledger.services.trial_balance import trial_balance
from evidenta.platform.rls.context import tenant_context
from tests.corpus.book import OPENING_COUNTERPART, YEAR_END, YEAR_START, Book, agree
from tests.corpus.citations import OPENING, case

pytestmark = pytest.mark.django_db(databases=["default", "migration", "refdata"])

#: Debit balances on the active accounts, credit balances on the passive ones.
BALANCES = {
    "242": ("100000", "0"),
    "216": ("50000", "0"),
    "2211": ("36000", "0"),
    "5211": ("0", "20000"),
    "311": ("0", "166000"),
}


@case(OPENING, cites=("Plan 242", "Plan 216", "Plan 221", "Plan 521", "Plan 311"))
def test_an_opening_batch_lands_each_balance_on_the_side_the_plan_names(book: Book) -> None:
    """242, 216, 221: "Soldul contului ... este debitor"; 311: "este creditor"; 521:
    its balance "reprezintă suma datoriilor comerciale curente" -- a credit, being a
    passive account. The trial balance reads them back on those sides."""
    with tenant_context(book.context):
        book.open_with(BALANCES)
        assert book.balance("242") == Decimal("100000")
        assert book.balance("216") == Decimal("50000")
        assert book.balance("2211") == Decimal("36000")
        assert book.balance("5211") == Decimal("-20000")
        assert book.balance("311") == Decimal("-166000")
        agree(book)


@case(OPENING, cites=("Plan — Dispoziţii generale",))
def test_the_batch_is_double_entry_and_the_technical_counterpart_ends_at_zero(book: Book) -> None:
    """Plan, cap. I: "Conturile din clasele 1-8 funcţionează în partidă dublă, conform
    căreia înregistrările se efectuează concomitent în debitul unui cont şi creditul
    altui cont." Each balance faces the technical account, which nets to nothing."""
    with tenant_context(book.context):
        entry = book.open_with(BALANCES)
        lines = book.lines(entry)
        assert sum((debit for _, debit, _ in lines), Decimal(0)) == sum(
            (credit for _, _, credit in lines), Decimal(0)
        )
        balance = trial_balance(book.company, YEAR_START, YEAR_END)
        assert balance.balanced
        assert balance.total_debit == Decimal("372000")
        assert book.balance(OPENING_COUNTERPART) == 0
        agree(book)
