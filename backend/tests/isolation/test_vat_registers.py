"""The VAT registers on the VAT fiscal period -- ADR-090, `F2.A6` second slice.

What is proved, under the application role (`T1`):

1. **The register of deliveries equals the collected-VAT account** for the
   month: two invoices and a credit note, the credit note negative, and the
   register's VAT total is 5344's net turnover -- the criterion `F2.A6` sets.
2. **The register of purchases splits deductible from borne**: the same supplier
   invoice before and after the registration, one in 2252 and one in cost, and
   the register says which from the event the engine recorded, so 2252's
   turnover is `total_vat - non_deductible_vat`.
3. **A validated invoice that has not posted is counted, not listed**: the rows
   agree with the ledger and the count says the drawer holds more.
4. **No period, no register**: a day outside the opened periods is a refusal
   naming the period, never an empty register that reads as "nothing sold".
5. **The export is Romanian and carries the legal name**, one line per document
   and rate, totals at the end.
6. **Over HTTP**: the JSON shape, the CSV headers, `on` required, an unknown
   side refused, and a company of the other tenant absent. The VAT-period door
   opens months the registration covers and refuses months it does not.
"""

from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from django.db.models import Sum
from django.test import Client

from evidenta.accounting.ledger.models import JournalLine
from evidenta.accounting.periods.errors import VatPeriodNotFoundError
from evidenta.accounting.periods.services.vat import open_vat_periods
from evidenta.accounting.posting.services.commercial import (
    ROLE_TVA_COLECTATA,
    ROLE_TVA_DEDUCTIBILA,
)
from evidenta.operations.tax.services.vat_register import (
    UnknownRegisterSideError,
    vat_register,
    vat_register_csv,
)
from evidenta.platform.documents.services.lifecycle import validate
from evidenta.platform.rls.context import tenant_context
from tests.isolation.test_coa_api import HOST_A, mfa_key, signed_in  # noqa: F401
from tests.isolation.test_line_rounding import direction, scale, source  # noqa: F401
from tests.isolation.test_vat_on_documents import (
    BEFORE,
    ON,
    a_purchase,
    a_sale,
    issue,
    record,
    vat_world,  # noqa: F401
)

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

JANUARY = (date(2026, 1, 1), date(2026, 1, 31))


@pytest.fixture
def registers_world(vat_world: dict[str, Any]) -> dict[str, Any]:  # noqa: F811
    """The VAT world with January's fiscal period opened -- the registration
    starts on the 15th, and a month with one day as a payer is a declared month."""
    with tenant_context(vat_world["context"]):
        open_vat_periods(vat_world["company"], *JANUARY)
    return vat_world


def _turnover(world: dict[str, Any], role: str) -> Decimal:
    sums = JournalLine.objects.filter(
        company_id=world["company"], account_id=world["accounts"][role]
    ).aggregate(credit=Sum("credit"), debit=Sum("debit"))
    return Decimal(sums["credit"] or 0) - Decimal(sums["debit"] or 0)


# --- 1. deliveries against 5344 ------------------------------------------------------


def test_the_register_of_deliveries_equals_the_collected_vat_account(
    registers_world: dict[str, Any],
) -> None:
    world = registers_world
    with tenant_context(world["context"]):
        issue(world, a_sale(world, prices=("1000.00",)))
        issue(world, a_sale(world, prices=("33.33", "33.33", "33.33")))
        issue(world, a_sale(world, prices=("500.00",), nature="return"))
        register = vat_register(world["company"], side="sales", on=ON)
        collected = _turnover(world, ROLE_TVA_COLECTATA)

    assert (register.start_date, register.end_date) == JANUARY
    assert [row.kind for row in register.rows] == ["invoice", "invoice", "credit_note"]
    # The credit note enters with its sign, which is what makes the total the
    # account's net turnover rather than a gross that nothing else reports.
    assert register.rows[2].vat == Decimal("-100.00")
    assert register.total_net == Decimal("599.99")
    assert register.total_vat == Decimal("120.01")
    assert register.total_amount == Decimal("720.00")
    assert register.total_vat == collected
    assert len(register.by_regime) == 1
    assert register.by_regime[0].vat_regime_code == "taxable_standard"
    assert register.by_regime[0].vat == Decimal("120.01")
    assert register.unposted == 0


# --- 2. purchases: deductible against borne ---------------------------------------------


def test_the_register_of_purchases_splits_deductible_from_borne(
    registers_world: dict[str, Any],
) -> None:
    world = registers_world
    with tenant_context(world["context"]):
        record(world, a_purchase(world, on=BEFORE, reference="AA 0001"))
        record(world, a_purchase(world, on=ON, reference="AA 0002"))
        register = vat_register(world["company"], side="purchases", on=ON)
        deducted = -_turnover(world, ROLE_TVA_DEDUCTIBILA)

    assert [(row.supplier_document_number, row.deductible) for row in register.rows] == [
        ("AA 0001", False),
        ("AA 0002", True),
    ]
    assert register.total_vat == Decimal("400.00")
    assert register.non_deductible_vat == Decimal("200.00")
    # 2252 holds only what was deductible; the rest is in the cost account.
    assert register.total_vat - register.non_deductible_vat == deducted == Decimal("200.00")


# --- 3. counted, not listed --------------------------------------------------------------


def test_a_validated_invoice_that_has_not_posted_is_counted_not_listed(
    registers_world: dict[str, Any],
) -> None:
    world = registers_world
    with tenant_context(world["context"]):
        issue(world, a_sale(world, prices=("1000.00",)))
        waiting = a_sale(world, prices=("700.00",))
        validate(waiting)
        register = vat_register(world["company"], side="sales", on=ON)

    assert len(register.rows) == 1
    assert register.total_vat == Decimal("200.00")
    assert register.unposted == 1


# --- 4. no period, no register -------------------------------------------------------------


def test_a_day_without_a_vat_period_is_a_refusal_not_an_empty_register(
    registers_world: dict[str, Any],
) -> None:
    with tenant_context(registers_world["context"]):
        with pytest.raises(VatPeriodNotFoundError):
            vat_register(registers_world["company"], side="sales", on=date(2026, 2, 10))
        with pytest.raises(UnknownRegisterSideError):
            vat_register(registers_world["company"], side="treasury", on=ON)


# --- 5. the export -------------------------------------------------------------------------


def test_the_export_is_romanian_one_line_per_rate_and_carries_the_legal_name(
    registers_world: dict[str, Any],
) -> None:
    world = registers_world
    with tenant_context(world["context"]):
        issue(world, a_sale(world, prices=("1000.00",)))
        issue(world, a_sale(world, prices=("500.00",), nature="return"))
        text = vat_register_csv(vat_register(world["company"], side="sales", on=ON)).decode(
            "utf-8-sig"
        )

    lines = text.splitlines()
    assert lines[0] == "Data documentului;Număr;Cumpărător;Fel;Regim TVA;Cota;Fără TVA;TVA;Total"
    assert "Partener SRL" in text
    assert "Notă de credit" in text
    # ro-MD figures: decimal comma, dates as zz.ll.aaaa, the credit note negative.
    assert "20.01.2026" in lines[1]
    assert ";-100,00;" in text
    assert lines[-1].endswith("Total;;500,00;100,00;600,00")


# --- 6. over HTTP ----------------------------------------------------------------------------


def _get(client: Client, path: str, expect: int = 200) -> Any:
    response = client.get(path, headers={"host": HOST_A})
    assert response.status_code == expect, response.content
    return response


def test_the_register_and_the_periods_over_http(
    registers_world: dict[str, Any],
    signed_in: Client,  # noqa: F811 -- fixture, imported to be found
    world: dict[str, uuid.UUID],
    company_of: Any,
) -> None:
    w = registers_world
    with tenant_context(w["context"]):
        issue(w, a_sale(w, prices=("1000.00",)))
    company = w["company"]
    base = f"/api/v1/tax/vat/companies/{company}/registers"

    body = _get(signed_in, f"{base}/sales?on=2026-01-20").json()
    assert body["side"] == "sales"
    assert body["period"]["start_date"] == "2026-01-01"
    assert {key: Decimal(value) for key, value in body["totals"].items()} == {
        "net": Decimal("1000.00"),
        "vat": Decimal("200.00"),
        "total": Decimal("1200.00"),
        "non_deductible_vat": Decimal("0"),
    }
    assert body["rows"][0]["partner_name"] == "Partener SRL"
    assert body["rows"][0]["slices"][0]["vat_rate_key"] == "vat.standard"
    assert body["unposted"] == 0

    exported = _get(signed_in, f"{base}/sales?on=2026-01-20&export=csv")
    assert exported["Content-Type"].startswith("text/csv")
    assert 'filename="registrul-livrarilor-2026-01.csv"' in exported["Content-Disposition"]
    assert exported.content.decode("utf-8-sig").startswith("Data documentului;")

    assert _get(signed_in, f"{base}/sales", expect=400).json()["code"] == "tax.date_required"
    assert (
        _get(signed_in, f"{base}/treasury?on=2026-01-20", expect=400).json()["code"]
        == "tax.unknown_register_side"
    )
    assert (
        _get(signed_in, f"{base}/sales?on=2026-02-10", expect=404).json()["code"]
        == "periods.vat_period_not_found"
    )

    # The periods door: February and March are covered by the open registration;
    # December 2025 is not.
    periods = f"/api/v1/accounting/periods/companies/{company}/vat-periods"
    listed = _get(signed_in, periods).json()
    assert [row["start_date"] for row in listed] == ["2026-01-01"]
    opened = signed_in.post(
        periods,
        data=json.dumps({"first_month": "2026-02-01", "through": "2026-03-31"}),
        content_type="application/json",
        headers={"host": HOST_A},
    )
    assert opened.status_code == 201, opened.content
    assert [row["start_date"] for row in opened.json()] == ["2026-02-01", "2026-03-01"]
    refused = signed_in.post(
        periods,
        data=json.dumps({"first_month": "2025-12-01", "through": "2025-12-31"}),
        content_type="application/json",
        headers={"host": HOST_A},
    )
    assert refused.status_code == 409, refused.content
    assert refused.json()["code"] == "periods.vat_period_without_registration"

    # Another tenant's company: absent, never forbidden (IZ-04).
    other = company_of(world["tenant_b"], "1002600000923", "Beta Registre")
    _get(signed_in, f"/api/v1/tax/vat/companies/{other}/registers/sales?on=2026-01-20", 404)
    assert _get(signed_in, f"/api/v1/accounting/periods/companies/{other}/vat-periods").json() == []
