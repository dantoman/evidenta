"""Closing the month and the exercise, against the Plan and SNC "Capital propriu".

The Plan's norms for the result accounts say *when* they are settled -- "la
finele perioadei de gestiune", against 351 -- and that 351 "la sfîrşitul
perioadei de gestiune nu are sold"; SNC "Capital propriu şi datorii" carries
the worked example (Exemplul 7: 190 000 of revenue, 110 000 of expenses,
settled on 31 December). The month, by contrast, posts nothing (ADR-054 §4:
the period of the norm is the year); what it validates is the Plan's rule for
class 8 -- "la data raportării conturile de gestiune se închid".
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from evidenta.accounting.ledger.models import JournalEntry
from evidenta.accounting.periods.errors import ManagementAccountsNotSettledError
from evidenta.accounting.periods.models import PeriodStatus
from evidenta.accounting.periods.services.lifecycle import close_period
from evidenta.accounting.posting.services.closing import (
    YearClosingResult,
    close_month,
    close_year,
)
from evidenta.accounting.posting.services.production import (
    AllocationFact,
    ProductShare,
    post_overhead_allocation,
)
from evidenta.platform.rls.context import tenant_context
from tests.corpus.book import MDL, SNAPSHOT, YEAR_END, Book, agree
from tests.corpus.citations import MONTH_CLOSED, YEAR_CLOSED, case

pytestmark = pytest.mark.django_db(databases=["default", "migration", "refdata"])

JAN_15, JAN_31 = date(2026, 1, 15), date(2026, 1, 31)


def close_the_month(book: Book, month: int) -> uuid.UUID:
    result = close_month(
        book.period(month).id,
        actor_user_id=book.user,
        request_id="corpus",
        capability_snapshot=dict(SNAPSHOT),
    )
    return result.accounting_event_id


def close_the_year(book: Book) -> YearClosingResult:
    for month in range(1, 12):
        close_period(book.period(month).id)
    return close_year(
        book.year.id,
        functional_currency=MDL,
        actor_user_id=book.user,
        request_id="corpus",
        capability_snapshot=dict(SNAPSHOT),
    )


# --- the month ----------------------------------------------------------------------


@case(MONTH_CLOSED, cites=("Plan 611", "Plan 351", "ADR-054 §4", "ADR-056 §3.1"))
def test_closing_a_month_settles_nothing_to_351(book: Book) -> None:
    """Plan 611: the revenue is settled to 351 "la finele perioadei de gestiune", and
    the period of the norm is the exercise, not the month (ADR-054 §4). January closes
    with the revenue still on 6111, no line on 351, no entry at all."""
    with tenant_context(book.context):
        book.open_with({"242": ("100000", "0"), "311": ("0", "100000")})
        book.note(
            [("2211", "36000.00", "0"), ("6111", "0", "36000.00")],
            on=JAN_15,
            description="Venituri din vînzarea produselor",
        )
        event_id = close_the_month(book, 1)
        assert not JournalEntry.objects.filter(accounting_event_id=event_id).exists()
        assert book.period(1).status == PeriodStatus.CLOSED
        assert book.balance("6111", end=JAN_31) == Decimal("-36000.00")
        assert book.balance("351") == 0
        agree(book)


@case(
    MONTH_CLOSED,
    cites=("Plan clasa 8", "Plan 821", "Plan 811", "Plan 216", "ADR-039 §10.1", "ADR-056 §3.1"),
)
def test_a_month_whose_management_accounts_carry_a_balance_does_not_close(book: Book) -> None:
    """Plan, clasa 8: "la data raportării conturile de gestiune se închid cu conturile de
    bilanţ şi/sau de rezultate". Indirect costs invoiced onto 821 (Plan 821: credit 521)
    keep January open; allocated to 811 (Plan 811: credit 821) they still do -- 811 is
    class 8 too -- until the finished products leave it for 216 (Plan 216: debit
    "intrarea ... produselor în corespondenţă cu creditul conturilor: ... 811"). Then
    both management accounts are at zero and the month closes."""
    with tenant_context(book.context):
        book.note(
            [("821", "10000.00", "0"), ("5211", "0", "10000.00")],
            on=JAN_15,
            description="Costuri indirecte de producţie facturate",
        )
        with pytest.raises(ManagementAccountsNotSettledError):
            close_period(book.period(1).id)
        assert book.period(1).status == PeriodStatus.OPEN

        post_overhead_allocation(
            tenant_id=book.tenant,
            company_id=book.company,
            functional_currency=MDL,
            fact=AllocationFact(
                allocation_id=uuid.uuid4(),
                period_start=date(2026, 1, 1),
                period_end=JAN_31,
                variable_costs=Decimal(10000),
                constant_costs=Decimal(0),
                normal_capacity=Decimal(1000),
                actual_volume=Decimal(1000),
                base_name="cantitatea de produse fabricate",
                products=(ProductShare(uuid.UUID(int=0xA), Decimal(1000), code="A"),),
            ),
            actor_user_id=book.user,
            request_id="corpus",
            capability_snapshot=dict(SNAPSHOT),
        )
        assert book.balance("821") == 0
        with pytest.raises(ManagementAccountsNotSettledError):
            close_period(book.period(1).id)

        book.note(
            [("216", "10000.00", "0"), ("811", "0", "10000.00")],
            on=JAN_31,
            description="Costul efectiv al produselor fabricate",
        )
        assert book.balance("811") == 0
        close_the_month(book, 1)
        assert book.period(1).status == PeriodStatus.CLOSED
        agree(book)


# --- the exercise -------------------------------------------------------------------


@case(
    YEAR_CLOSED,
    cites=(
        "SNC Capital propriu pct. 21",
        "SNC Capital propriu pct. 23",
        "Plan 611",
        "Plan 714",
        "Plan 351",
        "Plan 333",
        "ADR-050 §3.2",
    ),
)
def test_exemplul_7_the_year_settles_revenue_and_expenses_to_351_and_the_profit_to_333(
    book: Book,
) -> None:
    """Exemplul 7, on 31 December: "decontarea veniturilor curente în sumă de 190000 lei
    - ca diminuare a veniturilor curente şi majorare a rezultatului financiar total";
    "decontarea cheltuielilor curente în sumă de 110000 lei - ca diminuare concomitentă
    a rezultatului financiar total ... şi a cheltuielilor curente"; the profit, 80 000
    (pct. 21), on 333 (Plan 333: credit, against 351). 351 ends without a balance."""
    with tenant_context(book.context):
        book.note(
            [("2211", "190000.00", "0"), ("6111", "0", "190000.00")],
            on=JAN_15,
            description="Venituri ale anului",
        )
        book.note(
            [("714", "110000.00", "0"), ("5211", "0", "110000.00")],
            on=JAN_15,
            description="Cheltuieli ale anului",
        )
        result = close_the_year(book)
        assert result.journal_entry_id is not None
        entry = JournalEntry.objects.get(pk=result.journal_entry_id)
        assert entry.accounting_date == YEAR_END
        assert book.correspondences(entry.id) == [
            ("6111", "351", Decimal("190000.00")),
            ("351", "714", Decimal("110000.00")),
            ("351", "333", Decimal("80000.00")),
        ]
        assert book.balance("351") == 0
        assert book.balance("6111") == 0 and book.balance("714") == 0
        assert book.balance("333") == Decimal("-80000.00")
        agree(book)


@case(
    YEAR_CLOSED,
    cites=("Plan 731", "Plan 351", "Plan nomenclator 5341/5344", "ADR-050 §3.2"),
)
def test_the_income_tax_expense_settles_apart_after_the_rest_of_class_7(book: Book) -> None:
    """Plan 731: recognised "la finele perioadei de gestiune" against 534, settled to
    351 as its own step. ADR-050 §3.2 fixes the order -- classes 6 and 7 without 731,
    then 731, then 351 to 333. 9 600 is a booked amount, not a computed tax."""
    with tenant_context(book.context):
        book.note(
            [("2211", "190000.00", "0"), ("6111", "0", "190000.00")],
            on=JAN_15,
            description="Venituri ale anului",
        )
        book.note(
            [("714", "110000.00", "0"), ("5211", "0", "110000.00")],
            on=JAN_15,
            description="Cheltuieli ale anului",
        )
        book.note(
            [("731", "9600.00", "0"), ("5341", "0", "9600.00")],
            on=date(2026, 12, 20),
            description="Cheltuieli privind impozitul pe venit",
        )
        result = close_the_year(book)
        assert result.journal_entry_id is not None
        assert book.correspondences(result.journal_entry_id) == [
            ("6111", "351", Decimal("190000.00")),
            ("351", "714", Decimal("110000.00")),
            ("351", "731", Decimal("9600.00")),
            ("351", "333", Decimal("70400.00")),
        ]
        assert book.balance("731") == 0 and book.balance("351") == 0
        assert book.balance("333") == Decimal("-70400.00")
        agree(book)


@case(YEAR_CLOSED, cites=("Plan 333", "Plan 351"))
def test_a_loss_lands_on_the_debit_of_333(book: Book) -> None:
    """Plan 333: "În debitul acestui cont se înregistrează apariţia/majorarea pierderii
    nete ... în corespondenţă cu creditul conturilor: ... 351"; Plan 351: its credit
    takes "decontarea ... pierderii nete ... în corespondenţă cu debitul conturilor: 333".
    50 000 of revenue against 80 000 of expenses: Dt 333 / Ct 351 for 30 000."""
    with tenant_context(book.context):
        book.note(
            [("2211", "50000.00", "0"), ("6111", "0", "50000.00")],
            on=JAN_15,
            description="Venituri ale anului",
        )
        book.note(
            [("714", "80000.00", "0"), ("5211", "0", "80000.00")],
            on=JAN_15,
            description="Cheltuieli ale anului",
        )
        result = close_the_year(book)
        assert result.journal_entry_id is not None
        assert book.correspondences(result.journal_entry_id) == [
            ("6111", "351", Decimal("50000.00")),
            ("351", "714", Decimal("80000.00")),
            ("333", "351", Decimal("30000.00")),
        ]
        assert book.balance("333") == Decimal("30000.00")
        assert book.balance("351") == 0
        agree(book)
