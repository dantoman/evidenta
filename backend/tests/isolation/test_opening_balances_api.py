"""The six sets of an opening batch, over HTTP -- G3 of the gap plan.

`tests/isolation/test_opening_balances.py` proves the services and
`tests/integration/test_opening_balances.py` walks the general-ledger set through
the API. What neither did was carry the three sets the endpoint refused to accept
-- stock, fixed assets, payroll cumulatives -- and without them a company put
into service in the middle of a year computed its exemptions wrong (`13` section
D10) and could not start its assets.

So this walks all six through the real chain -- host, session, middleware -- under
the application role (`T1`), validates, posts, and reads the rows back. The
payroll set's two doors are asserted where they stand: the closed vocabulary of
ADR-061 and the sign are refused by the serializer with a code, before the
database's CHECK is ever reached.

Fixture codes, never the plan's (`OD-23`); the world is the one the service tests
built, reused rather than retyped.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from evidenta.accounting.ledger.models import JournalLine
from evidenta.accounting.opening.models import (
    BatchSource,
    OpeningBalancePayrollCumulative,
)
from evidenta.accounting.opening.services.batches import create_batch
from evidenta.masterdata.uom.models import UnitOfMeasure
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.isolation.test_coa_api import HOST_A, mfa_key, signed_in  # noqa: F401
from tests.isolation.test_opening_balances import AS_OF, seed_company_world

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

BASE = "/api/v1/accounting/opening-balances"


@pytest.fixture
def scene(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> dict[str, uuid.UUID]:
    return seed_company_world(
        seed,
        world["tenant_a"],
        world["user_a"],
        company_of,
        grant_company,
        idno="1002600000702",
        name="Alpha Solduri HTTP",
    )


def get(client: Client, path: str) -> Any:
    return client.get(path, headers={"host": HOST_A})


def post(client: Client, path: str, body: dict[str, Any], **headers: str) -> Any:
    return client.post(
        path,
        data=json.dumps(body, default=str),
        content_type="application/json",
        headers={"host": HOST_A, **headers},
    )


def open_batch(client: Client, scene: dict[str, uuid.UUID]) -> str:
    response = post(
        client,
        f"{BASE}/companies/{scene['company']}",
        {
            "as_of_date": AS_OF.isoformat(),
            "source": BatchSource.ONEC_IMPORT,
            "counterpart_account_id": str(scene["counterpart"]),
        },
    )
    assert response.status_code == 201, response.content
    return str(response.json()["id"])


def six_sets(scene: dict[str, uuid.UUID], ids: dict[str, uuid.UUID]) -> dict[str, Any]:
    """The same numbers as the service test's `full_batch`, on the wire.

    GL:  cash 1000 D, stock 700 D, asset cost 500 D, receivable 300 D
         equity 1900 C, payable 400 C, depreciation 200 C
    """
    return {
        "gl": [
            {"account_id": str(scene["cash"]), "debit": "1000.0000"},
            {"account_id": str(scene["stock"]), "debit": "700.0000"},
            {"account_id": str(scene["asset_cost"]), "debit": "500.0000"},
            {"account_id": str(scene["receivable"]), "debit": "300.0000"},
            {"account_id": str(scene["equity"]), "credit": "1900.0000"},
            {"account_id": str(scene["payable"]), "credit": "400.0000"},
            {"account_id": str(scene["asset_depreciation"]), "credit": "200.0000"},
        ],
        "receivables": [
            {
                "account_id": str(scene["receivable"]),
                "partner_id": str(ids["partner_a"]),
                "debit": "300.0000",
                "document_number": "AA-0001",
                "due_date": "2026-01-30",
            }
        ],
        "payables": [
            {
                "account_id": str(scene["payable"]),
                "partner_id": str(ids["partner_b"]),
                "credit": "400.0000",
            }
        ],
        "inventory": [
            {
                "account_id": str(scene["stock"]),
                "item_id": str(ids["item"]),
                "uom_id": str(ids["uom"]),
                "quantity": "7.000000",
                "total_cost": "700.0000",
                "warehouse_id": str(ids["warehouse"]),
                "lot": "L-2025-11",
                "unit_cost": "100.000000",
            }
        ],
        "assets": [
            {
                "asset_id": str(ids["asset"]),
                "cost_account_id": str(scene["asset_cost"]),
                "depreciation_account_id": str(scene["asset_depreciation"]),
                "entry_cost": "500.0000",
                "accumulated_depreciation": "200.0000",
                "in_service_date": "2024-05-01",
                "remaining_months": 36,
            }
        ],
        "payroll_cumulatives": [
            {
                "employee_id": str(ids["employee"]),
                "code": "income_tax.taxable_income",
                "amount": "12345.6700",
                "from_date": AS_OF.isoformat(),
            },
            {
                "employee_id": str(ids["employee"]),
                "code": "income_tax.exemptions_granted",
                "amount": "0.0000",
                "from_date": AS_OF.isoformat(),
            },
        ],
    }


@pytest.fixture
def ids() -> dict[str, uuid.UUID]:
    return {
        key: uuid.uuid4()
        for key in ("partner_a", "partner_b", "item", "warehouse", "uom", "asset", "employee")
    }


def test_all_six_sets_go_in_read_back_validate_and_post(
    signed_in: Client,  # noqa: F811
    scene: dict[str, uuid.UUID],
    ids: dict[str, uuid.UUID],
    world: dict[str, uuid.UUID],
) -> None:
    """The criterion of G3, end to end, with the ledger as the last witness."""
    batch_id = open_batch(signed_in, scene)

    added = post(signed_in, f"{BASE}/{batch_id}/rows", six_sets(scene, ids))
    assert added.status_code == 200, added.content

    detail = get(signed_in, f"{BASE}/{batch_id}").json()
    assert len(detail["gl"]) == 7
    assert detail["inventory"] == [
        {
            "account_id": str(scene["stock"]),
            "item_id": str(ids["item"]),
            "warehouse_id": str(ids["warehouse"]),
            "lot": "L-2025-11",
            "quantity": "7.000000",
            "uom_id": str(ids["uom"]),
            "unit_cost": "100.000000",
            "total_cost": "700.0000",
            "currency": None,
        }
    ]
    assert detail["assets"] == [
        {
            "asset_id": str(ids["asset"]),
            "cost_account_id": str(scene["asset_cost"]),
            "depreciation_account_id": str(scene["asset_depreciation"]),
            "entry_cost": "500.0000",
            "accumulated_depreciation": "200.0000",
            "in_service_date": "2024-05-01",
            "remaining_months": 36,
        }
    ]
    assert [row["code"] for row in detail["payroll_cumulatives"]] == [
        "income_tax.exemptions_granted",
        "income_tax.taxable_income",
    ]
    # The decomposition the accountant reads: stock and the asset's two legs
    # are there beside the partner sets.
    assert detail["decomposition"][str(scene["stock"])] == "700.0000"
    assert detail["decomposition"][str(scene["asset_cost"])] == "500.0000"
    assert detail["decomposition"][str(scene["asset_depreciation"])] == "-200.0000"

    listed = get(signed_in, f"{BASE}/companies/{scene['company']}").json()
    assert listed[0]["id"] == batch_id
    assert (listed[0]["inventory_rows"], listed[0]["asset_rows"], listed[0]["payroll_rows"]) == (
        1,
        1,
        2,
    )

    validated = post(signed_in, f"{BASE}/{batch_id}/validation", {})
    assert validated.status_code == 200, validated.content
    assert validated.json()["status"] == "validated"

    posted = post(
        signed_in, f"{BASE}/{batch_id}/posting", {}, **{"Idempotency-Key": "opening-http-1"}
    )
    assert posted.status_code == 201, posted.content
    entry_id = uuid.UUID(posted.json()["journal_entry_id"])

    context = TenantContext(
        tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="opening-http"
    )
    with tenant_context(context):
        lines = list(JournalLine.objects.filter(journal_entry_id=entry_id))
        stock = [line for line in lines if line.account_id == scene["stock"]]
        assert len(stock) == 1
        assert stock[0].debit == Decimal("700.0000")
        assert stock[0].item_id == ids["item"]
        assert stock[0].warehouse_id == ids["warehouse"]
        assert stock[0].quantity == Decimal("7.000000")

        cost = [line for line in lines if line.account_id == scene["asset_cost"]]
        depreciation = [line for line in lines if line.account_id == scene["asset_depreciation"]]
        assert cost[0].debit == Decimal("500.0000")
        assert depreciation[0].credit == Decimal("200.0000")
        assert cost[0].asset_id == depreciation[0].asset_id == ids["asset"]

        # The sixth set never posts -- it is stored, frozen, for `payroll` to read.
        assert all(line.employee_id is None for line in lines)
        stored = OpeningBalancePayrollCumulative.objects.filter(batch_id=uuid.UUID(batch_id))
        assert stored.count() == 2
        assert stored.get(code="income_tax.taxable_income").amount == Decimal("12345.6700")


def test_a_negative_cumulative_is_refused_with_a_code_before_the_database(
    signed_in: Client,  # noqa: F811
    scene: dict[str, uuid.UUID],
    world: dict[str, uuid.UUID],
) -> None:
    """ADR-061's sign, at the door: a 400 with a code, not an integrity error --
    and nothing of the request stored."""
    batch_id = open_batch(signed_in, scene)
    response = post(
        signed_in,
        f"{BASE}/{batch_id}/rows",
        {
            "gl": [{"account_id": str(scene["cash"]), "debit": "100.0000"}],
            "payroll_cumulatives": [
                {
                    "employee_id": str(uuid.uuid4()),
                    "code": "income_tax.exemptions_granted",
                    "amount": "-100.0000",
                    "from_date": AS_OF.isoformat(),
                }
            ],
        },
    )
    assert response.status_code == 400, response.content
    assert response.json()["code"] == "api.invalid"

    context = TenantContext(
        tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="opening-http"
    )
    with tenant_context(context):
        assert (
            OpeningBalancePayrollCumulative.objects.filter(batch_id=uuid.UUID(batch_id)).count()
            == 0
        )
    assert get(signed_in, f"{BASE}/{batch_id}").json()["gl"] == []


def test_a_code_outside_the_vocabulary_is_refused(
    signed_in: Client,  # noqa: F811
    scene: dict[str, uuid.UUID],
) -> None:
    """The three keys of ADR-061 and nothing else. A `code` nothing reads would be
    stored, frozen and silently ignored by the first payroll run."""
    batch_id = open_batch(signed_in, scene)
    response = post(
        signed_in,
        f"{BASE}/{batch_id}/rows",
        {
            "payroll_cumulatives": [
                {
                    "employee_id": str(uuid.uuid4()),
                    "code": "salary.gross",
                    "amount": "100.0000",
                    "from_date": AS_OF.isoformat(),
                }
            ]
        },
    )
    assert response.status_code == 400, response.content
    assert response.json()["code"] == "api.invalid"
    assert "salary.gross" in response.json()["message"]


def test_an_asset_on_one_account_is_refused_by_the_database(
    signed_in: Client,  # noqa: F811
    scene: dict[str, uuid.UUID],
) -> None:
    """Cost and depreciation on one account would net to a book value and lose
    both numbers. `opening_balance_asset_two_accounts` refuses it in the
    database -- the barrier that holds against the importer -- and the
    serializer says it first, so the trip through HTTP ends in a code (`C10`)
    rather than an integrity error the client cannot branch on."""
    batch_id = open_batch(signed_in, scene)
    response = post(
        signed_in,
        f"{BASE}/{batch_id}/rows",
        {
            "assets": [
                {
                    "asset_id": str(uuid.uuid4()),
                    "cost_account_id": str(scene["asset_cost"]),
                    "depreciation_account_id": str(scene["asset_cost"]),
                    "entry_cost": "500.0000",
                    "in_service_date": "2024-05-01",
                }
            ]
        },
    )
    assert response.status_code == 400, response.content
    assert response.json()["code"] == "api.invalid"
    assert get(signed_in, f"{BASE}/{batch_id}").json()["assets"] == []


def test_another_tenants_batch_is_not_found_for_every_set(
    signed_in: Client,  # noqa: F811
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
    ids: dict[str, uuid.UUID],
) -> None:
    """IZ-04 on the rows route with the three new sets in the body: 404, and
    the batch of tenant B keeps zero rows."""
    other = seed_company_world(
        seed,
        world["tenant_b"],
        world["user_b"],
        company_of,
        grant_company,
        idno="1002600000703",
        name="Beta Solduri HTTP",
    )
    context_b = TenantContext(
        tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="opening-b"
    )
    with tenant_context(context_b):
        batch = create_batch(
            company_id=other["company"],
            as_of_date=date(2026, 1, 1),
            source=BatchSource.MANUAL,
            counterpart_account_id=other["counterpart"],
            created_by_user_id=other["user"],
        )

    response = post(signed_in, f"{BASE}/{batch.id}/rows", six_sets(other, ids))
    assert response.status_code == 404, response.content
    assert response.json()["code"] == "opening.batch_not_found"

    with tenant_context(context_b):
        assert OpeningBalancePayrollCumulative.objects.filter(batch_id=batch.id).count() == 0


def _post_full(
    client: Client, scene: dict[str, uuid.UUID], ids: dict[str, uuid.UUID], key: str
) -> Any:
    batch_id = open_batch(client, scene)
    added = post(client, f"{BASE}/{batch_id}/rows", six_sets(scene, ids))
    assert added.status_code == 200, added.content
    validated = post(client, f"{BASE}/{batch_id}/validation", {})
    assert validated.status_code == 200, validated.content
    return post(client, f"{BASE}/{batch_id}/posting", {}, **{"Idempotency-Key": key})


def test_a_second_batch_at_the_same_date_posts_only_after_the_first_is_reversed(
    scene: dict[str, uuid.UUID],
    ids: dict[str, uuid.UUID],
    signed_in: Client,  # noqa: F811
) -> None:
    """Two live opening entries double every balance and the counterpart nets to
    zero on each, so nothing else would say so. The second batch is refused by
    name while the first entry stands, and posts once that entry is reversed --
    the correction path Spec B section 8.3 keeps open, now with a registered pair."""
    first = _post_full(signed_in, scene, ids, "opening-http-first")
    assert first.status_code == 201, first.content
    first_entry = first.json()["journal_entry_id"]

    second = _post_full(signed_in, scene, ids, "opening-http-second")
    assert second.status_code == 409, second.content
    assert second.json()["code"] == "opening.already_posted"

    reversed_ = post(
        signed_in,
        f"/api/v1/accounting/entries/{first_entry}/reversal",
        {
            "company_id": str(scene["company"]),
            "reason": "solduri greșite la import",
            "accounting_date": AS_OF.isoformat(),
        },
        **{"Idempotency-Key": "opening-http-storno"},
    )
    assert reversed_.status_code in (200, 201), reversed_.content

    third = _post_full(signed_in, scene, ids, "opening-http-third")
    assert third.status_code == 201, third.content


def test_a_quantity_finer_than_its_unit_is_refused(
    scene: dict[str, uuid.UUID],
    ids: dict[str, uuid.UUID],
    signed_in: Client,  # noqa: F811
    world: dict[str, uuid.UUID],
) -> None:
    """ADR-055: the unit says how fine a quantity may be, and a finer one is
    refused rather than rounded -- here at the opening set's door, as the
    document line already does."""
    context = TenantContext(
        tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="opening-http"
    )
    with tenant_context(context):
        unit = UnitOfMeasure.objects.create(
            tenant_id=world["tenant_a"], code="BUC", name="Bucată", decimal_places=0
        )
    batch_id = open_batch(signed_in, scene)
    rows = six_sets(scene, ids)
    rows["inventory"][0]["uom_id"] = str(unit.id)
    rows["inventory"][0]["quantity"] = "7.500000"
    response = post(signed_in, f"{BASE}/{batch_id}/rows", rows)
    assert response.status_code == 422, response.content
    assert response.json()["code"] == "opening.quantity_too_fine"
