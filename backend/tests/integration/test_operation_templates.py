"""Operation templates over HTTP -- layer 4 of ADR-036 section 7.

A template is the client's shortcut to a manual note, not a second kind of
posting: it expands into a `manual.journal_entry` payload and goes through the
same engine a typed note goes through. So the assertions here are as much about
*sameness* as about the shortcut -- the entry that comes out is an ordinary
manual entry, with the same lineage and the same idempotency, and the ledger
carries no trace of which form the person filled in.

That is deliberate and worth stating: how somebody typed an entry is a property
of the interface. What happened is a property of the accounting fact, and only
the second belongs in the ledger.

The chart is a fixture and its codes say so -- the published nomenclature is
`OD-23`, and a plausible real code here would make these assertions depend on the
act instead of on the chain.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date
from typing import Any

import pytest

from tests.integration.test_opening_balances import CASH, EQUITY, _company_with_chart

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

YEAR = 2026
POSTING_DATE = date(YEAR, 3, 10)


def _definition(cash_id: str, equity_id: str) -> dict[str, Any]:
    """An encashment: the same typed amount on both sides.

    Both lines take the amount from one input, so the entry balances by
    construction. A template that could produce an unbalanced entry would be
    refused at posting, which is late -- the definition is where it is cheap.
    """
    return {
        "name": "Incasare de la client",
        "entry_description": "Incasare in contul curent",
        "lines": [
            {"account_id": cash_id, "side": "debit", "amount": {"from_input": "suma"}},
            {"account_id": equity_id, "side": "credit", "amount": {"from_input": "suma"}},
        ],
    }


def _base(company_id: str) -> str:
    return f"/api/v1/accounting/entries/companies/{company_id}/templates"


def test_a_template_is_defined_read_back_and_posted_from(
    seed: Callable[..., None], post: Callable[..., Any], get: Callable[..., Any]
) -> None:
    company_id, by_code = _company_with_chart(seed, post, get)

    created = post(_base(company_id), _definition(by_code[CASH], by_code[EQUITY]))
    assert created.status_code == 201, created.content.decode()
    template_id = created.json()["id"]

    # The inputs are derived from the lines, not declared beside them: two places
    # saying which inputs a template has is one place too many.
    assert created.json()["inputs"] == ["suma"]

    listed = get(_base(company_id)).json()
    assert [row["name"] for row in listed] == ["Incasare de la client"]
    assert listed[0]["line_count"] == 2

    posted = post(
        f"{_base(company_id)}/{template_id}/posting",
        {
            "accounting_date": POSTING_DATE.isoformat(),
            "note_id": str(uuid.uuid4()),
            "inputs": {"suma": "1500.0000"},
        },
        **{"Idempotency-Key": "template-0001"},
    )
    assert posted.status_code == 201, posted.content.decode()

    balance = get(
        f"/api/v1/accounting/ledger/companies/{company_id}/trial-balance"
        f"?from={YEAR}-01-01&to={YEAR}-12-31"
    )
    rows = {row["account_code"]: row for row in balance.json()["rows"]}
    assert rows[CASH]["debit"] == "1500.0000"
    assert rows[EQUITY]["credit"] == "1500.0000"
    assert balance.json()["balanced"] is True


def test_the_entry_is_an_ordinary_manual_note(
    seed: Callable[..., None], post: Callable[..., Any], get: Callable[..., Any]
) -> None:
    """The ledger records what happened, not which form produced it.

    Asserted through the register: an entry posted from a template is
    indistinguishable there from one typed line by line, and it has to be --
    otherwise reports would have to know about a distinction that has no
    accounting meaning.
    """
    company_id, by_code = _company_with_chart(seed, post, get)
    template_id = post(_base(company_id), _definition(by_code[CASH], by_code[EQUITY])).json()["id"]

    post(
        f"{_base(company_id)}/{template_id}/posting",
        {
            "accounting_date": POSTING_DATE.isoformat(),
            "note_id": str(uuid.uuid4()),
            "inputs": {"suma": "300.0000"},
        },
        **{"Idempotency-Key": "template-plain"},
    )

    register = get(
        f"/api/v1/accounting/ledger/companies/{company_id}/entries"
        f"?from={YEAR}-01-01&to={YEAR}-12-31"
    )
    assert register.status_code == 200, register.content.decode()
    entries = register.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["entry_type"] == "standard"


def test_a_missing_input_is_refused_with_a_stable_code(
    seed: Callable[..., None], post: Callable[..., Any], get: Callable[..., Any]
) -> None:
    """`C10`. The form and the template drifting apart is the usual cause."""
    company_id, by_code = _company_with_chart(seed, post, get)
    template_id = post(_base(company_id), _definition(by_code[CASH], by_code[EQUITY])).json()["id"]

    refused = post(
        f"{_base(company_id)}/{template_id}/posting",
        {
            "accounting_date": POSTING_DATE.isoformat(),
            "note_id": str(uuid.uuid4()),
            "inputs": {},
        },
        **{"Idempotency-Key": "template-missing"},
    )
    assert refused.status_code >= 400
    assert refused.json()["code"] == "posting.template_input_missing"


def test_an_unexpected_input_is_refused_too(
    seed: Callable[..., None], post: Callable[..., Any], get: Callable[..., Any]
) -> None:
    """Refused rather than ignored, which is the interesting half.

    A key nobody asked for is usually a form still sending a field the template
    dropped -- and silently ignoring it posts an entry the person believes
    carries information it does not.
    """
    company_id, by_code = _company_with_chart(seed, post, get)
    template_id = post(_base(company_id), _definition(by_code[CASH], by_code[EQUITY])).json()["id"]

    refused = post(
        f"{_base(company_id)}/{template_id}/posting",
        {
            "accounting_date": POSTING_DATE.isoformat(),
            "note_id": str(uuid.uuid4()),
            "inputs": {"suma": "10.0000", "tva": "2.0000"},
        },
        **{"Idempotency-Key": "template-extra"},
    )
    assert refused.status_code >= 400
    assert refused.json()["code"] == "posting.template_input_unexpected"


def test_the_same_key_posts_once(
    seed: Callable[..., None], post: Callable[..., Any], get: Callable[..., Any]
) -> None:
    """`R19` on the accounting event, unchanged by the shortcut."""
    company_id, by_code = _company_with_chart(seed, post, get)
    template_id = post(_base(company_id), _definition(by_code[CASH], by_code[EQUITY])).json()["id"]

    body = {
        "accounting_date": POSTING_DATE.isoformat(),
        "note_id": str(uuid.uuid4()),
        "inputs": {"suma": "77.0000"},
    }
    first = post(
        f"{_base(company_id)}/{template_id}/posting", body, **{"Idempotency-Key": "template-twice"}
    )
    second = post(
        f"{_base(company_id)}/{template_id}/posting", body, **{"Idempotency-Key": "template-twice"}
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["journal_entry_id"] == second.json()["journal_entry_id"]


def test_a_retired_template_leaves_the_list_and_stays_readable(
    seed: Callable[..., None], post: Callable[..., Any], get: Callable[..., Any]
) -> None:
    """Never deleted: it still explains the entries posted from it.

    Withdrawn from the list, because offering a shortcut somebody deliberately
    retired is the same defect as offering a control the server refuses.
    """
    company_id, by_code = _company_with_chart(seed, post, get)
    template_id = post(_base(company_id), _definition(by_code[CASH], by_code[EQUITY])).json()["id"]

    retired = post(f"{_base(company_id)}/{template_id}/activation", {"active": False})
    assert retired.status_code == 200, retired.content.decode()
    assert retired.json()["is_active"] is False

    assert get(_base(company_id)).json() == []
    assert len(get(f"{_base(company_id)}?include_inactive=true").json()) == 1
    assert get(f"{_base(company_id)}/{template_id}").json()["name"] == "Incasare de la client"
