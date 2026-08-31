"""The document journal -- F1.8, the report that waited for something to list.

It was blocked by its own definition: "per document by definition" (ADR-053), and
until the commercial families posted, no document existed to appear in it. These
tests are the first that could have been written.

What they check is mostly what the report refuses to be: it lists a family without
knowing that family's type codes, it carries the **legal** name rather than an
identifier, and its VAT column is present and zero rather than absent -- a register
whose columns changed with its content could not be compared with the next
month's.

Under the application role (`T1`).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from evidenta.accounting.ledger.services.document_journal import document_journal
from evidenta.accounting.ledger.services.export import document_journal_csv
from evidenta.accounting.posting.services.commercial import (
    ROLE_CASA_MDL,
    ROLE_CREANTE_STRAINATATE,
    ROLE_CREANTE_TARA,
    ROLE_VENIT_SERVICII,
)
from evidenta.accounting.slots.models import AccountRoleBinding
from evidenta.operations.sales.services.documents import open_sale
from evidenta.operations.sales.services.issuing import issue_and_post
from evidenta.operations.treasury.services.documents import open_receipt
from evidenta.operations.treasury.services.recording import record_and_post
from evidenta.platform.documents.services.lines import LineInput, replace_lines
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.isolation.test_formulas import seed_account
from tests.isolation.test_ledger import seed_period
from tests.isolation.test_line_rounding import direction, scale, source  # noqa: F401
from tests.isolation.test_manual_entry import seed_template as seed_numbering

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

JANUARY = (date(2026, 1, 1), date(2026, 1, 31))
ON = date(2026, 1, 20)
SNAPSHOT: dict[str, Any] = {"version": 1, "on": "2026-01-01", "activated": [], "usable": []}

ROLE_ACCOUNT_CODES = {
    ROLE_CREANTE_TARA: "2211",
    ROLE_CREANTE_STRAINATATE: "2212",
    ROLE_VENIT_SERVICII: "6111",
    ROLE_CASA_MDL: "2411",
}


@pytest.fixture
def journal_world(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
    source: uuid.UUID,  # noqa: F811 -- the fiscal act fixture, imported to be found
) -> dict[str, Any]:
    tenant = world["tenant_a"]
    company = company_of(tenant, "1002600000917", "Alpha Jurnale")
    grant_company(tenant, company, world["user_a"], world["user_a"])
    seed_period(seed, tenant, company)
    seed_numbering(seed, tenant, company)
    for document_type in ("sales.document", "treasury.receipt"):
        seed_numbering(seed, tenant, company, document_type=document_type)
    scale(seed, world, "accounting.amount_scale", 2)
    direction(seed, world, "half_up")

    context = TenantContext(tenant_id=tenant, user_id=world["user_a"], request_id="journal")
    accounts = {
        role: seed_account(seed, tenant, company, code) for role, code in ROLE_ACCOUNT_CODES.items()
    }
    partner_id = uuid.uuid4()
    seed(
        "INSERT INTO partner (id, tenant_id, kind, legal_name, internal_name, is_customer,"
        " is_supplier, is_active, created_at, updated_at)"
        " VALUES (%s, %s, 'legal_entity', 'Societatea Comercială \"Beta\" SRL',"
        " 'beta (client vechi)', true, false, true, now(), now())",
        [partner_id, tenant],
    )
    with tenant_context(context):
        for role, account in accounts.items():
            AccountRoleBinding.objects.create(
                tenant_id=tenant,
                company_id=company,
                role=role,
                account_id=account,
                valid_from=date(2026, 1, 1),
                source="fixture",
            )
    return {
        "tenant": tenant,
        "company": company,
        "user": world["user_a"],
        "partner": partner_id,
        "context": context,
    }


def an_invoice(world: dict[str, Any], *, amount: str, on: date = ON) -> uuid.UUID:
    document_id = open_sale(
        company_id=world["company"],
        partner_id=world["partner"],
        document_date=on,
        revenue_kind="services",
        partner_resident=True,
    )
    replace_lines(
        document_id,
        [
            LineInput(
                description="Servicii",
                quantity=Decimal("1"),
                unit_price=Decimal(amount),
                net_amount=Decimal(amount),
                vat_amount=Decimal("0"),
                total_amount=Decimal(amount),
                vat_regime_code="fara_tva",
                vat_rate=Decimal("0"),
            )
        ],
    )
    issue_and_post(
        document_id=document_id,
        actor_user_id=world["user"],
        request_id="journal-invoice",
        capability_snapshot=SNAPSHOT,
    )
    return document_id


def test_the_journal_lists_a_family_without_naming_its_types(
    journal_world: dict[str, Any],
) -> None:
    """`sales`, not `sales.document` -- the registry answers which codes that is.

    A receipt is posted in the same window and must not appear: it belongs to
    another module, and the journal asked for a family rather than for everything
    the company posted.
    """
    with tenant_context(journal_world["context"]):
        an_invoice(journal_world, amount="1000.00")
        receipt = open_receipt(
            company_id=journal_world["company"],
            partner_id=journal_world["partner"],
            document_date=ON,
            amount=Decimal("400.00"),
            treasury_account="cash",
            partner_resident=True,
        )
        record_and_post(
            document_id=receipt,
            actor_user_id=journal_world["user"],
            request_id="journal-receipt",
            capability_snapshot=SNAPSHOT,
        )

        sales = document_journal(
            journal_world["company"], owner="sales", date_from=JANUARY[0], date_to=JANUARY[1]
        )
        treasury = document_journal(
            journal_world["company"], owner="treasury", date_from=JANUARY[0], date_to=JANUARY[1]
        )

    assert [row.document_type for row in sales.rows] == ["sales.document"]
    assert [row.document_type for row in treasury.rows] == ["treasury.receipt"]


def test_the_totals_are_the_servers_and_the_vat_column_is_present(
    journal_world: dict[str, Any],
) -> None:
    """`C19`, and the empty VAT column says something rather than being missing."""
    with tenant_context(journal_world["context"]):
        an_invoice(journal_world, amount="1000.00")
        an_invoice(journal_world, amount="250.50")

        report = document_journal(
            journal_world["company"], owner="sales", date_from=JANUARY[0], date_to=JANUARY[1]
        )

    assert report.total_net == Decimal("1250.50")
    assert report.total_amount == Decimal("1250.50")
    assert report.total_vat == Decimal("0")


def test_the_window_excludes_what_is_outside_it(journal_world: dict[str, Any]) -> None:
    """Selected by the accounting date -- the column the trial balance sums."""
    with tenant_context(journal_world["context"]):
        an_invoice(journal_world, amount="700.00", on=ON)

        inside = document_journal(
            journal_world["company"], owner="sales", date_from=JANUARY[0], date_to=JANUARY[1]
        )
        outside = document_journal(
            journal_world["company"],
            owner="sales",
            date_from=date(2026, 2, 1),
            date_to=date(2026, 2, 28),
        )

    assert len(inside.rows) == 1
    assert outside.rows == ()
    assert outside.total_amount == Decimal("0")


def test_the_register_carries_the_legal_name_not_the_internal_one(
    journal_world: dict[str, Any],
) -> None:
    """`C39` and ADR-034, and the fixture is built to catch the other choice.

    The partner has both names and they differ. A register printing the internal
    one is the artefact `OD-40` is open about -- and it would pass every other
    assertion here.
    """
    with tenant_context(journal_world["context"]):
        an_invoice(journal_world, amount="300.00")
        report = document_journal(
            journal_world["company"], owner="sales", date_from=JANUARY[0], date_to=JANUARY[1]
        )
        csv_bytes = document_journal_csv(report)

    assert report.rows[0].partner_name == 'Societatea Comercială "Beta" SRL'
    text = csv_bytes.decode("utf-8-sig")
    # Quoted the way CSV quotes a field containing quotes -- doubled, and the whole
    # field wrapped. Asserted in that form rather than by substring, because the
    # raw name is *not* what a correct writer emits and a test looking for it would
    # be asking the exporter to be wrong.
    assert '"Societatea Comercială ""Beta"" SRL"' in text
    assert "beta (client vechi)" not in text
    # The header a Moldovan spreadsheet reads, in Romanian, from the document layer.
    assert "Data contabilă;Data documentului;Număr;Contraparte" in text
