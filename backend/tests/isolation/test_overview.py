"""The control panel -- the read side of the ledger, under the application role.

The panel is a **reading**, so what is asserted here is not that a note posts:
that is `test_manual_entry`'s, and repeating it would be repeating a fixture. It
is that the reading is over the window it says it is over, that it carries what a
reader needs to tell a posting from a cancelled one, and that it stops at the
tenant boundary like every other read.

`T1`: under the application role, through the same policies a request goes
through. A panel that only added up because the seeding connection could see more
would be a panel that shows one tenant's turnover to another.

The amounts are chosen so no two sums coincide -- 1000, 2500, 400, 700. A month
that accidentally equalled the year to date would let a wrong window pass.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from evidenta.accounting.ledger.services.overview import company_overview
from evidenta.accounting.posting.services.manual import (
    NUMBERING_DOCUMENT_TYPE,
    post_manual_entry,
)
from evidenta.accounting.posting.services.reversal import post_reversal
from evidenta.accounting.slots.models import AccountRoleBinding
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

#: The day the panel is asked for. Mid-month on purpose: the month it reports is
#: the whole of March, and a service that stopped at the 10th would say so.
ASKED_ON = date(2026, 3, 10)

SNAPSHOT: dict[str, Any] = {
    "version": 1,
    "on": ASKED_ON.isoformat(),
    "activated": [],
    "usable": [],
}


def seed_account(
    seed: Callable[..., None], tenant_id: uuid.UUID, company_id: uuid.UUID, code: str
) -> uuid.UUID:
    """One account of the company's own, carrying nothing.

    The codes are `FIXTURE-*`: the content of the published chart is `OD-23`,
    open, and a plausible `241` in a fixture is that content arriving through the
    back door (R15).
    """
    account_id = uuid.uuid4()
    seed(
        "INSERT INTO company_account (id, tenant_id, company_id, account_code,"
        " parent_id, origin, template_account_id, name_ro, account_class,"
        " normal_balance, allows_subaccounts, currency_tracking, quantity_tracking,"
        " required_dimensions, slot_1_dimension, slot_2_dimension, slot_3_dimension,"
        " slot_4_dimension, is_blocked, valid_from, valid_to, created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, NULL, 'company', NULL, %s, 'asset', 'debit',"
        " false, false, false, '{}'::text[], NULL, NULL, NULL, NULL, false,"
        " '2020-01-01', NULL, now(), now())",
        [account_id, tenant_id, company_id, code, f"Cont de fixture {code}"],
    )
    return account_id


def seed_month(
    seed: Callable[..., None],
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    year_id: uuid.UUID,
    *,
    period_no: int,
    start: str,
    end: str,
) -> uuid.UUID:
    period_id = uuid.uuid4()
    seed(
        "INSERT INTO period (id, tenant_id, company_id, fiscal_year_id, period_no,"
        " start_date, end_date, status, reopened_count, closed_at, created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, 'open', 0, NULL, now(), now())",
        [period_id, tenant_id, company_id, year_id, period_no, start, end],
    )
    return period_id


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="panel")


@pytest.fixture
def scene(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> dict[str, uuid.UUID]:
    """One company, the first three months of 2026 open, two accounts, a template."""
    tenant = world["tenant_a"]
    company = company_of(tenant, "1002600000901", "Alpha Panou")
    grant_company(tenant, company, world["user_a"], world["user_a"])

    year_id = uuid.uuid4()
    seed(
        "INSERT INTO fiscal_year (id, tenant_id, company_id, code, start_date, end_date,"
        " status, created_at, updated_at)"
        " VALUES (%s, %s, %s, '2026', '2026-01-01', '2026-12-31', 'open', now(), now())",
        [year_id, tenant, company],
    )
    for period_no, (start, end) in enumerate(
        [("2026-01-01", "2026-01-31"), ("2026-02-01", "2026-02-28"), ("2026-03-01", "2026-03-31")],
        start=1,
    ):
        seed_month(seed, tenant, company, year_id, period_no=period_no, start=start, end=end)

    seed(
        "INSERT INTO numbering_template (id, tenant_id, company_id, document_type,"
        " series, prefix, suffix, separator, digits, include_year, year_format,"
        " reset_policy, regime, valid_from, created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, '', 'NC', '', '-', 4, true, 'yyyy', 'yearly',"
        " 'own', DATE '2000-01-01', now(), now())",
        [uuid.uuid4(), tenant, company, NUMBERING_DOCUMENT_TYPE],
    )

    return {
        "tenant": tenant,
        "company": company,
        "user": world["user_a"],
        "debit_account": seed_account(seed, tenant, company, "FIXTURE-D"),
        "credit_account": seed_account(seed, tenant, company, "FIXTURE-C"),
    }


def post(scene: dict[str, uuid.UUID], amount: str, *, on: date, key: str) -> uuid.UUID:
    """One note through the engine (R9), and its entry."""
    result = post_manual_entry(
        tenant_id=scene["tenant"],
        company_id=scene["company"],
        accounting_date=on,
        functional_currency="MDL",
        note_id=uuid.uuid5(uuid.NAMESPACE_URL, key),
        payload={
            "description": f"Nota {key}",
            "lines": [
                {"account_id": str(scene["debit_account"]), "debit": amount, "credit": "0"},
                {"account_id": str(scene["credit_account"]), "debit": "0", "credit": amount},
            ],
        },
        idempotency_key=key,
        actor_user_id=scene["user"],
        request_id="panel-test",
        capability_snapshot=dict(SNAPSHOT),
    )
    return result.journal_entry_id


def three_months(scene: dict[str, uuid.UUID]) -> None:
    """January, February and March, with two notes in March."""
    post(scene, "1000.0000", on=date(2026, 1, 15), key="jan")
    post(scene, "2500.0000", on=date(2026, 2, 10), key="feb")
    post(scene, "400.0000", on=date(2026, 3, 2), key="mar-1")
    post(scene, "700.0000", on=date(2026, 3, 9), key="mar-2")


def test_the_month_is_the_whole_month_and_not_the_day_it_was_asked_on(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Asked on the 10th, the panel answers for the 1st to the 31st.

    The window is stated with the figure precisely so this is checkable: a
    turnover cut at the day the question was asked is not comparable with the
    previous month's, and the panel puts the two beside each other.
    """
    with tenant_context(context):
        three_months(scene)
        panel = company_overview(scene["company"], ASKED_ON)

    assert (panel.month.start_date, panel.month.end_date) == (
        date(2026, 3, 1),
        date(2026, 3, 31),
    )
    assert panel.month.debit == Decimal("1100.0000")
    assert panel.month.balanced

    assert panel.previous_month.start_date == date(2026, 2, 1)
    assert panel.previous_month.debit == Decimal("2500.0000")

    # From the first of January to the end of the month reported, so the KPI and
    # the check below it cannot disagree about where March ends.
    assert (panel.year_to_date.start_date, panel.year_to_date.end_date) == (
        date(2026, 1, 1),
        date(2026, 3, 31),
    )
    assert panel.year_to_date.debit == Decimal("4600.0000")


def test_the_series_carries_six_months_and_the_empty_ones_are_zeros(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """A month with no postings is a zero in its place, never a missing bar.

    Dropped, the chart would draw four months under six labels -- or worse, six
    bars whose labels have slipped by two.
    """
    with tenant_context(context):
        three_months(scene)
        panel = company_overview(scene["company"], ASKED_ON)

    assert [window.start_date for window in panel.series] == [
        date(2025, 10, 1),
        date(2025, 11, 1),
        date(2025, 12, 1),
        date(2026, 1, 1),
        date(2026, 2, 1),
        date(2026, 3, 1),
    ]
    assert panel.series[0].debit == Decimal("0")
    assert panel.series[-1] == panel.month


def test_the_extract_is_newest_first_and_says_what_was_cancelled(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Both halves of R14 travel with the row, as they do on the register.

    A panel that showed a reversed entry as a plain posting would be showing an
    amount that is no longer in the books -- five rows is exactly the size at
    which nobody would check.
    """
    with tenant_context(context):
        three_months(scene)
        cancelled = post(scene, "300.0000", on=date(2026, 3, 9), key="mar-3")
        post_reversal(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            entry_id=cancelled,
            accounting_date=date(2026, 3, 9),
            reason="Nota a fost inregistrata de doua ori",
            idempotency_key="mar-3-storno",
            actor_user_id=scene["user"],
            request_id="panel-test",
            capability_snapshot=dict(SNAPSHOT),
        )
        panel = company_overview(scene["company"], ASKED_ON)

    assert len(panel.latest_entries) == 5
    dates = [entry.accounting_date for entry in panel.latest_entries]
    assert dates == sorted(dates, reverse=True)

    storno = panel.latest_entries[0]
    assert storno.entry_type == "reversal"
    assert storno.reverses_entry_id == cancelled

    reversed_entry = next(entry for entry in panel.latest_entries if entry.id == cancelled)
    assert reversed_entry.reversed_by_entry_id == storno.id


def test_the_cash_tile_is_absent_until_the_chart_binds_an_account(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Unbound is `None`, never `0,00`.

    A zero is a statement about a company's till. "Nobody has said which account
    this is" is a statement about the chart, and only one of the two is true here
    -- which is why the panel has to be able to tell them apart (R28).

    The binding is written through the application role inside the test's own
    transaction, not seeded: the row would otherwise outlive the test on the
    admin connection, and the next test's cleanup would meet a foreign key
    pointing at the account it is trying to delete. Measured, once.
    """
    with tenant_context(context):
        three_months(scene)
        assert company_overview(scene["company"], ASKED_ON).cash is None

        AccountRoleBinding.objects.create(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            role="CASA_MDL",
            account_id=scene["debit_account"],
            valid_from=date(2020, 1, 1),
            source="fixture",
        )
        cash = company_overview(scene["company"], ASKED_ON).cash

    assert cash is not None
    # Everything debited to it since the ledger began, not only this month's:
    # a balance is not a turnover.
    assert cash.balance == Decimal("4600.0000")
    assert cash.account_code == "FIXTURE-D"


def test_the_panel_stops_at_the_tenant_boundary(
    world: dict[str, uuid.UUID], context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The same company id, read from the other tenant: zeros and nothing else.

    Absence rather than refusal (IZ-04) -- and zeros rather than an error,
    because that is what a panel over an empty ledger looks like. What must not
    happen is a figure.
    """
    with tenant_context(context):
        three_months(scene)

    intruder = TenantContext(
        tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="panel-intruder"
    )
    with tenant_context(intruder):
        panel = company_overview(scene["company"], ASKED_ON)

    assert panel.month.debit == Decimal("0")
    assert panel.year_to_date.debit == Decimal("0")
    assert panel.latest_entries == ()
    assert panel.cash is None
    assert panel.draft_entries == 0
