"""The closing door -- G1: the routes over the period lifecycle, under the
application role, through the HTTP client.

The rules are the engine's and are tested where they live (`test_closing.py`,
`test_ledger.py`); what these assert is that the door reaches them whole and
answers with the stable code (`C10`): the checks count what has not reached the
ledger, a closed month refuses a posting dated in it, a reopening needs its
reason and is counted, a closed exercise locks its months for good -- and none
of it exists for another tenant (IZ-04).
"""

from __future__ import annotations

import calendar
import json
import uuid
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from evidenta.accounting.periods.models import FiscalYear, Period
from evidenta.accounting.posting.formula import Formula
from evidenta.accounting.posting.invariants import Origin
from evidenta.accounting.posting.services.closing import ROLE_NET, ROLE_TAX, ROLE_TOTAL
from evidenta.accounting.posting.services.commercial import ROLE_CREANTE_TARA
from evidenta.accounting.posting.services.formulas import post_formulas
from evidenta.accounting.slots.models import AccountRoleBinding
from evidenta.operations.sales.services.issuing import issue_and_post
from evidenta.platform.documents.services.lifecycle import validate
from evidenta.platform.rls.context import tenant_context
from tests.isolation.test_coa_api import HOST_A, mfa_key, signed_in  # noqa: F401
from tests.isolation.test_formulas import seed_account
from tests.isolation.test_ledger import seed_event, seed_period
from tests.isolation.test_line_rounding import scale, source  # noqa: F401
from tests.isolation.test_sales_posting import ON, SNAPSHOT, a_sale, sales_world  # noqa: F401

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

BASE = "/api/v1/accounting/periods"
MDL = "MDL"

#: The check codes, spelled here rather than imported: the screen keys its
#: labels on these strings, so a rename on the server must break this file.
CONFIRMED = "documents_confirmed_not_posted"
DRAFT = "documents_draft"
ENTRIES = "journal_entries_draft"
EVENTS = "events_not_posted"
CLASS_8 = "management_accounts_unsettled"


@pytest.fixture
def door(
    sales_world: dict[str, Any],  # noqa: F811 -- fixtures, imported to be found
    seed: Callable[..., None],
) -> dict[str, Any]:
    """The sales world -- an open January, a numbering template, a partner, the
    sales roles -- plus what closing an exercise needs: a December for the chain
    to land in, the three role accounts of ADR-050, and a class-8 account."""
    tenant, company = sales_world["tenant"], sales_world["company"]
    with tenant_context(sales_world["context"]):
        year = FiscalYear.objects.get(company_id=company)
        january = Period.objects.get(fiscal_year=year, period_no=1)
    # Every month of the exercise, not just the two the assertions name: the
    # year closing refuses an exercise whose months do not tile it, so a
    # fixture with a gap would be testing a shape production cannot reach.
    months: dict[int, uuid.UUID] = {1: january.id}
    for number in range(2, 13):
        last_day = calendar.monthrange(2026, number)[1]
        _, period_id = seed_period(
            seed,
            tenant,
            company,
            start=f"2026-{number:02d}-01",
            end=f"2026-{number:02d}-{last_day:02d}",
            period_no=number,
            year_id=year.id,
        )
        months[number] = period_id
    december = months[12]
    roles = {
        ROLE_TOTAL: seed_account(seed, tenant, company, "351FIX"),
        ROLE_TAX: seed_account(seed, tenant, company, "731FIX"),
        ROLE_NET: seed_account(seed, tenant, company, "333FIX"),
    }
    with tenant_context(sales_world["context"]):
        for role, account in roles.items():
            AccountRoleBinding.objects.create(
                tenant_id=tenant,
                company_id=company,
                role=role,
                account_id=account,
                valid_from=date(2026, 1, 1),
                source="fixture",
            )
    return {
        **sales_world,
        "year": year.id,
        "january": january.id,
        "december": december,
        "months": months,
        "cost": seed_account(seed, tenant, company, "8FIX"),
    }


def _send(
    client: Client,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    expect: int = 200,
) -> Any:
    kwargs: dict[str, Any] = {"headers": {"host": HOST_A}}
    if body is not None:
        kwargs["data"] = json.dumps(body)
        kwargs["content_type"] = "application/json"
    response = getattr(client, method)(path, **kwargs)
    assert response.status_code == expect, response.content
    return response.json()


def _checks(client: Client, period_id: uuid.UUID) -> dict[str, dict[str, Any]]:
    rows = _send(client, "get", f"{BASE}/periods/{period_id}/closing-checks")
    return {row["code"]: row for row in rows}


def _periods(client: Client, door: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = _send(
        client, "get", f"{BASE}/companies/{door['company']}/fiscal-years/{door['year']}/periods"
    )
    return {row["id"]: row for row in rows}


def _closing(client: Client, period_id: uuid.UUID, expect: int = 200) -> Any:
    return _send(client, "post", f"{BASE}/periods/{period_id}/closing", {}, expect=expect)


def _reopening(
    client: Client, period_id: uuid.UUID, body: dict[str, Any], expect: int = 200
) -> Any:
    return _send(client, "post", f"{BASE}/periods/{period_id}/reopening", body, expect=expect)


def _issue(door: dict[str, Any], document_id: uuid.UUID) -> None:
    issue_and_post(
        document_id=document_id,
        actor_user_id=door["user"],
        request_id="closing-door",
        capability_snapshot=SNAPSHOT,
    )


# --- the checks -------------------------------------------------------------------


def test_the_checks_count_what_has_not_reached_the_ledger(
    door: dict[str, Any],
    signed_in: Client,  # noqa: F811
) -> None:
    """A validated invoice is a numbered document whose posting the closing would
    strand; a draft is unfinished work. Both counted, neither blocking -- the
    engine refuses on class 8 alone, and the door does not invent a second rule."""
    with tenant_context(door["context"]):
        validate(a_sale(door))
        a_sale(door)

    january = _checks(signed_in, door["january"])
    assert january[CONFIRMED] == {"code": CONFIRMED, "count": 1, "blocking": False}
    assert january[DRAFT] == {"code": DRAFT, "count": 1, "blocking": False}
    assert january[ENTRIES] == {"code": ENTRIES, "count": 0, "blocking": False}
    assert january[EVENTS] == {"code": EVENTS, "count": 0, "blocking": False}
    assert january[CLASS_8] == {"code": CLASS_8, "count": 0, "blocking": True}

    # The window is the month's: December sees none of January's work.
    december = _checks(signed_in, door["december"])
    assert {code: row["count"] for code, row in december.items()} == {
        CONFIRMED: 0,
        DRAFT: 0,
        ENTRIES: 0,
        EVENTS: 0,
        CLASS_8: 0,
    }


def test_an_unsettled_management_account_is_the_one_blocking_check(
    door: dict[str, Any],
    signed_in: Client,  # noqa: F811
    seed: Callable[..., None],
) -> None:
    """Clasa 8 with a balance at the month's end: the check says so beforehand,
    and the closing refuses with the same reading (ADR-039 section 10.1)."""
    on = date(2026, 1, 15)
    with tenant_context(door["context"]):
        event = seed_event(seed, door["tenant"], door["company"], door["user"])
        post_formulas(
            tenant_id=door["tenant"],
            company_id=door["company"],
            accounting_date=on,
            functional_currency=MDL,
            accounting_event_id=event,
            origin=Origin(module="manual", document_type="fixture", document_id=uuid.uuid4()),
            rule_ref="fixture.closing.v1",
            description="Cost neînchis",
            request_id="closing-door",
            actor_user_id=door["user"],
            formulas=[
                Formula(
                    debit_account_id=door["cost"],
                    credit_account_id=door["accounts"][ROLE_CREANTE_TARA],
                    amount=Decimal("100.00"),
                    currency=MDL,
                    amount_currency=Decimal("100.00"),
                    exchange_rate=Decimal(1),
                    rate_date=on,
                    document_date=on,
                )
            ],
        )

    assert _checks(signed_in, door["january"])[CLASS_8] == {
        "code": CLASS_8,
        "count": 1,
        "blocking": True,
    }
    refusal = _closing(signed_in, door["january"], expect=409)
    assert refusal["code"] == "periods.class8_not_settled"
    assert _periods(signed_in, door)[str(door["january"])]["status"] == "open"


# --- the month --------------------------------------------------------------------


def test_a_closed_month_refuses_a_posting_dated_in_it(
    door: dict[str, Any],
    signed_in: Client,  # noqa: F811
) -> None:
    """The refusal is the engine's (`R12`); the door only exposes it. Asserted
    through another door -- the sale's issuance -- so what is shown is that the
    closing reached the period the engine reads, not a flag the view set."""
    with tenant_context(door["context"]):
        late = a_sale(door)

    closed = _closing(signed_in, door["january"])
    assert closed["period"]["status"] == "closed"
    assert closed["period"]["closed_at"] is not None
    assert closed["period"]["reopened_count"] == 0
    assert uuid.UUID(closed["accounting_event_id"])

    refusal = _send(signed_in, "post", f"/api/v1/sales/invoices/{late}/issuance", {}, expect=409)
    assert refusal["code"] == "periods.period_not_open"

    # Closed twice would move the closing date to today; refused with the code.
    assert _closing(signed_in, door["january"], expect=409)["code"] == "periods.period_not_open"
    # The list agrees with the closing's own answer.
    row = _periods(signed_in, door)[str(door["january"])]
    assert (row["status"], row["period_no"], row["start_date"], row["end_date"]) == (
        "closed",
        1,
        "2026-01-01",
        "2026-01-31",
    )


def test_a_reopening_needs_its_reason_and_is_counted(
    door: dict[str, Any],
    signed_in: Client,  # noqa: F811
) -> None:
    _closing(signed_in, door["january"])

    # No reason, or a blank one: refused before the service is reached, with the
    # generic code -- the field is missing, which is a shape problem.
    assert _reopening(signed_in, door["january"], {}, expect=400)["code"] == "api.invalid"
    assert (
        _reopening(signed_in, door["january"], {"reason": "   "}, expect=400)["code"]
        == "api.invalid"
    )
    assert _periods(signed_in, door)[str(door["january"])]["status"] == "closed"

    reopened = _reopening(
        signed_in, door["january"], {"reason": "Factură sosită după închiderea lunii"}
    )
    assert reopened["status"] == "open"
    assert reopened["reopened_count"] == 1
    assert _periods(signed_in, door)[str(door["january"])]["reopened_count"] == 1

    # Open already: the reopening does not stack.
    assert (
        _reopening(signed_in, door["january"], {"reason": "din nou"}, expect=409)["code"]
        == "periods.period_not_open"
    )

    # And the month now takes the posting it refused while closed.
    with tenant_context(door["context"]):
        _issue(door, a_sale(door))
    assert _checks(signed_in, door["january"])[CONFIRMED]["count"] == 0

    # Closed again: a second closing, counted on the key, not a replay.
    closed_again = _closing(signed_in, door["january"])
    assert closed_again["period"]["status"] == "closed"
    assert closed_again["period"]["reopened_count"] == 1


# --- the exercise -----------------------------------------------------------------


def test_closing_the_exercise_locks_every_month_for_good(
    door: dict[str, Any],
    signed_in: Client,  # noqa: F811
) -> None:
    """One revenue in January; the chain sweeps it to 351 and 351 to 333, dated
    the last day, in December; then December closes and the exercise locks
    every month. `locked` is terminal, and every route says so with its code."""
    with tenant_context(door["context"]):
        _issue(door, a_sale(door, amount="5000.00"))
    # Every month but the last closes first -- the chain's precondition.
    for number in range(1, 12):
        _closing(signed_in, door["months"][number])

    closed = _send(signed_in, "post", f"{BASE}/fiscal-years/{door['year']}/closing", {})
    assert closed["fiscal_year"]["id"] == str(door["year"])
    assert closed["fiscal_year"]["status"] == "closed"
    assert uuid.UUID(closed["accounting_event_id"])
    assert uuid.UUID(closed["journal_entry_id"])
    # 6111 -> 351, then 351 -> 333: two correspondences, no tax line (nothing on 731).
    assert closed["formulas"] == 2
    assert closed["periods_locked"] == 12

    rows = _periods(signed_in, door)
    assert {row["status"] for row in rows.values()} == {"locked"}
    assert rows[str(door["december"])]["closed_at"] is not None

    # Nothing inside it moves again, and each refusal names why.
    reason = {"reason": "o corecție"}
    assert (
        _reopening(signed_in, door["january"], reason, expect=409)["code"]
        == "periods.period_locked"
    )
    assert (
        _reopening(signed_in, door["december"], reason, expect=409)["code"]
        == "periods.period_locked"
    )
    assert _closing(signed_in, door["december"], expect=409)["code"] == "periods.period_locked"
    again = _send(signed_in, "post", f"{BASE}/fiscal-years/{door['year']}/closing", {}, expect=409)
    assert again["code"] == "periods.fiscal_year_closed"


def test_the_exercise_does_not_close_over_an_open_month(
    door: dict[str, Any],
    signed_in: Client,  # noqa: F811
) -> None:
    """January still open: refused, and nothing locked -- the door does not close
    the months on the caller's behalf."""
    refusal = _send(
        signed_in, "post", f"{BASE}/fiscal-years/{door['year']}/closing", {}, expect=409
    )
    assert refusal["code"] == "periods.periods_still_open"
    assert {row["status"] for row in _periods(signed_in, door).values()} == {"open"}


# --- isolation --------------------------------------------------------------------


def test_another_tenant_finds_none_of_it(
    door: dict[str, Any],
    signed_in: Client,  # noqa: F811
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> None:
    """Tenant B's exercise and month, asked for with tenant A's session: absent
    on every route, never forbidden (IZ-04) -- a 403 would confirm the ids."""
    other = company_of(world["tenant_b"], "1002600000912", "Beta Închidere")
    grant_company(world["tenant_b"], other, world["user_b"], world["user_b"])
    year_b, period_b = seed_period(seed, world["tenant_b"], other)

    attempts: list[tuple[str, str, dict[str, Any] | None, str]] = [
        (
            "get",
            f"{BASE}/companies/{other}/fiscal-years/{year_b}/periods",
            None,
            "periods.fiscal_year_not_found",
        ),
        ("get", f"{BASE}/periods/{period_b}/closing-checks", None, "periods.period_not_found"),
        ("post", f"{BASE}/periods/{period_b}/closing", {}, "periods.period_not_found"),
        (
            "post",
            f"{BASE}/periods/{period_b}/reopening",
            {"reason": "nu e a mea"},
            "periods.period_not_found",
        ),
        ("post", f"{BASE}/fiscal-years/{year_b}/closing", {}, "periods.fiscal_year_not_found"),
        # A's own exercise reached through B's company: the same absence.
        (
            "get",
            f"{BASE}/companies/{other}/fiscal-years/{door['year']}/periods",
            None,
            "periods.fiscal_year_not_found",
        ),
    ]
    for method, path, body, code in attempts:
        assert _send(signed_in, method, path, body, expect=404)["code"] == code, path

    # And B's month is untouched by the attempts.
    with tenant_context(door["context"]):
        assert not Period.objects.filter(id=period_b).exists()
    assert (ON.year, ON.month) == (2026, 1)
