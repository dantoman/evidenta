"""The vertical slice, end to end and over HTTP.

    company -> chart of accounts -> manual journal note -> trial balance

One test that walks it exactly as a person does, through the endpoints a browser
calls, under the application role like the rest of the suite (T1). Everything it
asserts is a number or an account somebody could check by hand.

What it is here to catch is the class of failure a unit test cannot: each step
works, and the chain does not -- a company created without access, a chart with
no postable account, an entry that posts into a period nobody opened, a balance
that does not balance.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from evidenta.accounting.coa.models import CompanyAccount
from evidenta.accounting.ledger.models import JournalEntry, JournalLine
from evidenta.accounting.events.models import AccountingEvent
from evidenta.platform.rls.context import tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

IDNO = "1013600012345"
TODAY = date.today()


def _template(seed: Callable[..., None]) -> uuid.UUID:
    """A two-account published version -- the smallest chart a note can use.

    Not the real nomenclature: this suite is about the chain, and a 476-row
    fixture would make every assertion here depend on the act's content instead
    of on the posting. The loader that reads the act has its own test.
    """
    template_id, cash_id, capital_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    seed(
        "INSERT INTO coa_template (id, code, version, valid_from, source_act,"
        " status, created_at, updated_at)"
        " VALUES (%s, 'TEST', '1', '2020-01-01', 'fixture', 'published', now(), now())",
        [template_id],
    )
    for account_id, code, name, klass, balance in (
        (cash_id, "242", "Conturi curente în monedă națională", "asset", "debit"),
        (capital_id, "311", "Capital social", "equity", "credit"),
    ):
        seed(
            "INSERT INTO coa_template_account (id, template_id, account_code, name_ro,"
            " account_class, normal_balance, is_system, allows_subaccounts,"
            " currency_tracking, quantity_tracking, required_dimensions, valid_from,"
            " created_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, true, false, false, false, '{}',"
            " '2020-01-01', now())",
            [account_id, template_id, code, name, klass, balance],
        )
    return template_id


def test_the_whole_slice(
    seed: Callable[..., None],
    post: Callable[..., Any],
    get: Callable[..., Any],
    signed_in: dict[str, Any],
) -> None:
    template_id = _template(seed)

    # 1. The company. `P-9` -- the application role cannot insert this row itself.
    created = post(
        "/api/v1/companies",
        {"idno": IDNO, "legal_name": "Test Vertical SRL", "functional_currency": "MDL"},
    )
    assert created.status_code == 201, created.content
    company_id = created.json()["id"]

    # Visible immediately, because the privileged path granted the creator access
    # in the same transaction (ADR-040 2.1). Without that, this list is empty and
    # every step below fails on a company its own creator cannot see.
    assert [row["id"] for row in get("/api/v1/companies").json()] == [company_id]

    # 2. The exercise, then the chart.
    year = post(
        f"/api/v1/accounting/periods/companies/{company_id}/fiscal-years",
        {"code": str(TODAY.year), "start_date": f"{TODAY.year}-01-01",
         "end_date": f"{TODAY.year}-12-31"},
    )
    assert year.status_code == 201, year.content
    assert year.json()["periods"] == 12

    chart = post(
        f"/api/v1/accounting/coa/companies/{company_id}/chart",
        {"template_id": str(template_id)},
    )
    assert chart.status_code == 201, chart.content

    accounts = get(f"/api/v1/accounting/coa/companies/{company_id}/accounts").json()
    by_code = {row["account_code"]: row["id"] for row in accounts}
    assert set(by_code) == {"242", "311"}

    # A second chart is refused: a company has one, and a second would be a
    # second answer to "which version were these books built on".
    again = post(
        f"/api/v1/accounting/coa/companies/{company_id}/chart",
        {"template_id": str(template_id)},
    )
    assert again.status_code == 409
    assert again.json()["code"] == "coa.chart_already_instantiated"

    # 3. The manual note: 5.000,00 into the current account against capital.
    note = {
        "company_id": company_id,
        "accounting_date": str(TODAY),
        "description": "Aport la capitalul social",
        "lines": [
            {"account_id": by_code["242"], "debit": "5000.00", "credit": "0"},
            {"account_id": by_code["311"], "debit": "0", "credit": "5000.00"},
        ],
    }
    posted = post("/api/v1/accounting/entries/manual", note, **{"Idempotency-Key": "slice-0001"})
    assert posted.status_code == 201, posted.content
    assert posted.json()["posted_now"] is True

    # R19: the same key twice posts once. The second answer names the same entry.
    replay = post("/api/v1/accounting/entries/manual", note, **{"Idempotency-Key": "slice-0001"})
    assert replay.status_code == 200
    assert replay.json()["posted_now"] is False
    assert replay.json()["journal_entry_id"] == posted.json()["journal_entry_id"]

    # C9: no key, no posting. The refusal is the endpoint's, before any effect.
    keyless = post("/api/v1/accounting/entries/manual", note)
    assert keyless.status_code == 400
    assert keyless.json()["code"] == "api.idempotency_key_required"

    # 4. The chain, R13, read in the database with the amounts and the accounts.
    with tenant_context(signed_in["context"]):
        entries = list(JournalEntry.objects.filter(company_id=company_id))
        assert len(entries) == 1, "one key, one entry -- twice posted is the bug"

        lines = list(JournalLine.objects.filter(journal_entry_id=entries[0].id))
        assert len(lines) == 2
        assert sum(line.debit for line in lines) == Decimal("5000.00")
        assert sum(line.debit for line in lines) == sum(line.credit for line in lines)

        cash = CompanyAccount.objects.get(company_id=company_id, account_code="242")
        debited = next(line for line in lines if line.debit > 0)
        assert debited.account_id == cash.id

        event = AccountingEvent.objects.get(id=uuid.UUID(posted.json()["accounting_event_id"]))
        assert event.status == "posted"
        assert event.event_type == "manual.journal_entry"

    # 5. The trial balance, from the server, balanced.
    balance = get(
        f"/api/v1/accounting/ledger/companies/{company_id}/trial-balance"
        f"?from={TODAY.year}-01-01&to={TODAY.year}-12-31"
    )
    assert balance.status_code == 200, balance.content
    body = balance.json()

    rows = {row["account_code"]: row for row in body["rows"]}
    assert set(rows) == {"242", "311"}
    assert rows["242"]["debit"] == "5000.0000"
    assert rows["242"]["closing"] == "5000.0000"
    assert rows["311"]["credit"] == "5000.0000"
    # Debit-positive throughout, so a credit balance is negative rather than
    # folded into the column somebody expected it in.
    assert rows["311"]["closing"] == "-5000.0000"
    assert body["total_debit"] == body["total_credit"] == "5000.0000"
    assert body["balanced"] is True

    # The window is inclusive at both ends and the opening is what came before:
    # asked for tomorrow onwards, today's posting is an opening balance, not a
    # movement.
    tomorrow = date.fromordinal(TODAY.toordinal() + 1)
    later = get(
        f"/api/v1/accounting/ledger/companies/{company_id}/trial-balance"
        f"?from={tomorrow}&to={TODAY.year + 1}-12-31"
    ).json()
    opening = {row["account_code"]: row for row in later["rows"]}
    assert opening["242"]["opening"] == "5000.0000"
    assert opening["242"]["debit"] == "0"
