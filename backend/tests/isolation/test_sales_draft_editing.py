"""A draft invoice is rewritten and thrown away; anything numbered is neither.

Over HTTP and under the application role. The rule itself is the document
core's and is tested there (`test_documents.py`); what these assert is that the
sales routes reach it whole: header and positions rewritten in one request, the
answer equal to the document reopened, the register in agreement, nothing
numbered by editing -- and past draft the stable code (`C10`), not a 500 from
the trigger that would have refused the write anyway.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from evidenta.operations.sales.models import SalesDocument
from evidenta.operations.sales.services.issuing import issue_and_post
from evidenta.operations.sales.types import SALES_DOCUMENT
from evidenta.platform.documents.services.lifecycle import open_draft, validate
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.isolation.test_coa_api import HOST_A, mfa_key, signed_in  # noqa: F401
from tests.isolation.test_line_rounding import scale, source  # noqa: F401
from tests.isolation.test_manual_entry import seed_template as seed_numbering
from tests.isolation.test_sales_posting import ON, SNAPSHOT, a_sale, sales_world  # noqa: F401

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

#: What a company not registered for VAT may state on a line (ADR-089).
NO_VAT = "fara_tva"


@pytest.fixture
def priced(seed: Callable[..., None], world: dict[str, uuid.UUID]) -> None:
    """The unit-price scale, which pricing a line reads and `sales_world` does not
    seed: its sales are written with their amounts given, while a rewrite over
    HTTP is priced from what was typed."""
    scale(seed, world, "accounting.unit_price_scale", 4)


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
    return None if response.status_code == 204 else response.json()


def _rewrite(world: dict[str, Any]) -> dict[str, Any]:
    """Every header field different from what `a_sale` opens, and two positions
    instead of one, so an unchanged field is a field the route did not carry."""
    return {
        "partner_id": str(world["partner"]),
        "document_date": "2026-01-22",
        "nature": "return",
        "revenue_kind": "goods",
        "partner_resident": False,
        "lines": [
            {
                "description": "Mărfuri returnate",
                "quantity": "3",
                "unit_price": "100.00",
                "vat_regime_code": NO_VAT,
            },
            {
                "description": "Ambalaj",
                "quantity": "1",
                "unit_price": "12.50",
                "vat_regime_code": NO_VAT,
            },
        ],
    }


def test_a_draft_is_rewritten_in_full_and_stays_a_draft(
    sales_world: dict[str, Any],  # noqa: F811 -- fixtures, imported to be found
    priced: None,
    signed_in: Client,  # noqa: F811
) -> None:
    with tenant_context(sales_world["context"]):
        draft = a_sale(sales_world, amount="5000.00")
    path = f"/api/v1/sales/invoices/{draft}"

    before = _send(signed_in, "get", path)
    assert before["state"] == "draft"
    assert before["formatted_number"] is None
    assert [line["description"] for line in before["lines"]] == ["Servicii de contabilitate"]

    after = _send(signed_in, "put", path, _rewrite(sales_world))

    # The same document, still unnumbered: editing allocates nothing.
    assert after["id"] == str(draft)
    assert after["state"] == "draft"
    assert after["formatted_number"] is None
    # The core's header and the type's own row, both rewritten.
    assert after["document_date"] == "2026-01-22"
    # The second date follows the first when the body does not say otherwise --
    # the same default opening a draft applies, and not a stale copy of the old.
    assert after["accounting_date"] == "2026-01-22"
    assert after["nature"] == "return"
    assert after["revenue_kind"] == "goods"
    assert after["partner_resident"] is False
    # The positions replaced as a block, renumbered from 1, and given back at
    # the scale they were typed rather than the scale they are stored.
    assert [
        (line["line_no"], line["description"], line["quantity"], line["unit_price"])
        for line in after["lines"]
    ] == [(1, "Mărfuri returnate", "3", "100"), (2, "Ambalaj", "1", "12.5")]
    totals = {key: Decimal(value) for key, value in after["totals"].items()}
    assert totals == {"net": Decimal("312.50"), "vat": Decimal("0"), "total": Decimal("312.50")}

    # Reopened, it is what the rewrite answered; and the register agrees.
    assert _send(signed_in, "get", path) == after
    rows = {
        row["id"]: row
        for row in _send(
            signed_in, "get", f"/api/v1/sales/companies/{sales_world['company']}/invoices"
        )
    }
    assert Decimal(rows[str(draft)]["totals"]["total"]) == Decimal("312.50")
    assert rows[str(draft)]["revenue_kind"] == "goods"


def test_a_refused_line_leaves_the_draft_as_it_was(
    sales_world: dict[str, Any],  # noqa: F811
    priced: None,
    signed_in: Client,  # noqa: F811
) -> None:
    """Header and positions are one request, so a refusal on a line is a
    refusal of the whole rewrite -- not a new header over the old positions."""
    with tenant_context(sales_world["context"]):
        draft = a_sale(sales_world, amount="5000.00")
    path = f"/api/v1/sales/invoices/{draft}"

    body = _rewrite(sales_world)
    # The company is not registered for VAT, so a regime is refused by name.
    body["lines"][1]["vat_regime_code"] = "taxable_standard"
    refused = _send(signed_in, "put", path, body, expect=422)
    assert refused["code"] == "sales.vat_regime_requires_registration"

    unchanged = _send(signed_in, "get", path)
    assert unchanged["document_date"] == str(ON)
    assert unchanged["revenue_kind"] == "services"
    assert unchanged["partner_resident"] is True
    assert [line["description"] for line in unchanged["lines"]] == ["Servicii de contabilitate"]


def test_past_draft_the_document_is_neither_rewritten_nor_deleted(
    sales_world: dict[str, Any],  # noqa: F811
    signed_in: Client,  # noqa: F811
) -> None:
    """Validated or posted, the answer is the same and the code is the same:
    the number is out, the correction is a reversal (`R10`, one layer up)."""
    with tenant_context(sales_world["context"]):
        validated = a_sale(sales_world)
        validate(validated)
        posted = a_sale(sales_world)
        issue_and_post(
            document_id=posted,
            actor_user_id=sales_world["user"],
            request_id="draft-editing-posted",
            capability_snapshot=SNAPSHOT,
        )

    for document, state in ((validated, "confirmed"), (posted, "posted")):
        path = f"/api/v1/sales/invoices/{document}"
        refused = _send(signed_in, "put", path, _rewrite(sales_world), expect=409)
        assert refused["code"] == "documents.not_editable", state
        refused = _send(signed_in, "delete", path, expect=409)
        assert refused["code"] == "documents.not_editable", state

        detail = _send(signed_in, "get", path)
        assert detail["state"] == state
        assert detail["formatted_number"] is not None
        assert detail["document_date"] == str(ON)
        assert [line["description"] for line in detail["lines"]] == ["Servicii de contabilitate"]


def test_a_draft_is_deleted_and_the_register_no_longer_lists_it(
    sales_world: dict[str, Any],  # noqa: F811
    signed_in: Client,  # noqa: F811
) -> None:
    with tenant_context(sales_world["context"]):
        gone = a_sale(sales_world)
        kept = a_sale(sales_world, amount="1.00")
    path = f"/api/v1/sales/invoices/{gone}"

    assert _send(signed_in, "delete", path, expect=204) is None
    assert _send(signed_in, "get", path, expect=404)["code"] == "documents.not_found"
    rows = _send(signed_in, "get", f"/api/v1/sales/companies/{sales_world['company']}/invoices")
    assert {row["id"] for row in rows} == {str(kept)}


def test_another_tenants_draft_is_not_there_to_rewrite_or_delete(
    sales_world: dict[str, Any],  # noqa: F811
    signed_in: Client,  # noqa: F811
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
    seed: Callable[..., None],
) -> None:
    """404, never 403 (IZ-04): "exists and is not yours" over a range of
    identifiers is an enumeration oracle. And nothing moves on the other side."""
    foreign_company = company_of(world["tenant_b"], "1002600000913", "Beta Vânzări")
    grant_company(world["tenant_b"], foreign_company, world["user_b"], world["user_b"])
    seed_numbering(seed, world["tenant_b"], foreign_company, document_type=SALES_DOCUMENT)
    foreign = TenantContext(
        tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="setup"
    )
    with tenant_context(foreign):
        document = open_draft(
            company_id=foreign_company, document_type=SALES_DOCUMENT, document_date=ON
        )
        SalesDocument.objects.create(
            document=document,
            tenant_id=document.tenant_id,
            company_id=document.company_id,
            nature="delivery",
            revenue_kind="services",
            partner_resident=True,
        )
    path = f"/api/v1/sales/invoices/{document.id}"

    refused = _send(signed_in, "put", path, _rewrite(sales_world), expect=404)
    assert refused["code"] == "documents.not_found"
    refused = _send(signed_in, "delete", path, expect=404)
    assert refused["code"] == "documents.not_found"

    with tenant_context(foreign):
        row = SalesDocument.objects.select_related("document").get(document_id=document.id)
        assert row.document.state == "draft"
        assert row.revenue_kind == "services"
