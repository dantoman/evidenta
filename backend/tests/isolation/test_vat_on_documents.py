"""VAT reaches the ledger -- ADR-089, step 6, first slice.

What is proved, under the application role (`T1`):

1. **A registered company issues with VAT and the ledger carries 5344**, with
   the rate stamped on the VAT formula (ADR-048) and the receivable owing the
   total. The net goes to revenue; the difference is owed to the budget.
2. **VAT is rounded on each line and the document adds the lines** -- the rule
   the owner fixed. Three lines of 33,33 at 20% give 20,01, not the 20,00 a rate
   on the total base would give, and the difference is visible in `totals_of`.
3. **The status on the document's date decides what a line may state** (ADR-088):
   a treatment before the registration is refused, and *no VAT* after it is
   refused too, because for a payer it is not a treatment.
4. **A rate that is not active is a refusal, never zero** (`OD-22`): the reduced
   regime exists in the vocabulary and its parameter is not seeded, so a line
   under it names the missing key instead of pricing at nothing.
5. **The credit note takes the VAT back**: 5344 debited, the receivable credited.
6. **A registered buyer deducts and an unregistered buyer bears the cost** -- the
   same invoice, one day apart across the registration, lands in 2252 or in the
   cost account. The discriminator is on the fact, and the engine holds it against
   the stamp `emit` wrote: a fact that lies about it is refused.
7. **The registration has a door**, over HTTP, guarded by `company.edit`, refusing
   an overlap; the status is dated, and a company of another tenant is absent.
8. **The document journal's VAT column stops being zero**, and agrees with the
   ledger of the collected-VAT account for the month -- the first half of the
   `F2.A6` done criterion.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from django.db.models import Sum
from django.test import Client

from evidenta.accounting.ledger.models import JournalEntry, JournalFormula, JournalLine
from evidenta.accounting.ledger.services.document_journal import document_journal
from evidenta.accounting.posting.services.commercial import (
    ROLE_CHELTUIELI_ADMINISTRATIVE,
    ROLE_CREANTE_TARA,
    ROLE_DATORII_TARA,
    ROLE_RETUR_REDUCERI,
    ROLE_TVA_COLECTATA,
    ROLE_TVA_DEDUCTIBILA,
    ROLE_VENIT_SERVICII,
    PurchaseInvoiceFact,
    PurchaseVatStatusMismatchError,
    VatShare,
    post_purchase_invoice,
)
from evidenta.accounting.slots.models import AccountRoleBinding
from evidenta.operations.purchases.services.documents import open_purchase
from evidenta.operations.purchases.services.lines import Position as PurchasePosition
from evidenta.operations.purchases.services.lines import write_lines as write_purchase_lines
from evidenta.operations.purchases.services.recording import record_and_post
from evidenta.operations.sales.services.documents import open_sale
from evidenta.operations.sales.services.issuing import (
    VatWithoutRegistrationError,
    issue_and_post,
)
from evidenta.operations.sales.services.lines import (
    Position,
    RegisteredCompanyStatesRegimeError,
    VatRegimeRequiresRegistrationError,
    VatRegimeUnknownError,
    VatUnavailableError,
    write_lines,
)
from evidenta.platform.documents.services.lines import totals_of, vat_breakdown
from evidenta.platform.identity.services import roles as role_service
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.isolation.test_coa_api import HOST_A, mfa_key, signed_in  # noqa: F401
from tests.isolation.test_formulas import seed_account
from tests.isolation.test_ledger import seed_period
from tests.isolation.test_line_rounding import SOURCE_ID, direction, scale, source  # noqa: F401
from tests.isolation.test_manual_entry import seed_template as seed_numbering

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

#: Three days, one registration between the first two. Every test that depends
#: on the status names one of these, so the date is the argument, not a clock.
BEFORE = date(2026, 1, 10)
REGISTERED_FROM = date(2026, 1, 15)
ON = date(2026, 1, 20)

SNAPSHOT: dict[str, Any] = {"version": 1, "on": "2026-01-01", "activated": [], "usable": []}

STANDARD = "taxable_standard"
REDUCED = "taxable_reduced"
NO_VAT = "fara_tva"

#: The plan codes, because the assertions read them: 5344 is where collected VAT
#: goes and 2252 where deductible VAT goes, and a posting that balanced through
#: any other pair would pass `R11` and be wrong.
ROLE_ACCOUNT_CODES = {
    ROLE_CREANTE_TARA: "2211",
    ROLE_VENIT_SERVICII: "6111",
    ROLE_RETUR_REDUCERI: "7128",
    ROLE_TVA_COLECTATA: "5344",
    ROLE_DATORII_TARA: "5211",
    ROLE_CHELTUIELI_ADMINISTRATIVE: "7135",
    ROLE_TVA_DEDUCTIBILA: "2252",
}


def vat_vocabulary(seed: Callable[..., None], world: dict[str, uuid.UUID]) -> None:
    """The regime table and the standard rate, active -- and **not** the reduced one.

    A fixture, so the margin is a platform convention with this file as its
    reference: claiming an act for a test value would be the fabrication the
    constraint exists to refuse, from the other side. The reduced rate is left
    unseeded on purpose; one test needs a regime whose rate cannot resolve.
    """

    def row(key: str, value_type: str, value: str) -> None:
        seed(
            "INSERT INTO fiscal_parameter (id, parameter_key, scope, value_type, value,"
            " valid_from, margin_basis, margin_reference, source_id, status,"
            " approved_by_user_id, approved_at, source_confidence, created_at, updated_at)"
            " VALUES (%s, %s, 'global', %s, %s::jsonb, DATE '2020-01-01',"
            " 'platform_convention', 'test_vat_on_documents fixture', %s,"
            " 'active', %s, now(), 'confirmed', now(), now())",
            [uuid.uuid4(), key, value_type, value, SOURCE_ID, world["user_a"]],
        )

    row(
        "vat.regimes",
        "table",
        json.dumps(
            {
                "codes": [STANDARD, REDUCED, "exempt_without_deduction", "exempt_with_deduction"],
                "rates": {STANDARD: "vat.standard", REDUCED: "vat.reduced"},
            }
        ),
    )
    row("vat.standard", "percentage", "20")


def register(
    seed: Callable[..., None],
    tenant: uuid.UUID,
    company: uuid.UUID,
    *,
    valid_from: date,
    valid_to: date | None = None,
) -> None:
    seed(
        "INSERT INTO company_vat_registration (id, tenant_id, company_id, vat_code,"
        " valid_from, valid_to, created_at) VALUES (%s, %s, %s, '0301234', %s, %s, now())",
        [uuid.uuid4(), tenant, company, valid_from, valid_to],
    )


@pytest.fixture
def vat_world(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
    source: uuid.UUID,  # noqa: F811 -- the fiscal act fixture, imported to be found
) -> dict[str, Any]:
    """One company, registered for VAT from the 15th, with both document families
    numbered, the seven bindings, the vocabulary, and one partner on both sides."""
    tenant = world["tenant_a"]
    company = company_of(tenant, "1002600000921", "Alpha TVA")
    grant_company(tenant, company, world["user_a"], world["user_a"])
    seed_period(seed, tenant, company)
    seed_numbering(seed, tenant, company)
    seed_numbering(seed, tenant, company, document_type="sales.document")
    seed_numbering(seed, tenant, company, document_type="purchases.document")
    scale(seed, world, "accounting.amount_scale", 2)
    scale(seed, world, "accounting.unit_price_scale", 4)
    direction(seed, world, "half_up")
    vat_vocabulary(seed, world)
    register(seed, tenant, company, valid_from=REGISTERED_FROM)

    context = TenantContext(tenant_id=tenant, user_id=world["user_a"], request_id="vat")
    accounts = {
        role: seed_account(seed, tenant, company, code) for role, code in ROLE_ACCOUNT_CODES.items()
    }
    partner_id = uuid.uuid4()
    seed(
        "INSERT INTO partner (id, tenant_id, kind, legal_name, is_customer, is_supplier,"
        " is_active, created_at, updated_at)"
        " VALUES (%s, %s, 'legal_entity', 'Partener SRL', true, true, true, now(), now())",
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
        # The permissions of the system roles, as the product installs them --
        # `company.edit` is what the registration endpoint asks for.
        role_service.create_system_roles(tenant)
    return {
        "tenant": tenant,
        "company": company,
        "user": world["user_a"],
        "partner": partner_id,
        "context": context,
        "accounts": accounts,
        "codes": {account: ROLE_ACCOUNT_CODES[role] for role, account in accounts.items()},
    }


# --- helpers -----------------------------------------------------------------


def a_sale(
    world: dict[str, Any],
    *,
    on: date = ON,
    regime: str = STANDARD,
    prices: tuple[str, ...] = ("1000.00",),
    nature: str = "delivery",
) -> uuid.UUID:
    document_id = open_sale(
        company_id=world["company"],
        partner_id=world["partner"],
        document_date=on,
        revenue_kind="services",
        partner_resident=True,
        nature=nature,
    )
    write_lines(
        document_id,
        [
            Position(
                description="Servicii de contabilitate",
                quantity=Decimal("1"),
                unit_price=Decimal(price),
                vat_regime_code=regime,
            )
            for price in prices
        ],
    )
    return document_id


def a_purchase(
    world: dict[str, Any], *, on: date = ON, regime: str = STANDARD, reference: str
) -> uuid.UUID:
    document_id = open_purchase(
        company_id=world["company"],
        partner_id=world["partner"],
        document_date=on,
        supplier_document_number=reference,
        supplier_document_date=on,
        cost_destination="administrative",
        partner_resident=True,
    )
    write_purchase_lines(
        document_id,
        [
            PurchasePosition(
                description="Chirie",
                quantity=Decimal("1"),
                unit_price=Decimal("1000.00"),
                vat_regime_code=regime,
            )
        ],
    )
    return document_id


def issue(world: dict[str, Any], document_id: uuid.UUID) -> uuid.UUID:
    result = issue_and_post(
        document_id=document_id,
        actor_user_id=world["user"],
        request_id="vat",
        capability_snapshot=SNAPSHOT,
    )
    assert result.journal_entry_id is not None
    return result.journal_entry_id


def record(world: dict[str, Any], document_id: uuid.UUID) -> uuid.UUID:
    result = record_and_post(
        document_id=document_id,
        actor_user_id=world["user"],
        request_id="vat",
        capability_snapshot=SNAPSHOT,
    )
    assert result.journal_entry_id is not None
    return result.journal_entry_id


Formula = tuple[str, str, Decimal, Decimal | None, str | None]


def formulas_of(world: dict[str, Any], journal_entry_id: uuid.UUID) -> list[Formula]:
    """(debit code, credit code, amount, VAT rate, VAT rate key), in formula order."""
    codes = world["codes"]
    return [
        (
            codes[row.debit_account_id],
            codes[row.credit_account_id],
            row.amount,
            row.vat_rate,
            row.vat_rate_key,
        )
        for row in JournalFormula.objects.filter(journal_entry_id=journal_entry_id).order_by(
            "formula_number"
        )
    ]


# --- 1. the sale with VAT ------------------------------------------------------


def test_a_registered_company_issues_with_vat_and_5344_carries_the_rate(
    vat_world: dict[str, Any],
) -> None:
    with tenant_context(vat_world["context"]):
        document_id = a_sale(vat_world)
        totals = totals_of(document_id)
        entry_id = issue(vat_world, document_id)
        formulas = formulas_of(vat_world, entry_id)
        lines = list(JournalLine.objects.filter(journal_entry_id=entry_id))
        entry = JournalEntry.objects.get(id=entry_id)

    assert (totals.net, totals.vat, totals.total) == (
        Decimal("1000.00"),
        Decimal("200.00"),
        Decimal("1200.00"),
    )
    # Net to revenue, VAT to 5344 with its rate and the key it was resolved under
    # (ADR-048, `R18`); the receivable is debited by both.
    assert formulas == [
        ("2211", "6111", Decimal("1000.00"), None, None),
        ("2211", "5344", Decimal("200.00"), Decimal("20"), "vat.standard"),
    ]
    assert sum(line.debit for line in lines) == Decimal("1200.00")
    assert sum(line.credit for line in lines) == Decimal("1200.00")
    assert entry.status == "posted"


def test_vat_is_rounded_on_each_line_and_the_document_adds_the_lines(
    vat_world: dict[str, Any],
) -> None:
    """Three lines of 33,33 at 20%: each 6,666 rounds to 6,67, the document says
    20,01. On the total base it would say 20,00 (99,99 at 20% = 19,998), and the
    one ban of difference is exactly the class of complaint ADR-037 §3.1 names."""
    with tenant_context(vat_world["context"]):
        document_id = a_sale(vat_world, prices=("33.33", "33.33", "33.33"))
        totals = totals_of(document_id)
        breakdown = vat_breakdown(document_id)

    assert totals.net == Decimal("99.99")
    assert totals.vat == Decimal("20.01")
    assert totals.total == Decimal("120.00")
    # One slice: same regime, same key, same rate, summed.
    assert len(breakdown) == 1
    assert breakdown[0].vat_rate_key == "vat.standard"
    assert breakdown[0].vat == Decimal("20.01")


# --- 3. the status on the document's date ----------------------------------------


def test_a_company_not_yet_registered_on_the_document_date_may_not_state_a_regime(
    vat_world: dict[str, Any],
) -> None:
    with tenant_context(vat_world["context"]), pytest.raises(VatRegimeRequiresRegistrationError):
        a_sale(vat_world, on=BEFORE, regime=STANDARD)


def test_a_registered_company_states_a_regime_and_not_a_status(
    vat_world: dict[str, Any],
) -> None:
    """`fara_tva` is "the issuer is not a payer", and on the 20th that is false."""
    with tenant_context(vat_world["context"]), pytest.raises(RegisteredCompanyStatesRegimeError):
        a_sale(vat_world, on=ON, regime=NO_VAT)


def test_before_the_registration_the_company_issues_without_vat_as_before(
    vat_world: dict[str, Any],
) -> None:
    """The step-5 document is still the step-5 document: same two formulas."""
    with tenant_context(vat_world["context"]):
        document_id = a_sale(vat_world, on=BEFORE, regime=NO_VAT)
        entry_id = issue(vat_world, document_id)
        formulas = formulas_of(vat_world, entry_id)

    assert formulas == [("2211", "6111", Decimal("1000.00"), None, None)]


def test_issuance_refuses_vat_when_the_registration_no_longer_covers_the_date(
    vat_world: dict[str, Any], seed: Callable[..., None]
) -> None:
    """The lines were admissible when typed; the registration was then corrected
    to end before the document's date. The legal document is checked at the moment
    it becomes one, not only at entry."""
    with tenant_context(vat_world["context"]):
        document_id = a_sale(vat_world, on=ON)
    seed(
        "UPDATE company_vat_registration SET valid_to = %s WHERE company_id = %s",
        [date(2026, 1, 18), vat_world["company"]],
    )
    with tenant_context(vat_world["context"]), pytest.raises(VatWithoutRegistrationError):
        issue(vat_world, document_id)


# --- 4. a missing rate, an unknown regime ---------------------------------------


def test_a_rate_that_is_not_active_is_a_refusal_that_names_the_key(
    vat_world: dict[str, Any],
) -> None:
    with tenant_context(vat_world["context"]), pytest.raises(VatUnavailableError) as refused:
        a_sale(vat_world, regime=REDUCED)

    assert refused.value.context["fiscal_code"] == "fiscal.no_parameter"
    assert "vat.reduced" in str(refused.value)


def test_a_regime_the_nomenclature_does_not_list_is_refused(vat_world: dict[str, Any]) -> None:
    with tenant_context(vat_world["context"]), pytest.raises(VatRegimeUnknownError):
        a_sale(vat_world, regime="taxable_horeca")


# --- 5. the credit note ----------------------------------------------------------


def test_the_credit_note_takes_the_vat_back(vat_world: dict[str, Any]) -> None:
    with tenant_context(vat_world["context"]):
        document_id = a_sale(vat_world, prices=("500.00",), nature="return")
        entry_id = issue(vat_world, document_id)
        formulas = formulas_of(vat_world, entry_id)

    # 7128 for the net, and 5344 **debited** for the VAT: the obligation to the
    # budget comes down by what was charged on the delivery that came back.
    assert formulas == [
        ("7128", "2211", Decimal("500.00"), None, None),
        ("5344", "2211", Decimal("100.00"), Decimal("20"), "vat.standard"),
    ]


# --- 6. the purchase: deductible or borne ------------------------------------------


def test_a_registered_buyer_deducts_and_an_unregistered_buyer_bears_the_vat_as_cost(
    vat_world: dict[str, Any],
) -> None:
    """The same supplier invoice, dated the 10th and the 20th. Registered on the
    20th: cost 1 000, 2252 for 200. Not registered on the 10th: cost 1 200, and
    no VAT formula at all -- the VAT is what the service cost."""
    with tenant_context(vat_world["context"]):
        registered = a_purchase(vat_world, on=ON, reference="AA 0002")
        not_registered = a_purchase(vat_world, on=BEFORE, reference="AA 0001")
        deducted = formulas_of(vat_world, record(vat_world, registered))
        borne = formulas_of(vat_world, record(vat_world, not_registered))

    assert deducted == [
        ("7135", "5211", Decimal("1000.00"), None, None),
        ("2252", "5211", Decimal("200.00"), Decimal("20"), "vat.standard"),
    ]
    assert borne == [("7135", "5211", Decimal("1200.00"), None, None)]


def test_a_fact_that_contradicts_the_stamp_is_refused(vat_world: dict[str, Any]) -> None:
    """The purchases module derives `vat_deductible` from the status; `emit` stamps
    the same status. A fact claiming deduction on a day the company was not
    registered is one of the two readings being wrong, and neither posts."""
    fact = PurchaseInvoiceFact(
        document_id=uuid.uuid4(),
        partner_id=vat_world["partner"],
        accounting_date=BEFORE,
        document_date=BEFORE,
        total=Decimal("1200.00"),
        net=Decimal("1000.00"),
        vat=Decimal("200.00"),
        vat_by_rate=(
            VatShare(
                rate_key="vat.standard",
                rate=Decimal("20"),
                net=Decimal("1000.00"),
                vat=Decimal("200.00"),
            ),
        ),
        vat_deductible=True,
        currency="MDL",
        cost_destination="administrative",
        partner_resident=True,
        description="Factură primită AA 0009",
    )
    with tenant_context(vat_world["context"]), pytest.raises(PurchaseVatStatusMismatchError):
        post_purchase_invoice(
            tenant_id=vat_world["tenant"],
            company_id=vat_world["company"],
            functional_currency="MDL",
            fact=fact,
            actor_user_id=vat_world["user"],
            request_id="vat",
            capability_snapshot=SNAPSHOT,
        )


# --- 7. the registration has a door ------------------------------------------------


def _get(client: Client, path: str, expect: int = 200) -> Any:
    response = client.get(path, headers={"host": HOST_A})
    assert response.status_code == expect, response.content
    return response.json()


def _post(client: Client, path: str, body: dict[str, Any], expect: int) -> Any:
    return _send(client, "post", path, body, expect)


def _send(client: Client, method: str, path: str, body: dict[str, Any], expect: int) -> Any:
    response = getattr(client, method)(
        path, data=json.dumps(body), content_type="application/json", headers={"host": HOST_A}
    )
    assert response.status_code == expect, response.content
    return response.json()


def test_the_registration_is_recorded_over_http_and_the_status_is_dated(
    vat_world: dict[str, Any],
    signed_in: Client,  # noqa: F811 -- fixture, imported to be found
    company_of: Callable[..., uuid.UUID],
    world: dict[str, uuid.UUID],
) -> None:
    company = vat_world["company"]
    base = f"/api/v1/companies/{company}"

    # An earlier, closed registration -- entered because it is history, not a toggle.
    created = _post(
        signed_in,
        f"{base}/vat-registrations",
        {
            "vat_code": "0300001",
            "valid_from": "2026-01-01",
            "valid_to": "2026-01-10",
            "source": "certificat nr. 1",
        },
        201,
    )
    assert created["vat_code"] == "0300001"
    assert created["valid_to"] == "2026-01-10"

    # Overlapping the fixture's open registration from the 15th: refused, with its code.
    refused = _post(
        signed_in,
        f"{base}/vat-registrations",
        {"vat_code": "0300002", "valid_from": "2026-01-20"},
        409,
    )
    assert refused["code"] == "tenancy.vat_registration_overlap"

    listed = _get(signed_in, f"{base}/vat-registrations")
    assert [row["valid_from"] for row in listed] == ["2026-01-01", "2026-01-15"]

    # The status is the one in force on the day asked about, and the day is required.
    assert _get(signed_in, f"{base}/tax-status?on=2026-01-05")["vat"]["registered"] is True
    assert _get(signed_in, f"{base}/tax-status?on=2026-01-12")["vat"] == {"registered": False}
    on_the_20th = _get(signed_in, f"{base}/tax-status?on=2026-01-20")["vat"]
    assert on_the_20th["registered"] is True and on_the_20th["code"] == "0301234"
    assert _get(signed_in, f"{base}/tax-status", expect=400)["code"] == "tenancy.date_required"

    # A company of the other tenant is absent, never forbidden (IZ-04).
    other = company_of(world["tenant_b"], "1002600000922", "Beta TVA")
    _get(signed_in, f"/api/v1/companies/{other}/tax-status?on=2026-01-20", expect=404)
    _get(signed_in, f"/api/v1/companies/{other}/vat-registrations", expect=404)


def test_the_regime_vocabulary_is_served_with_what_each_rate_resolves_to(
    vat_world: dict[str, Any],
    signed_in: Client,  # noqa: F811
) -> None:
    body = _get(signed_in, "/api/v1/fiscal/vat/regimes?on=2026-01-20")
    by_code = {row["code"]: row for row in body["regimes"]}

    assert set(by_code) == {STANDARD, REDUCED, "exempt_without_deduction", "exempt_with_deduction"}
    assert by_code[STANDARD] == {
        "code": STANDARD,
        "rate_key": "vat.standard",
        "rate": "20",
        "unavailable": None,
    }
    # The reduced rate is not active: the row says so and says why, instead of
    # vanishing or reading as zero.
    assert by_code[REDUCED]["rate"] is None
    assert by_code[REDUCED]["unavailable"] == "fiscal.no_parameter"
    assert by_code["exempt_with_deduction"]["rate"] == "0"
    assert (
        _get(signed_in, "/api/v1/fiscal/vat/regimes", expect=400)["code"] == "fiscal.date_required"
    )


def test_an_invoice_with_vat_over_http_carries_the_vat_in_its_totals(
    vat_world: dict[str, Any],
    signed_in: Client,  # noqa: F811
) -> None:
    company = vat_world["company"]
    created = _post(
        signed_in,
        f"/api/v1/sales/companies/{company}/invoices",
        {
            "partner_id": str(vat_world["partner"]),
            "document_date": "2026-01-20",
            "nature": "delivery",
            "revenue_kind": "services",
            "partner_resident": True,
            "lines": [
                {
                    "description": "Servicii",
                    "quantity": "2",
                    "unit_price": "250.00",
                    "vat_regime_code": STANDARD,
                }
            ],
        },
        201,
    )
    # Compared as numbers: the server's strings carry the stored scale.
    assert {key: Decimal(value) for key, value in created["totals"].items()} == {
        "net": Decimal("500.00"),
        "vat": Decimal("100.00"),
        "total": Decimal("600.00"),
    }

    # And the register row says the same -- the list is one grouped query.
    rows = _get(signed_in, f"/api/v1/sales/companies/{company}/invoices")
    listed = {row["id"]: row["totals"] for row in rows}[created["id"]]
    assert {key: Decimal(value) for key, value in listed.items()} == {
        key: Decimal(value) for key, value in created["totals"].items()
    }

    # A line without a regime is refused by shape, before any rule runs.
    _send(
        signed_in,
        "put",
        f"/api/v1/sales/invoices/{created['id']}/lines",
        {"lines": [{"description": "Servicii", "quantity": "1", "unit_price": "1.00"}]},
        400,
    )


# --- 8. the journal agrees with the ledger --------------------------------------------


def test_the_document_journal_vat_column_agrees_with_the_collected_vat_account(
    vat_world: dict[str, Any],
) -> None:
    with tenant_context(vat_world["context"]):
        issue(vat_world, a_sale(vat_world, prices=("1000.00",)))
        issue(vat_world, a_sale(vat_world, prices=("33.33", "33.33", "33.33")))
        journal = document_journal(vat_world["company"], owner="sales", date_from=ON, date_to=ON)
        collected = JournalLine.objects.filter(
            company_id=vat_world["company"],
            account_id=vat_world["accounts"][ROLE_TVA_COLECTATA],
        ).aggregate(credit=Sum("credit"), debit=Sum("debit"))

    assert journal.total_net == Decimal("1099.99")
    assert journal.total_vat == Decimal("220.01")
    assert journal.total_amount == Decimal("1320.00")
    assert Decimal(collected["credit"]) - Decimal(collected["debit"] or 0) == journal.total_vat
