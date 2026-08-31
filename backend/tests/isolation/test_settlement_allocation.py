"""Which invoice the money answered -- ADR-087, `F2.A3`.

The assertion that matters most is a **negative** one: an allocation in the
functional currency moves no balance. The receipt already debited the treasury
and credited the receivable when it was posted; saying which invoice it answered
adds an answer, not an entry. If that ever stops being true, the ledger has grown
a second route and this test is where it shows.

The rest are the ceilings and the discriminator: an allocation may not exceed what
is left on either side, and residence reaches the accounting fact **from the
settled document** rather than from the movement or from a default.

Under the application role (`T1`).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from evidenta.accounting.events.models import AccountingEvent
from evidenta.accounting.ledger.models import JournalEntry, JournalLine
from evidenta.accounting.posting.services.commercial import (
    ROLE_CASA_MDL,
    ROLE_CREANTE_STRAINATATE,
    ROLE_CREANTE_TARA,
    ROLE_VENIT_SERVICII,
)
from evidenta.accounting.slots.models import AccountRoleBinding
from evidenta.operations.sales.services.documents import open_sale
from evidenta.operations.sales.services.issuing import issue_and_post
from evidenta.operations.settlements.models import Settlement
from evidenta.operations.settlements.services.allocation import (
    NotSettleableError,
    OverAllocatedError,
    allocate,
    outstanding,
)
from evidenta.operations.treasury.services.documents import open_receipt
from evidenta.operations.treasury.services.recording import record_and_post
from evidenta.platform.audit.models import AuditEvent
from evidenta.platform.documents.services.lines import LineInput, replace_lines
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.isolation.test_formulas import seed_account
from tests.isolation.test_ledger import seed_period
from tests.isolation.test_line_rounding import direction, scale, source  # noqa: F401
from tests.isolation.test_manual_entry import seed_template as seed_numbering

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

ON = date(2026, 1, 20)
SNAPSHOT: dict[str, Any] = {"version": 1, "on": "2026-01-01", "activated": [], "usable": []}

ROLE_ACCOUNT_CODES = {
    ROLE_CREANTE_TARA: "2211",
    ROLE_CREANTE_STRAINATATE: "2212",
    ROLE_VENIT_SERVICII: "6111",
    ROLE_CASA_MDL: "2411",
}


@pytest.fixture
def matched_world(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
    source: uuid.UUID,  # noqa: F811 -- the fiscal act fixture, imported to be found
) -> dict[str, Any]:
    """A company that can both issue an invoice and receive money against it."""
    tenant = world["tenant_a"]
    company = company_of(tenant, "1002600000916", "Alpha Decontări")
    grant_company(tenant, company, world["user_a"], world["user_a"])
    seed_period(seed, tenant, company)
    seed_numbering(seed, tenant, company)
    for document_type in ("sales.document", "treasury.receipt"):
        seed_numbering(seed, tenant, company, document_type=document_type)
    scale(seed, world, "accounting.amount_scale", 2)
    direction(seed, world, "half_up")

    context = TenantContext(tenant_id=tenant, user_id=world["user_a"], request_id="settlement")
    accounts = {
        role: seed_account(seed, tenant, company, code) for role, code in ROLE_ACCOUNT_CODES.items()
    }
    partner_id = uuid.uuid4()
    seed(
        "INSERT INTO partner (id, tenant_id, kind, legal_name, is_customer, is_supplier,"
        " is_active, created_at, updated_at)"
        " VALUES (%s, %s, 'legal_entity', 'Client SRL', true, false, true, now(), now())",
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
        "accounts": accounts,
    }


def an_invoice(
    world: dict[str, Any], *, amount: str = "5000.00", resident: bool = True
) -> uuid.UUID:
    document_id = open_sale(
        company_id=world["company"],
        partner_id=world["partner"],
        document_date=ON,
        revenue_kind="services",
        partner_resident=resident,
    )
    replace_lines(
        document_id,
        [
            LineInput(
                description="Servicii de contabilitate",
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
        request_id="invoice",
        capability_snapshot=SNAPSHOT,
    )
    return document_id


def a_receipt(
    world: dict[str, Any], *, amount: str = "5000.00", resident: bool = True
) -> uuid.UUID:
    document_id = open_receipt(
        company_id=world["company"],
        partner_id=world["partner"],
        document_date=ON,
        amount=Decimal(amount),
        treasury_account="cash",
        partner_resident=resident,
    )
    record_and_post(
        document_id=document_id,
        actor_user_id=world["user"],
        request_id="receipt",
        capability_snapshot=SNAPSHOT,
    )
    return document_id


def _balance() -> tuple[Decimal, Decimal, int]:
    lines = list(JournalLine.objects.all())
    return (
        sum((line.debit for line in lines), Decimal(0)),
        sum((line.credit for line in lines), Decimal(0)),
        JournalEntry.objects.count(),
    )


def _allocate(world: dict[str, Any], invoice: uuid.UUID, receipt: uuid.UUID, amount: str) -> Any:
    del world
    return allocate(
        settled_document_id=invoice,
        movement_document_id=receipt,
        amount=Decimal(amount),
    )


def test_an_allocation_moves_no_balance(matched_world: dict[str, Any]) -> None:
    """The property the whole design rests on -- ADR-087 §2.

    Both figures and the entry count, before and after. Two equal sums would also
    be equal if everything were zero, so the count is what says the world was not
    empty to begin with.
    """
    with tenant_context(matched_world["context"]):
        invoice = an_invoice(matched_world)
        receipt = a_receipt(matched_world)
        before = _balance()

        result = _allocate(matched_world, invoice, receipt, "5000.00")

        after = _balance()
        settlements = Settlement.objects.count()

    assert before == after
    assert before[2] == 2, "an invoice and a receipt were posted before the allocation"
    assert settlements == 1
    assert result.outstanding_after == Decimal("0.00")


def test_the_outstanding_drops_by_exactly_the_amount(matched_world: dict[str, Any]) -> None:
    with tenant_context(matched_world["context"]):
        invoice = an_invoice(matched_world, amount="5000.00")
        receipt = a_receipt(matched_world, amount="2000.00")

        assert outstanding(invoice) == Decimal("5000.00")
        result = _allocate(matched_world, invoice, receipt, "2000.00")

        assert result.outstanding_after == Decimal("3000.00")
        assert outstanding(invoice) == Decimal("3000.00")


def test_more_than_is_left_on_the_document_is_refused(matched_world: dict[str, Any]) -> None:
    with tenant_context(matched_world["context"]):
        invoice = an_invoice(matched_world, amount="1000.00")
        first = a_receipt(matched_world, amount="1000.00")
        second = a_receipt(matched_world, amount="1000.00")

        _allocate(matched_world, invoice, first, "1000.00")
        with pytest.raises(OverAllocatedError):
            _allocate(matched_world, invoice, second, "1000.00")


def test_more_than_the_movement_holds_is_refused(matched_world: dict[str, Any]) -> None:
    """The second ceiling, and it is not the same one.

    A receipt of 500 cannot answer 800 of an invoice that is open for 5000: the
    document has room, the money does not.
    """
    with tenant_context(matched_world["context"]):
        invoice = an_invoice(matched_world, amount="5000.00")
        receipt = a_receipt(matched_world, amount="500.00")

        with pytest.raises(OverAllocatedError):
            _allocate(matched_world, invoice, receipt, "800.00")


def test_a_receipt_does_not_settle_what_it_is_not(matched_world: dict[str, Any]) -> None:
    """A receipt clears a receivable. Pointed at a receipt, it refuses."""
    with tenant_context(matched_world["context"]):
        receipt = a_receipt(matched_world, amount="100.00")
        other = a_receipt(matched_world, amount="100.00")

        with pytest.raises(NotSettleableError):
            _allocate(matched_world, receipt, other, "100.00")


def test_residence_is_recorded_from_the_settled_document(
    matched_world: dict[str, Any],
) -> None:
    """ADR-073 §2 through ADR-087 §4, and the trap is deliberate.

    The invoice says the customer is **not** a resident; the receipt says they
    are. One of the two has to win, and it must be the invoice -- that is where
    the receivable was recognised, and where somebody was asked. A settlement that
    took the movement's word would compute the difference against the wrong
    account the day currencies arrive.

    Read from the audit trail rather than from an accounting event, because in the
    functional currency there is no event: the discriminator is kept where the act
    of matching is kept.
    """
    with tenant_context(matched_world["context"]):
        invoice = an_invoice(matched_world, amount="400.00", resident=False)
        receipt = a_receipt(matched_world, amount="400.00", resident=True)

        result = _allocate(matched_world, invoice, receipt, "400.00")
        entry = AuditEvent.objects.get(entity_id=result.settlement_id)

    assert entry.action == "settlement.allocated"
    recorded = entry.new_value
    assert recorded is not None
    assert recorded["partner_resident"] is False


def test_nothing_is_emitted_where_no_difference_can_arise(
    matched_world: dict[str, Any],
) -> None:
    """The other half of ADR-087 §2, and the engine is what taught it.

    `contract_denomination` has exactly two values -- the two notions the standard
    names -- and neither of them means "the contract is in lei". An allocation
    that emitted the event anyway would have to invent a third.
    """
    with tenant_context(matched_world["context"]):
        before = AccountingEvent.objects.count()
        invoice = an_invoice(matched_world, amount="300.00")
        receipt = a_receipt(matched_world, amount="300.00")
        after_documents = AccountingEvent.objects.count()

        _allocate(matched_world, invoice, receipt, "300.00")
        after_allocation = AccountingEvent.objects.count()

    # Two events for the two documents, and not a third for the match.
    assert after_documents == before + 2
    assert after_allocation == after_documents
