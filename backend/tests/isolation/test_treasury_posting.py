"""Money reaches the ledger through the engine -- ADR-073 §5, step 5.

Four assertions matter here, and three of them are about what the posting does
**not** know:

1. The treasury account follows the **instrument** -- cash or bank -- not the
   document. The same receipt from the same customer lands in the till or in the
   bank account depending on where it was handed over, and nothing on the invoice
   knows which.
2. The counterparty account follows residence, as everywhere else.
3. **Which invoice the money settles is not asked and not recorded.** That is the
   ADR's decision, not an omission: settlement is its own step, and a half-written
   link is one reports would start reading.
4. Idempotent on the event (`R19`).

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
    ROLE_CONT_CURENT_MDL,
    ROLE_CREANTE_STRAINATATE,
    ROLE_CREANTE_TARA,
    ROLE_DATORII_TARA,
)
from evidenta.accounting.slots.models import AccountRoleBinding
from evidenta.operations.treasury.services.documents import (
    TreasuryAccountInvalidError,
    TreasuryAmountInvalidError,
    open_payment,
    open_receipt,
)
from evidenta.operations.treasury.services.recording import record_and_post
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.isolation.test_formulas import seed_account
from tests.isolation.test_ledger import seed_period
from tests.isolation.test_line_rounding import direction, scale, source  # noqa: F401
from tests.isolation.test_manual_entry import seed_template as seed_numbering

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

ON = date(2026, 1, 22)

SNAPSHOT: dict[str, Any] = {"version": 1, "on": "2026-01-01", "activated": [], "usable": []}

#: 2411 against 2421 is what separates the till from the bank account, and that
#: separation is the point of the first test.
ROLE_ACCOUNT_CODES = {
    ROLE_CASA_MDL: "2411",
    ROLE_CONT_CURENT_MDL: "2421",
    ROLE_CREANTE_TARA: "2211",
    ROLE_CREANTE_STRAINATATE: "2212",
    ROLE_DATORII_TARA: "5211",
}


@pytest.fixture
def treasury_world(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
    source: uuid.UUID,  # noqa: F811 -- the fiscal act fixture, imported to be found
) -> dict[str, Any]:
    tenant = world["tenant_a"]
    company = company_of(tenant, "1002600000915", "Alpha Trezorerie")
    grant_company(tenant, company, world["user_a"], world["user_a"])
    seed_period(seed, tenant, company)
    seed_numbering(seed, tenant, company)
    for document_type in ("treasury.receipt", "treasury.payment"):
        seed_numbering(seed, tenant, company, document_type=document_type)
    scale(seed, world, "accounting.amount_scale", 2)
    direction(seed, world, "half_up")

    context = TenantContext(tenant_id=tenant, user_id=world["user_a"], request_id="treasury")
    accounts = {
        role: seed_account(seed, tenant, company, code) for role, code in ROLE_ACCOUNT_CODES.items()
    }
    partner_id = uuid.uuid4()
    seed(
        "INSERT INTO partner (id, tenant_id, kind, legal_name, is_customer, is_supplier,"
        " is_active, created_at, updated_at)"
        " VALUES (%s, %s, 'legal_entity', 'Client SRL', true, true, true, now(), now())",
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


def _post(world: dict[str, Any], document_id: uuid.UUID, request_id: str) -> Any:
    return record_and_post(
        document_id=document_id,
        actor_user_id=world["user"],
        request_id=request_id,
        capability_snapshot=SNAPSHOT,
    )


def _sides(entry_id: uuid.UUID) -> dict[str, uuid.UUID]:
    lines = list(JournalLine.objects.filter(journal_entry_id=entry_id))
    assert len(lines) == 2
    return {
        "debit": next(line for line in lines if line.debit > 0).account_id,
        "credit": next(line for line in lines if line.credit > 0).account_id,
    }


def test_the_treasury_account_follows_the_instrument(treasury_world: dict[str, Any]) -> None:
    """Cash or bank -- ADR-073 §5, and a default would have put both in one place.

    Two receipts from the same customer for the same amount; only where the money
    landed differs, and nothing on an invoice could have said which.
    """
    with tenant_context(treasury_world["context"]):
        in_cash = _post(
            treasury_world,
            open_receipt(
                company_id=treasury_world["company"],
                partner_id=treasury_world["partner"],
                document_date=ON,
                amount=Decimal("1500.00"),
                treasury_account="cash",
                partner_resident=True,
            ),
            "receipt-cash",
        )
        in_bank = _post(
            treasury_world,
            open_receipt(
                company_id=treasury_world["company"],
                partner_id=treasury_world["partner"],
                document_date=ON,
                amount=Decimal("1500.00"),
                treasury_account="bank",
                partner_resident=True,
            ),
            "receipt-bank",
        )
        assert in_cash.journal_entry_id is not None
        assert in_bank.journal_entry_id is not None
        sides = (_sides(in_cash.journal_entry_id), _sides(in_bank.journal_entry_id))

    accounts = treasury_world["accounts"]
    assert sides[0]["debit"] == accounts[ROLE_CASA_MDL]
    assert sides[1]["debit"] == accounts[ROLE_CONT_CURENT_MDL]
    # The receivable did not move with it: one discriminator, one account.
    assert sides[0]["credit"] == sides[1]["credit"] == accounts[ROLE_CREANTE_TARA]


def test_the_receivable_follows_residence(treasury_world: dict[str, Any]) -> None:
    with tenant_context(treasury_world["context"]):
        foreign = _post(
            treasury_world,
            open_receipt(
                company_id=treasury_world["company"],
                partner_id=treasury_world["partner"],
                document_date=ON,
                amount=Decimal("900.00"),
                treasury_account="bank",
                partner_resident=False,
            ),
            "receipt-foreign",
        )
        assert foreign.journal_entry_id is not None
        sides = _sides(foreign.journal_entry_id)

    assert sides["credit"] == treasury_world["accounts"][ROLE_CREANTE_STRAINATATE]


def test_a_payment_is_the_mirror(treasury_world: dict[str, Any]) -> None:
    """Debit the payable, credit the treasury -- the same fact, the other way."""
    with tenant_context(treasury_world["context"]):
        paid = _post(
            treasury_world,
            open_payment(
                company_id=treasury_world["company"],
                partner_id=treasury_world["partner"],
                document_date=ON,
                amount=Decimal("2000.00"),
                treasury_account="bank",
                partner_resident=True,
            ),
            "payment-1",
        )
        assert paid.journal_entry_id is not None
        sides = _sides(paid.journal_entry_id)
        entry = JournalEntry.objects.get(id=paid.journal_entry_id)
        lines = list(JournalLine.objects.filter(journal_entry_id=entry.id))

    accounts = treasury_world["accounts"]
    assert sides["debit"] == accounts[ROLE_DATORII_TARA]
    assert sides["credit"] == accounts[ROLE_CONT_CURENT_MDL]
    assert sum(line.debit for line in lines) == Decimal("2000.00")


def test_the_movement_records_no_invoice(treasury_world: dict[str, Any]) -> None:
    """ADR-073 §5, asserted where somebody would be tempted to add it.

    The payload the ledger keeps carries the counterparty and the amount, and says
    nothing about which receivable it answers. If a column for that ever appears,
    this fails and sends the reader to the decision rather than to the diff.
    """
    with tenant_context(treasury_world["context"]):
        posted = _post(
            treasury_world,
            open_receipt(
                company_id=treasury_world["company"],
                partner_id=treasury_world["partner"],
                document_date=ON,
                amount=Decimal("100.00"),
                treasury_account="cash",
                partner_resident=True,
            ),
            "receipt-plain",
        )
        payload = AccountingEvent.objects.get(id=posted.accounting_event_id).payload

    assert set(payload) == {
        "document_id",
        "partner_id",
        "amount",
        "currency",
        "treasury_account",
        "partner_resident",
        "document_date",
    }


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"treasury_account": "seif"}, TreasuryAccountInvalidError),
        ({"amount": Decimal("0")}, TreasuryAmountInvalidError),
        ({"amount": Decimal("-50.00")}, TreasuryAmountInvalidError),
    ],
)
def test_the_movement_refuses_what_it_cannot_mean(
    treasury_world: dict[str, Any], kwargs: dict[str, Any], expected: type[Exception]
) -> None:
    """A third account, and a negative receipt: neither is a movement.

    The negative one matters most. Allowed, it would make a payment expressible as
    a receipt with a minus, and then every report would have to know which of the
    two conventions it was reading.
    """
    base: dict[str, Any] = {
        "company_id": treasury_world["company"],
        "partner_id": treasury_world["partner"],
        "document_date": ON,
        "amount": Decimal("10.00"),
        "treasury_account": "cash",
        "partner_resident": True,
    }
    with tenant_context(treasury_world["context"]), pytest.raises(expected):
        open_receipt(**{**base, **kwargs})


def test_recording_twice_posts_once(treasury_world: dict[str, Any]) -> None:
    """`R19`, on the event and not on the endpoint."""
    with tenant_context(treasury_world["context"]):
        document_id = open_receipt(
            company_id=treasury_world["company"],
            partner_id=treasury_world["partner"],
            document_date=ON,
            amount=Decimal("777.00"),
            treasury_account="cash",
            partner_resident=True,
        )
        first = _post(treasury_world, document_id, "twice-1")
        second = _post(treasury_world, document_id, "twice-2")
        entries = JournalEntry.objects.filter(company_id=treasury_world["company"]).count()

    assert first.posted_now is True
    assert second.posted_now is False
    assert second.accounting_event_id == first.accounting_event_id
    assert entries == 1
