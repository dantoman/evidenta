"""The partner directory over HTTP -- the surface an opening receivable needs.

The module had a table and nothing else: no service, no route. The consequence
showed up one layer out, in a screen that could not offer receivables because a
form asking a person for a `partner_id` is a form nobody can fill in correctly.

So the assertions here are mostly about *finding* rather than about storing. What
a person has in front of them is the name on the document and the IDNO on it, and
those are what the search has to match.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

BASE = "/api/v1/masterdata/partners/"

CLIENT = {
    "legal_name": "Alfa Comert SRL",
    "short_name": "Alfa",
    "idno": "1003600012345",
    "is_customer": True,
}
SUPPLIER = {
    "legal_name": "Beta Furnizor SRL",
    "idno": "1003600054321",
    "is_supplier": True,
}


def test_a_partner_is_recorded_and_found_again(
    post: Callable[..., Any], get: Callable[..., Any]
) -> None:
    created = post(BASE, CLIENT)
    assert created.status_code == 201, created.content.decode()
    assert created.json()["legal_name"] == "Alfa Comert SRL"
    assert created.json()["is_active"] is True

    post(BASE, SUPPLIER)

    # By name, case-insensitively: nobody types the case off an invoice.
    assert [row["legal_name"] for row in get(f"{BASE}?q=alfa").json()] == ["Alfa Comert SRL"]
    # By the short name, which exists for the interface and never reaches a
    # printed document (C39).
    assert len(get(f"{BASE}?q=Alfa").json()) == 1
    # By IDNO, from the start: a person copying a number off an invoice copies it
    # from the beginning.
    assert [row["idno"] for row in get(f"{BASE}?q=10036000543").json()] == ["1003600054321"]


def test_the_roles_narrow_the_directory(post: Callable[..., Any], get: Callable[..., Any]) -> None:
    """One record with two flags, not two records that disagree about the address."""
    post(BASE, CLIENT)
    post(BASE, SUPPLIER)
    both = post(BASE, {"legal_name": "Gama Mixt SRL", "is_customer": True, "is_supplier": True})
    assert both.status_code == 201, both.content.decode()

    customers = {row["legal_name"] for row in get(f"{BASE}?role=customer").json()}
    suppliers = {row["legal_name"] for row in get(f"{BASE}?role=supplier").json()}

    assert customers == {"Alfa Comert SRL", "Gama Mixt SRL"}
    assert suppliers == {"Beta Furnizor SRL", "Gama Mixt SRL"}


def test_a_partner_with_no_role_is_refused(post: Callable[..., Any]) -> None:
    """A record nothing can be posted against. The database refuses it too."""
    refused = post(BASE, {"legal_name": "Delta Nimic SRL"})
    assert refused.status_code == 422
    assert refused.json()["code"] == "partners.malformed"


def test_a_second_record_for_one_idno_is_refused(post: Callable[..., Any]) -> None:
    """Refused rather than merged.

    By the time anybody notices, the balances have already split between the two
    records -- and it surfaces as a reconciliation that will not close, far from
    the screen where the duplicate was created.
    """
    assert post(BASE, CLIENT).status_code == 201
    clash = post(BASE, {**CLIENT, "legal_name": "Alfa Comert SRL (vechi)"})

    assert clash.status_code == 409
    assert clash.json()["code"] == "partners.idno_taken"


def test_a_malformed_idno_is_refused(post: Callable[..., Any]) -> None:
    """Thirteen digits. Checked here rather than discovered on an invoice."""
    refused = post(BASE, {**CLIENT, "idno": "1234"})
    assert refused.status_code == 422
    assert refused.json()["code"] == "partners.malformed"


def test_a_retired_partner_leaves_the_directory_and_stays_readable(
    post: Callable[..., Any], get: Callable[..., Any]
) -> None:
    """Never deleted: entries posted against it still name it."""
    partner_id = post(BASE, CLIENT).json()["id"]

    retired = post(f"{BASE}{partner_id}/activation", {"active": False})
    assert retired.status_code == 200, retired.content.decode()
    assert retired.json()["is_active"] is False

    assert get(BASE).json() == []
    assert len(get(f"{BASE}?include_inactive=true").json()) == 1
    assert get(f"{BASE}{partner_id}").json()["legal_name"] == "Alfa Comert SRL"
