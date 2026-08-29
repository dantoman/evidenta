"""Closing the month and the exercise -- F1.5.4, ADR-039 section 10, ADR-050.

What is asserted is the **shape of the chain and the state machine around it**,
never a treatment: which correspondences the year's closing produces from which
balances, in which order, that 351 is left at zero and 333 holds the result, that
the month closes only over settled management accounts, and that after the year
closes nothing inside it moves. No chart code appears: the accounts are
fixtures whose codes start with the class digit the chain selects on, and the
three roles of the chain are bound to fixture accounts explicitly.

Under the application role, like every test in this suite (T1).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from evidenta.accounting.events.models import AccountingEvent
from evidenta.accounting.ledger.models import JournalEntry, JournalFormula
from evidenta.accounting.ledger.services.trial_balance import trial_balance
from evidenta.accounting.periods.errors import (
    FiscalYearClosedError,
    LastPeriodNotOpenError,
    ManagementAccountsNotSettledError,
    PeriodsStillOpenError,
    ResultAccountsCarryOpeningBalanceError,
)
from evidenta.accounting.periods.models import FiscalYear, Period, PeriodStatus
from evidenta.accounting.periods.services.lifecycle import close_period, reopen_period
from evidenta.accounting.periods.services.opening import open_fiscal_year
from evidenta.accounting.posting.formula import Formula
from evidenta.accounting.posting.invariants import Origin
from evidenta.accounting.posting.services.closing import (
    EVENT_MONTH,
    EVENT_YEAR,
    HANDLER_YEAR,
    ROLE_NET,
    ROLE_TAX,
    ROLE_TOTAL,
    close_month,
    close_year,
)
from evidenta.accounting.posting.services.formulas import post_formulas
from evidenta.accounting.slots.models import AccountRoleBinding
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.isolation.test_formulas import seed_account
from tests.isolation.test_ledger import seed_event
from tests.isolation.test_manual_entry import seed_template as seed_numbering

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

MDL = "MDL"
SNAPSHOT: dict[str, Any] = {"version": 1, "on": "2026-01-01", "activated": [], "usable": []}
POSTING = date(2026, 1, 15)


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="closing")


@pytest.fixture
def scene(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
    context: TenantContext,
) -> dict[str, Any]:
    """One company with the 2026 exercise open, a numbering template, and the
    accounts the chain needs: a balance-sheet counterpart, a revenue, an expense,
    the tax expense, and the three role accounts. Codes are fixtures that start
    with the class digit -- the only thing the chain reads from a code."""
    tenant = world["tenant_a"]
    company = company_of(tenant, "1002600000902", "Alpha Închidere")
    grant_company(tenant, company, world["user_a"], world["user_a"])
    seed_numbering(seed, tenant, company)
    accounts = {
        "asset": seed_account(seed, tenant, company, "2FIX"),
        "revenue": seed_account(seed, tenant, company, "6FIX"),
        "expense": seed_account(seed, tenant, company, "7FIX"),
        "tax": seed_account(seed, tenant, company, "731FIX"),
        "total": seed_account(seed, tenant, company, "351FIX"),
        "net": seed_account(seed, tenant, company, "333FIX"),
        "cost": seed_account(seed, tenant, company, "8FIX"),
    }
    with tenant_context(context):
        year = open_fiscal_year(company, "2026", date(2026, 1, 1), date(2026, 12, 31))
        for role, key in ((ROLE_TOTAL, "total"), (ROLE_TAX, "tax"), (ROLE_NET, "net")):
            AccountRoleBinding.objects.create(
                tenant_id=tenant,
                company_id=company,
                role=role,
                account_id=accounts[key],
                valid_from=date(2026, 1, 1),
                source="fixture",
            )
    return {"tenant": tenant, "company": company, "user": world["user_a"], "year": year, **accounts}


def post(
    scene: dict[str, Any],
    seed: Callable[..., None],
    debit: uuid.UUID,
    credit: uuid.UUID,
    amount: str,
    on: date = POSTING,
) -> uuid.UUID:
    event = seed_event(seed, scene["tenant"], scene["company"], scene["user"])
    result = post_formulas(
        tenant_id=scene["tenant"],
        company_id=scene["company"],
        accounting_date=on,
        functional_currency=MDL,
        accounting_event_id=event,
        origin=Origin(module="manual", document_type="fixture", document_id=uuid.uuid4()),
        rule_ref="fixture.closing.v1",
        description="Mișcare de fixture",
        request_id="closing",
        actor_user_id=scene["user"],
        formulas=[
            Formula(
                debit_account_id=debit,
                credit_account_id=credit,
                amount=Decimal(amount),
                currency=MDL,
                amount_currency=Decimal(amount),
                exchange_rate=Decimal(1),
                rate_date=on,
                document_date=on,
            )
        ],
    )
    return result.journal_entry_id


def periods_of(year: FiscalYear) -> list[Period]:
    return list(Period.objects.filter(fiscal_year=year).order_by("period_no"))


def close_months_but_last(scene: dict[str, Any]) -> None:
    for period in periods_of(scene["year"])[:-1]:
        close_period(period.id)


def closing_of(scene: dict[str, Any]) -> Any:
    return close_year(
        scene["year"].id,
        functional_currency=MDL,
        actor_user_id=scene["user"],
        request_id="closing",
        capability_snapshot=SNAPSHOT,
    )


def balance_of(scene: dict[str, Any], account: uuid.UUID) -> Decimal:
    rows = trial_balance(scene["company"], date(2026, 1, 1), date(2026, 12, 31)).rows
    return next((row.closing for row in rows if row.account_id == account), Decimal(0))


def correspondences(entry_id: uuid.UUID) -> list[tuple[uuid.UUID, uuid.UUID, Decimal]]:
    return [
        (f.debit_account_id, f.credit_account_id, f.amount)
        for f in JournalFormula.objects.filter(journal_entry_id=entry_id).order_by("id")
    ]


# --- the month --------------------------------------------------------------------


def test_closing_a_month_records_an_event_and_posts_nothing(
    scene: dict[str, Any], context: TenantContext
) -> None:
    with tenant_context(context):
        january = periods_of(scene["year"])[0]
        result = close_month(
            january.id,
            actor_user_id=scene["user"],
            request_id="closing",
            capability_snapshot=SNAPSHOT,
        )
        event = AccountingEvent.objects.get(pk=result.accounting_event_id)
        assert event.event_type == EVENT_MONTH
        assert event.status == "posted"
        assert not JournalEntry.objects.filter(accounting_event_id=event.id).exists()
        january.refresh_from_db()
        assert january.status == PeriodStatus.CLOSED


def test_a_month_with_an_unsettled_management_account_does_not_close(
    scene: dict[str, Any], context: TenantContext, seed: Callable[..., None]
) -> None:
    """Clasa 8 is settled by the ordinary postings; the closing only checks
    (ADR-039 section 10.1). The refusal is the primitive's, so the door and a
    direct call are refused alike."""
    with tenant_context(context):
        january = periods_of(scene["year"])[0]
        post(scene, seed, scene["cost"], scene["asset"], "100")
        with pytest.raises(ManagementAccountsNotSettledError):
            close_period(january.id)
        with pytest.raises(ManagementAccountsNotSettledError):
            close_month(
                january.id,
                actor_user_id=scene["user"],
                request_id="closing",
                capability_snapshot=SNAPSHOT,
            )
        january.refresh_from_db()
        assert january.status == PeriodStatus.OPEN

        # Settled -- the cost has left the management account -- the month closes.
        post(scene, seed, scene["expense"], scene["cost"], "100")
        close_month(
            january.id,
            actor_user_id=scene["user"],
            request_id="closing",
            capability_snapshot=SNAPSHOT,
        )


def test_a_reclosed_month_is_a_second_event_not_a_replay(
    scene: dict[str, Any], context: TenantContext
) -> None:
    with tenant_context(context):
        january = periods_of(scene["year"])[0]
        first = close_month(
            january.id,
            actor_user_id=scene["user"],
            request_id="closing",
            capability_snapshot=SNAPSHOT,
        )
        reopen_period(january.id, "corecție")
        second = close_month(
            january.id,
            actor_user_id=scene["user"],
            request_id="closing",
            capability_snapshot=SNAPSHOT,
        )
    assert first.accounting_event_id != second.accounting_event_id


# --- the exercise -------------------------------------------------------------------


def test_the_chain_closes_results_apart_from_the_tax_and_leaves_351_at_zero(
    scene: dict[str, Any], context: TenantContext, seed: Callable[..., None]
) -> None:
    """Revenue 1000, expenses 600, income tax 80 (booked before the close, as the
    accountant does): the chain sweeps 6 and 7 to 351 without 731, then 731 to
    351 as its own correspondence, then 351 to 333 -- profit 320."""
    with tenant_context(context):
        post(scene, seed, scene["asset"], scene["revenue"], "1000")
        post(scene, seed, scene["expense"], scene["asset"], "600")
        post(scene, seed, scene["tax"], scene["asset"], "80")
        close_months_but_last(scene)

        result = closing_of(scene)

        assert result.journal_entry_id is not None
        entry = JournalEntry.objects.get(pk=result.journal_entry_id)
        assert entry.entry_type == "closing"
        assert entry.rule_ref == HANDLER_YEAR
        assert entry.accounting_date == date(2026, 12, 31)
        assert correspondences(entry.id) == [
            (scene["revenue"], scene["total"], Decimal("1000.0000")),
            (scene["total"], scene["expense"], Decimal("600.0000")),
            (scene["total"], scene["tax"], Decimal("80.0000")),
            (scene["total"], scene["net"], Decimal("320.0000")),
        ]
        assert balance_of(scene, scene["total"]) == 0
        assert balance_of(scene, scene["revenue"]) == 0
        assert balance_of(scene, scene["expense"]) == 0
        assert balance_of(scene, scene["tax"]) == 0
        assert balance_of(scene, scene["net"]) == Decimal("-320.0000")

        event = AccountingEvent.objects.get(pk=result.accounting_event_id)
        assert event.event_type == EVENT_YEAR and event.status == "posted"
        # The event says what the closing stood on: the balances, and the accounts
        # the roles resolved to on that day (R13, R18).
        assert event.payload["role_accounts"][ROLE_TOTAL] == str(scene["total"])
        assert {b["account_code"] for b in event.payload["balances"]} == {"6FIX", "7FIX", "731FIX"}

        year = FiscalYear.objects.get(pk=scene["year"].id)
        assert year.status == "closed"
        assert {p.status for p in periods_of(year)} == {PeriodStatus.LOCKED}
        assert result.periods_locked == 12


def test_a_loss_goes_the_other_way(
    scene: dict[str, Any], context: TenantContext, seed: Callable[..., None]
) -> None:
    with tenant_context(context):
        post(scene, seed, scene["asset"], scene["revenue"], "500")
        post(scene, seed, scene["expense"], scene["asset"], "900")
        close_months_but_last(scene)
        result = closing_of(scene)
        assert result.journal_entry_id is not None
        assert correspondences(result.journal_entry_id)[-1] == (
            scene["net"],
            scene["total"],
            Decimal("400.0000"),
        )
        assert balance_of(scene, scene["total"]) == 0
        assert balance_of(scene, scene["net"]) == Decimal("400.0000")


def test_an_exercise_with_nothing_to_close_closes_without_an_entry(
    scene: dict[str, Any], context: TenantContext
) -> None:
    with tenant_context(context):
        close_months_but_last(scene)
        result = closing_of(scene)
        assert result.journal_entry_id is None and result.formulas == 0
        assert FiscalYear.objects.get(pk=scene["year"].id).status == "closed"


def test_the_year_does_not_close_over_an_open_month_or_a_closed_last_one(
    scene: dict[str, Any], context: TenantContext
) -> None:
    with tenant_context(context):
        with pytest.raises(PeriodsStillOpenError):
            closing_of(scene)
        for period in periods_of(scene["year"]):
            close_period(period.id)
        with pytest.raises(LastPeriodNotOpenError):
            closing_of(scene)
        assert FiscalYear.objects.get(pk=scene["year"].id).status == "open"


def test_result_accounts_must_enter_the_exercise_at_zero(
    scene: dict[str, Any], context: TenantContext, seed: Callable[..., None]
) -> None:
    """A balance carried in from before the exercise means the previous year was
    never closed here; sweeping it into this year's result would be silent."""
    with tenant_context(context):
        open_fiscal_year(scene["company"], "2025", date(2025, 1, 1), date(2025, 12, 31))
        post(scene, seed, scene["asset"], scene["revenue"], "10", on=date(2025, 12, 15))
        close_months_but_last(scene)
        with pytest.raises(ResultAccountsCarryOpeningBalanceError):
            closing_of(scene)


def test_a_closed_exercise_is_not_closed_twice(
    scene: dict[str, Any], context: TenantContext
) -> None:
    with tenant_context(context):
        close_months_but_last(scene)
        closing_of(scene)
        with pytest.raises(FiscalYearClosedError):
            closing_of(scene)


def test_the_chain_is_refused_when_the_last_month_cannot_close(
    scene: dict[str, Any], context: TenantContext, seed: Callable[..., None]
) -> None:
    """The chain posts, then the last month closes with its class-8 check, all in
    one transaction: an unsettled management account rolls the chain back too."""
    with tenant_context(context):
        post(scene, seed, scene["asset"], scene["revenue"], "100")
        post(scene, seed, scene["cost"], scene["asset"], "5", on=date(2026, 12, 10))
        close_months_but_last(scene)
        with pytest.raises(ManagementAccountsNotSettledError):
            closing_of(scene)
        assert not JournalEntry.objects.filter(entry_type="closing").exists()
        assert FiscalYear.objects.get(pk=scene["year"].id).status == "open"
