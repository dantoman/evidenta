"""A10 -- the reporting-date revaluation of monetary items in currency, against SNC
"Diferenţe de curs valutar şi de sumă" pct. 11, 14, 15 and Exemplul 3.

The act carries one worked example the handler can be held to (Exemplul 3): a
receivable in euro restated at the reporting date, then settled in the next
period from the restated rate. Its figures are rounded to the leu in the text;
the engine keeps the scale of `accounting.amount_scale`, so the corpus asserts
4 270,50 where the act prints 4 270 -- an explained difference, not a divergence
(README, "Explicate, nu divergențe").

Three claims:

1. **A receivable restated at a higher rate is a favourable difference**, receivable
   and revenue up (pct. 14 through pct. 9 (1)): 13 000 EUR, 15,0540 → 15,3825.
2. **After a revaluation the next difference starts from the revalued rate** (pct. 15,
   Exemplul 3's second half): the same receivable at 15,3158 is 867,10 against
   15,3825, not against 15,0540.
3. **The same reporting date twice posts once** (`R19`): the key is the company and
   the date, so the second run returns the first entry.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

import pytest

from evidenta.accounting.posting.services.revaluation import (
    RECEIVABLE,
    RevaluationPostingResult,
    RevaluedItem,
    post_revaluation,
)
from evidenta.platform.rls.context import tenant_context
from tests.corpus.book import MDL, SNAPSHOT, Book, agree
from tests.corpus.citations import REVALUATION, case

pytestmark = pytest.mark.django_db(databases=["default", "migration", "refdata"])

REPORTING = date(2026, 1, 31)
NEXT_REPORTING = date(2026, 2, 28)
CUSTOMER = uuid.UUID("00000000-0000-0000-0000-00000000ee03")
INVOICE = uuid.UUID("00000000-0000-0000-0000-00000000dd03")


def item(*, carrying: str, closing: str) -> RevaluedItem:
    return RevaluedItem(
        document_id=INVOICE,
        document_type="sales.document",
        side=RECEIVABLE,
        partner_id=CUSTOMER,
        currency="EUR",
        amount_currency=Decimal(13000),
        carrying_rate=Decimal(carrying),
        closing_rate=Decimal(closing),
    )


def revalue(book: Book, *, as_of: date, items: Sequence[RevaluedItem]) -> RevaluationPostingResult:
    return post_revaluation(
        tenant_id=book.tenant,
        company_id=book.company,
        revaluation_id=uuid.uuid4(),
        as_of=as_of,
        functional_currency=MDL,
        items=items,
        actor_user_id=book.user,
        request_id="corpus-revaluation",
        capability_snapshot=SNAPSHOT,
    )


@case(
    REVALUATION,
    cites=(
        "SNC Diferenţe de curs pct. 11",
        "SNC Diferenţe de curs pct. 14",
        "SNC Diferenţe de curs Exemplul 3",
        "Plan nomenclator 2211/2212",
        "Plan nomenclator 6226/7224",
    ),
)
def test_a_receivable_restated_at_a_higher_rate_is_a_favourable_difference(book: Book) -> None:
    """Exemplul 3, first half: 13 000 EUR at 15,0540 restated at 15,3825 -- 13 000 x
    0,3285 = 4 270,50, "ca majorare concomitentă a creanţelor şi veniturilor curente":
    Dt 2212 / Ct 6226."""
    with tenant_context(book.context):
        result = revalue(book, as_of=REPORTING, items=[item(carrying="15.0540", closing="15.3825")])
        assert result.journal_entry_id is not None
        assert book.correspondences(result.journal_entry_id) == [
            ("2212", "6226", Decimal("4270.50")),
        ]
        agree(book)


@case(
    REVALUATION,
    cites=(
        "SNC Diferenţe de curs pct. 15",
        "SNC Diferenţe de curs Exemplul 3",
        "Plan nomenclator 6226/7224",
    ),
)
def test_the_next_difference_starts_from_the_revalued_rate(book: Book) -> None:
    """Exemplul 3, second half: the same receivable at 15,3158 against the restated
    15,3825 -- 13 000 x 0,0667 = 867,10 unfavourable, Dt 7224 / Ct 2212. Against the
    original 15,0540 it would have been a gain of 3 403,40, which is the error pct. 15
    forbids: each period recognises its own difference."""
    with tenant_context(book.context):
        revalue(book, as_of=REPORTING, items=[item(carrying="15.0540", closing="15.3825")])
        result = revalue(
            book, as_of=NEXT_REPORTING, items=[item(carrying="15.3825", closing="15.3158")]
        )
        assert result.journal_entry_id is not None
        assert book.correspondences(result.journal_entry_id) == [
            ("7224", "2212", Decimal("867.10")),
        ]
        agree(book)


@case(REVALUATION, cites=("SNC Diferenţe de curs pct. 13", "SNC Diferenţe de curs pct. 14"))
def test_the_same_reporting_date_twice_posts_once(book: Book) -> None:
    """pct. 13 lets the entity choose the periodicity; whatever it is, one date is one
    revaluation. The second run returns the first entry and writes nothing."""
    with tenant_context(book.context):
        first = revalue(book, as_of=REPORTING, items=[item(carrying="15.0540", closing="15.3825")])
        again = revalue(book, as_of=REPORTING, items=[item(carrying="15.0540", closing="15.3825")])
        assert again.posted_now is False
        assert again.journal_entry_id == first.journal_entry_id
        agree(book)
