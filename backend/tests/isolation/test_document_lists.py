"""The invoice registers carry each document's total -- on every row, from the server.

The screen renders `totals.total` and nothing else: it adds nothing up (`C19`),
and it has no way to get the figure per row short of one request per document.
So either the list carries the total or the register shows a dash on every
line -- which is what it did, because only the detail attached the totals.

Two things are asserted. That the list shows the figure the detail shows,
because a register and the document it opens into cannot disagree; and that the
sum is per document, because the list is one grouped query and a grouping error
would put one invoice's total on another. Over HTTP and under the application
role: the aggregate is a second query over `document_line`, and RLS must bound
it the way it bounds the rows.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from evidenta.operations.purchases.services.documents import open_purchase
from evidenta.operations.sales.services.documents import open_sale
from evidenta.platform.rls.context import tenant_context
from tests.isolation.test_coa_api import HOST_A, mfa_key, signed_in  # noqa: F401
from tests.isolation.test_line_rounding import source  # noqa: F401
from tests.isolation.test_purchases_posting import ON as PURCHASE_ON
from tests.isolation.test_purchases_posting import (
    THEIRS,
    a_purchase,
    purchases_world,  # noqa: F401
)
from tests.isolation.test_sales_posting import ON as SALE_ON
from tests.isolation.test_sales_posting import a_sale, sales_world  # noqa: F401

pytestmark = pytest.mark.django_db(databases=["default", "migration"])


def _get(client: Client, path: str) -> Any:
    response = client.get(path, headers={"host": HOST_A})
    assert response.status_code == 200, response.content
    return response.json()


def _amounts(totals: dict[str, str]) -> dict[str, Decimal]:
    return {key: Decimal(value) for key, value in totals.items()}


def _assert_register_carries_totals(
    client: Client, list_path: str, detail_path: str, expected: dict[str, str]
) -> None:
    rows = {row["id"]: row for row in _get(client, list_path)}
    assert set(rows) == set(expected)
    for document_id, total in expected.items():
        listed = _amounts(rows[document_id]["totals"])
        # The figure on the row, per document: a grouping error would show one
        # invoice's total on another, and a draft with no positions shows zero
        # rather than a dash -- it is a known nothing, not an unknown.
        assert listed["total"] == Decimal(total), document_id
        assert listed["total"] == listed["net"] + listed["vat"]
        # And the same figure the document shows when opened.
        detail = _get(client, detail_path.format(document_id))
        assert _amounts(detail["totals"]) == listed


def test_the_sales_register_carries_each_invoice_total(
    sales_world: dict[str, Any],  # noqa: F811 -- fixtures, imported to be found
    signed_in: Client,  # noqa: F811
) -> None:
    with tenant_context(sales_world["context"]):
        first = a_sale(sales_world, amount="5000.00")
        second = a_sale(sales_world, amount="1200.50")
        blank = open_sale(
            company_id=sales_world["company"],
            partner_id=sales_world["partner"],
            document_date=SALE_ON,
            revenue_kind="services",
            partner_resident=True,
            nature="delivery",
        )

    _assert_register_carries_totals(
        signed_in,
        f"/api/v1/sales/companies/{sales_world['company']}/invoices",
        "/api/v1/sales/invoices/{}",
        {str(first): "5000.00", str(second): "1200.50", str(blank): "0"},
    )


def test_the_purchase_register_carries_each_invoice_total(
    purchases_world: dict[str, Any],  # noqa: F811 -- fixtures, imported to be found
    signed_in: Client,  # noqa: F811
) -> None:
    with tenant_context(purchases_world["context"]):
        first = a_purchase(purchases_world, amount="3000.00", reference="AA 0001")
        second = a_purchase(purchases_world, amount="745.25", reference="AA 0002")
        blank = open_purchase(
            company_id=purchases_world["company"],
            partner_id=purchases_world["partner"],
            document_date=PURCHASE_ON,
            supplier_document_number="AA 0003",
            supplier_document_date=THEIRS,
            cost_destination="administrative",
            partner_resident=True,
        )

    _assert_register_carries_totals(
        signed_in,
        f"/api/v1/purchases/companies/{purchases_world['company']}/invoices",
        "/api/v1/purchases/invoices/{}",
        {str(first): "3000.00", str(second): "745.25", str(blank): "0"},
    )
