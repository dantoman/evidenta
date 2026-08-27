"""Opening balances, over HTTP, into the ledger and out again in the balance.

The services for this landed with F1.7.2 and nothing reached them, which had a
consequence that is easy to miss in a backlog: the product was usable only by a
company founded today. A firm arriving from another system had no way to bring
its balances in, so its trial balance started at zero and told the truth about
nothing.

This walks the whole way -- company, exercise, chart, batch, rows, validation,
posting -- and then reads the balance back. The last step is the point: an
opening batch that posts and does not show up in the balance has moved numbers
into a table nobody reads.

**The chart here is a fixture, and its codes say so.** The published nomenclature
is `OD-23`, open; a plausible `242` in a fixture is that content arriving through
a side door, and the assertions below would then depend on the act rather than on
the chain.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date
from typing import Any

import pytest

#: Not ``transaction=True``, and the reason is worth keeping: a transactional
#: test flushes the database at teardown **as the application role**, and
#: `entry_parameter_stamp` has no DELETE for it by design (ADR-047). The first
#: version of this file used it and died in teardown with "permission denied",
#: which reads like a broken fixture and is actually the append-only guarantee
#: working. The harness has no need for it: everything here goes through the
#: test client on one connection, and `seed()` cleans up after itself.
pytestmark = pytest.mark.django_db(databases=["default", "migration"])

IDNO = "1002600099001"
YEAR = 2026
AS_OF = date(YEAR, 1, 1)

#: Codes no chart uses. See the module docstring.
CASH = "FIXTURE-CASH"
EQUITY = "FIXTURE-EQUITY"
OPENING = "FIXTURE-OPENING"


def _template(seed: Callable[..., None]) -> uuid.UUID:
    """Three accounts: an asset, a source of funds, and the technical one.

    The technical opening account is not decoration and not a suspense bucket
    either. Every balance is posted against it, so its own balance after the
    entry is the completeness test of Spec B section 8.3: anything other than
    zero means a line went in without its mirror.
    """
    template_id = uuid.uuid4()
    seed(
        "INSERT INTO coa_template (id, code, version, valid_from, source_act,"
        " status, created_at, updated_at)"
        " VALUES (%s, 'OPENING-FIXTURE', '1', '2020-01-01', 'fixture', 'published',"
        " now(), now())",
        [template_id],
    )
    for code, name, klass, balance in (
        (CASH, "Cont de fixture pentru numerar", "asset", "debit"),
        (OPENING, "Cont de fixture, deschidere tehnica", "equity", "credit"),
        (EQUITY, "Cont de fixture pentru capital", "equity", "credit"),
    ):
        seed(
            "INSERT INTO coa_template_account (id, template_id, account_code, name_ro,"
            " account_class, normal_balance, is_system, allows_subaccounts,"
            " currency_tracking, quantity_tracking, required_dimensions, valid_from,"
            " created_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, true, false, false, false, '{}',"
            " '2020-01-01', now())",
            [uuid.uuid4(), template_id, code, name, klass, balance],
        )
    return template_id


def _company_with_chart(
    seed: Callable[..., None], post: Callable[..., Any], get: Callable[..., Any]
) -> tuple[str, dict[str, str]]:
    template_id = _template(seed)

    created = post(
        "/api/v1/companies",
        {"idno": IDNO, "legal_name": "Test Solduri SRL", "functional_currency": "MDL"},
    )
    assert created.status_code == 201, created.content
    company_id = created.json()["id"]

    year = post(
        f"/api/v1/accounting/periods/companies/{company_id}/fiscal-years",
        {"code": str(YEAR), "start_date": f"{YEAR}-01-01", "end_date": f"{YEAR}-12-31"},
    )
    assert year.status_code == 201, year.content

    chart = post(
        f"/api/v1/accounting/coa/companies/{company_id}/chart",
        {"template_id": str(template_id)},
    )
    assert chart.status_code == 201, chart.content

    accounts = get(f"/api/v1/accounting/coa/companies/{company_id}/accounts").json()
    return company_id, {row["account_code"]: row["id"] for row in accounts}


def test_a_company_can_bring_its_balances_in_and_read_them_back(
    seed: Callable[..., None], post: Callable[..., Any], get: Callable[..., Any]
) -> None:
    """The whole way, ending where an accountant would look."""
    company_id, by_code = _company_with_chart(seed, post, get)

    batch = post(
        f"/api/v1/accounting/opening-balances/companies/{company_id}",
        {
            "as_of_date": AS_OF.isoformat(),
            "source": "onec_import",
            # The account the whole set balances against, and it is named rather
            # than assumed: a wrong counterpart is a wrong opening entry that
            # balances, and those are the ones nobody notices.
            "counterpart_account_id": by_code[OPENING],
        },
    )
    assert batch.status_code == 201, batch.content
    batch_id = batch.json()["id"]
    assert batch.json()["status"] == "draft"

    # The general-ledger set balances **by itself**. The technical account is not
    # there to absorb a difference: reconciling to zero is the condition of the
    # import, not its goal, and the service says so in as many words.
    rows = post(
        f"/api/v1/accounting/opening-balances/{batch_id}/rows",
        {
            "gl": [
                {"account_id": by_code[CASH], "debit": "10000.0000", "credit": "0"},
                {"account_id": by_code[EQUITY], "debit": "0", "credit": "10000.0000"},
            ]
        },
    )
    assert rows.status_code == 200, rows.content

    detail = get(f"/api/v1/accounting/opening-balances/{batch_id}").json()
    assert len(detail["gl"]) == 2

    validated = post(f"/api/v1/accounting/opening-balances/{batch_id}/validation", {})
    assert validated.status_code == 200, validated.content
    assert validated.json()["status"] == "validated"

    posted = post(
        f"/api/v1/accounting/opening-balances/{batch_id}/posting",
        {},
        **{"Idempotency-Key": "opening-0001"},
    )
    assert posted.status_code == 201, posted.content.decode()
    assert posted.json()["posted_now"] is True

    balance = get(
        f"/api/v1/accounting/ledger/companies/{company_id}/trial-balance"
        f"?from={YEAR}-01-01&to={YEAR}-12-31"
    )
    assert balance.status_code == 200, balance.content
    by_account = {row["account_code"]: row for row in balance.json()["rows"]}

    assert by_account[CASH]["debit"] == "10000.0000"
    assert by_account[CASH]["closing"] == "10000.0000"
    assert by_account[EQUITY]["credit"] == "10000.0000"

    # The completeness test, read from the balance rather than trusted: every
    # line went in with its mirror, so the technical account nets to nothing.
    assert by_account[OPENING]["closing"] == "0.0000"
    assert balance.json()["balanced"] is True


def test_the_same_key_posts_one_opening_entry(
    seed: Callable[..., None], post: Callable[..., Any], get: Callable[..., Any]
) -> None:
    """`R19` on the accounting event, not on the endpoint.

    An opening batch posted twice doubles a company's entire starting position,
    and the second posting is not something a person notices in a balance they
    have never seen before.
    """
    company_id, by_code = _company_with_chart(seed, post, get)

    batch_id = post(
        f"/api/v1/accounting/opening-balances/companies/{company_id}",
        {
            "as_of_date": AS_OF.isoformat(),
            "source": "manual",
            "counterpart_account_id": by_code[OPENING],
        },
    ).json()["id"]
    post(
        f"/api/v1/accounting/opening-balances/{batch_id}/rows",
        {
            "gl": [
                {"account_id": by_code[CASH], "debit": "2500.0000", "credit": "0"},
                {"account_id": by_code[EQUITY], "debit": "0", "credit": "2500.0000"},
            ]
        },
    )
    post(f"/api/v1/accounting/opening-balances/{batch_id}/validation", {})

    first = post(
        f"/api/v1/accounting/opening-balances/{batch_id}/posting",
        {},
        **{"Idempotency-Key": "opening-repeat"},
    )
    second = post(
        f"/api/v1/accounting/opening-balances/{batch_id}/posting",
        {},
        **{"Idempotency-Key": "opening-repeat"},
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["journal_entry_id"] == second.json()["journal_entry_id"]
    assert second.json()["posted_now"] is False


def test_posting_without_an_idempotency_key_is_refused(
    seed: Callable[..., None], post: Callable[..., Any], get: Callable[..., Any]
) -> None:
    """`C9`. The one endpoint here with a financial effect is the one that needs it."""
    company_id, by_code = _company_with_chart(seed, post, get)

    batch_id = post(
        f"/api/v1/accounting/opening-balances/companies/{company_id}",
        {
            "as_of_date": AS_OF.isoformat(),
            "source": "manual",
            "counterpart_account_id": by_code[OPENING],
        },
    ).json()["id"]
    post(
        f"/api/v1/accounting/opening-balances/{batch_id}/rows",
        {
            "gl": [
                {"account_id": by_code[CASH], "debit": "100.0000", "credit": "0"},
                {"account_id": by_code[EQUITY], "debit": "0", "credit": "100.0000"},
            ]
        },
    )
    post(f"/api/v1/accounting/opening-balances/{batch_id}/validation", {})

    keyless = post(f"/api/v1/accounting/opening-balances/{batch_id}/posting", {})
    assert keyless.status_code == 400


def test_an_abandoned_batch_can_be_found_again(
    seed: Callable[..., None], post: Callable[..., Any], get: Callable[..., Any]
) -> None:
    """The listing, and the reason it is not a convenience.

    A batch is never deleted, and three of its four states outlive the session
    that created them. Without a way back to yesterday's draft, the next import
    starts from zero beside it and the company ends up holding two partial
    pictures of one opening position -- both plausible, neither complete.
    """
    company_id, by_code = _company_with_chart(seed, post, get)

    started = post(
        f"/api/v1/accounting/opening-balances/companies/{company_id}",
        {
            "as_of_date": AS_OF.isoformat(),
            "source": "onec_import",
            "counterpart_account_id": by_code[OPENING],
        },
    ).json()["id"]
    post(
        f"/api/v1/accounting/opening-balances/{started}/rows",
        {
            "gl": [
                {"account_id": by_code[CASH], "debit": "40.0000", "credit": "0"},
                {"account_id": by_code[EQUITY], "debit": "0", "credit": "40.0000"},
            ]
        },
    )

    listed = get(f"/api/v1/accounting/opening-balances/companies/{company_id}")
    assert listed.status_code == 200, listed.content.decode()
    rows = listed.json()

    assert [row["id"] for row in rows] == [started]
    assert rows[0]["status"] == "draft"
    # Counts, not contents: a list screen needs to know the batch holds two rows,
    # not what they are.
    assert rows[0]["gl_rows"] == 2
    assert rows[0]["receivable_rows"] == 0
