"""A sale reaches the ledger through the engine -- ADR-073, `F2.A1`.

Under the application role, like everything in this suite (`T1`).

What is proved:

1. **One route.** The invoice becomes an accounting event and an entry through the
   Posting Engine, exactly like a manual note. The `R13` chain walks back from the
   journal line to the document.
2. **The discriminators are refused, not assumed.** A sale of goods is refused
   because the stock half needs inventory; a residence that is not a boolean is
   refused because the receivable account differs.
3. **The receivable follows residence**, which is the assertion a default would
   have made pass while posting to the wrong account.
4. **Idempotent on the event** (`R19`): issuing twice posts once.
5. **The roles resolve at all** -- which they did not before, because
   `install_default_bindings` had no caller outside the tests (ADR-073 §10).
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
    ROLE_CREANTE_STRAINATATE,
    ROLE_CREANTE_TARA,
    ROLE_RETUR_REDUCERI,
    ROLE_VENIT_SERVICII,
    CostSideRequiresInventoryError,
    SalesDiscriminatorMissingError,
)
from evidenta.accounting.slots.models import AccountRoleBinding
from evidenta.operations.sales.services.documents import SaleMalformedError, open_sale
from evidenta.operations.sales.services.issuing import issue_and_post
from evidenta.platform.documents.services.lines import LineInput, replace_lines
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.isolation.test_formulas import seed_account
from tests.isolation.test_ledger import seed_period
from tests.isolation.test_line_rounding import direction, scale, source  # noqa: F401
from tests.isolation.test_manual_entry import seed_template as seed_numbering

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

ON = date(2026, 1, 20)

#: The profile the engine reads. Explicit and versioned: `R26` makes it an input,
#: and a snapshot with no version records nothing about what the company had.
SNAPSHOT: dict[str, Any] = {"version": 1, "on": "2026-01-01", "activated": [], "usable": []}

#: One fixture account per role, and the plan codes only where an assertion reads
#: them: `2211` and `2212` are what separates a domestic receivable from a
#: foreign one, and that separation is the point of the test that names them.
ROLE_ACCOUNT_CODES = {
    ROLE_CREANTE_TARA: "2211",
    ROLE_CREANTE_STRAINATATE: "2212",
    ROLE_VENIT_SERVICII: "6111",
    # 7128 arrives with the credit note: a return is a distribution expense, not
    # revenue with a minus (ADR-073 §7).
    ROLE_RETUR_REDUCERI: "7128",
}


@pytest.fixture
def sales_world(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
    source: uuid.UUID,  # noqa: F811 -- the fiscal act fixture, imported to be found
) -> dict[str, Any]:
    """A company with an open January, a numbering template, the conventions, the
    three role bindings this family needs, and one partner to invoice."""
    tenant = world["tenant_a"]
    company = company_of(tenant, "1002600000911", "Alpha Vânzări")
    grant_company(tenant, company, world["user_a"], world["user_a"])
    seed_period(seed, tenant, company)
    # Two templates: the journal entry's, and the sale's own. A company with no
    # template for the document type cannot number it, and numbering happens
    # inside `validate` -- so without this the sale never reaches the engine.
    seed_numbering(seed, tenant, company)
    seed_numbering(seed, tenant, company, document_type="sales.document")
    scale(seed, world, "accounting.amount_scale", 2)
    direction(seed, world, "half_up")

    context = TenantContext(tenant_id=tenant, user_id=world["user_a"], request_id="sales-posting")
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


def a_sale(
    world: dict[str, Any],
    *,
    revenue_kind: str = "services",
    resident: bool = True,
    amount: str = "5000.00",
    nature: str = "delivery",
) -> uuid.UUID:
    document_id = open_sale(
        company_id=world["company"],
        partner_id=world["partner"],
        document_date=ON,
        revenue_kind=revenue_kind,
        partner_resident=resident,
        nature=nature,
    )
    replace_lines(
        document_id,
        [
            LineInput(
                description="Servicii de contabilitate",
                quantity=Decimal("1"),
                unit_price=Decimal(amount),
                # The amounts are given rather than derived: the line layer stores
                # what it is told and applies no rate (ADR-037 section 3.1 is
                # open). No VAT here at all -- that is step 6.
                net_amount=Decimal(amount),
                vat_amount=Decimal("0"),
                total_amount=Decimal(amount),
                vat_regime_code="fara_tva",
                vat_rate=Decimal("0"),
            )
        ],
    )
    return document_id


def test_a_sale_reaches_the_ledger_through_the_engine(
    sales_world: dict[str, Any],
) -> None:
    """One route, and the chain walks back to the document (`R13`)."""
    with tenant_context(sales_world["context"]):
        document_id = a_sale(sales_world)
        result = issue_and_post(
            document_id=document_id,
            actor_user_id=sales_world["user"],
            request_id="sale-1",
            capability_snapshot=SNAPSHOT,
        )

        assert result.posted_now is True
        assert result.journal_entry_id is not None

        entry = JournalEntry.objects.get(id=result.journal_entry_id)
        lines = list(JournalLine.objects.filter(journal_entry_id=entry.id))

    assert len(lines) == 2
    assert sum(line.debit for line in lines) == sum(line.credit for line in lines)
    assert sum(line.debit for line in lines) == Decimal("5000.00")


def test_the_receivable_follows_the_counterparty_residence(
    sales_world: dict[str, Any],
) -> None:
    """The assertion a default would have made pass on the wrong account.

    `partner` has no residence field, so nothing could have derived this. Both
    sales are otherwise identical; the debit account is not.
    """
    with tenant_context(sales_world["context"]):
        domestic = a_sale(sales_world, resident=True)
        issue_and_post(
            document_id=domestic,
            actor_user_id=sales_world["user"],
            request_id="sale-domestic",
            capability_snapshot=SNAPSHOT,
        )
        foreign = a_sale(sales_world, resident=False)
        issue_and_post(
            document_id=foreign,
            actor_user_id=sales_world["user"],
            request_id="sale-foreign",
            capability_snapshot=SNAPSHOT,
        )

        debits = {
            document: _debit_accounts(document, sales_world) for document in (domestic, foreign)
        }

    assert debits[domestic] == {"2211"}
    assert debits[foreign] == {"2212"}


def test_a_sale_of_goods_is_refused_because_the_stock_half_is_missing(
    sales_world: dict[str, Any],
) -> None:
    """Half an entry balances. That is what makes it dangerous."""
    with tenant_context(sales_world["context"]):
        document_id = a_sale(sales_world, revenue_kind="goods")
        with pytest.raises(CostSideRequiresInventoryError):
            issue_and_post(
                document_id=document_id,
                actor_user_id=sales_world["user"],
                request_id="sale-goods",
                capability_snapshot=SNAPSHOT,
            )


def test_the_two_discriminators_are_required_at_the_door(
    sales_world: dict[str, Any],
) -> None:
    """Refused where a person can still fix it, not at posting time."""
    with tenant_context(sales_world["context"]):
        with pytest.raises(SaleMalformedError):
            open_sale(
                company_id=sales_world["company"],
                partner_id=sales_world["partner"],
                document_date=ON,
                revenue_kind="whatever",
                partner_resident=True,
            )
        with pytest.raises(SaleMalformedError):
            open_sale(
                company_id=sales_world["company"],
                partner_id=sales_world["partner"],
                document_date=ON,
                revenue_kind="services",
                partner_resident="yes",  # type: ignore[arg-type]
            )


def test_the_handler_refuses_a_payload_without_residence(
    sales_world: dict[str, Any],
) -> None:
    """The other half of the same rule, at the layer that would have to guess.

    The service refuses it at the door; this is the treatment refusing it too, so
    a caller that reached the engine another way meets the same answer.
    """
    from evidenta.accounting.posting.services.commercial import recognise_sale

    with pytest.raises(SalesDiscriminatorMissingError):
        recognise_sale(
            tenant_id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            accounting_date=ON,
            functional_currency="MDL",
            payload={
                "revenue_kind": "services",
                "total": "100.00",
                "currency": "MDL",
                "document_date": str(ON),
            },
        )


def test_issuing_twice_posts_once(sales_world: dict[str, Any]) -> None:
    """`R19`, on the event rather than on the endpoint."""
    with tenant_context(sales_world["context"]):
        document_id = a_sale(sales_world)
        first = issue_and_post(
            document_id=document_id,
            actor_user_id=sales_world["user"],
            request_id="sale-once",
            capability_snapshot=SNAPSHOT,
        )
        second = issue_and_post(
            document_id=document_id,
            actor_user_id=sales_world["user"],
            request_id="sale-twice",
            capability_snapshot=SNAPSHOT,
        )

        assert second.posted_now is False
        assert second.journal_entry_id == first.journal_entry_id
        assert AccountingEvent.objects.filter(source_document_id=document_id).count() == 1
        assert (
            JournalEntry.objects.filter(accounting_event_id=first.accounting_event_id).count() == 1
        )


def _debit_accounts(document_id: uuid.UUID, world: dict[str, Any]) -> set[str]:
    """The plan codes debited for a document, walked back through its event (`R13`)."""
    codes = {
        account_id: code
        for role, code in ROLE_ACCOUNT_CODES.items()
        for account_id in [world["accounts"][role]]
    }
    event = AccountingEvent.objects.get(source_document_id=document_id)
    return {
        codes[line.account_id]
        for line in JournalLine.objects.filter(
            journal_entry__accounting_event_id=event.id, debit__gt=0
        )
    }


def test_a_credit_note_is_a_distribution_expense_not_negative_revenue(
    sales_world: dict[str, Any],
) -> None:
    """ADR-073 §7, and the assertion is about which account, not which sign.

    A return could be posted by crediting revenue, and the entry would balance:
    `R11` passes, the trial balance totals agree, and turnover comes out
    understated by exactly the returns. The standard's chart puts the return in
    class 712, beside the other costs of selling, and that is what this reads.
    """
    with tenant_context(sales_world["context"]):
        document_id = a_sale(sales_world, nature="return", amount="800.00")
        result = issue_and_post(
            document_id=document_id,
            actor_user_id=sales_world["user"],
            request_id="return-1",
            capability_snapshot=SNAPSHOT,
        )
        assert result.journal_entry_id is not None
        lines = list(JournalLine.objects.filter(journal_entry_id=result.journal_entry_id))
        debit = next(line for line in lines if line.debit > 0)
        credit = next(line for line in lines if line.credit > 0)

    accounts = sales_world["accounts"]
    assert debit.account_id == accounts[ROLE_RETUR_REDUCERI]
    assert credit.account_id == accounts[ROLE_CREANTE_TARA]
    # And revenue was not touched at all -- the failure this test exists for.
    assert accounts[ROLE_VENIT_SERVICII] not in {line.account_id for line in lines}
    assert debit.debit == Decimal("800.00")


def test_a_return_and_a_delivery_are_different_events(sales_world: dict[str, Any]) -> None:
    """One document type, two facts -- so two event types and two idempotency keys.

    A shared key would make the second document of a pair look like a retry of the
    first, which is the shape a credit note against its own invoice would take.
    """
    with tenant_context(sales_world["context"]):
        issue_and_post(
            document_id=a_sale(sales_world, amount="100.00"),
            actor_user_id=sales_world["user"],
            request_id="pair-sale",
            capability_snapshot=SNAPSHOT,
        )
        issue_and_post(
            document_id=a_sale(sales_world, nature="return", amount="100.00"),
            actor_user_id=sales_world["user"],
            request_id="pair-return",
            capability_snapshot=SNAPSHOT,
        )
        kinds = set(
            AccountingEvent.objects.filter(company_id=sales_world["company"]).values_list(
                "event_type", flat=True
            )
        )

    assert kinds == {"sales.invoice_issued", "sales.return_issued"}


def test_an_advance_is_refused_by_name(sales_world: dict[str, Any]) -> None:
    """ADR-073 §6 kept its treatment unregistered on purpose.

    Posting only the first half -- crediting the advance -- would grow a balance
    of advances that nothing in the product could ever clear. The refusal names
    the decision rather than reporting a missing handler.
    """
    from evidenta.operations.sales.services.issuing import SaleNotIssuableError

    with tenant_context(sales_world["context"]):
        document_id = a_sale(sales_world, nature="advance", amount="500.00")
        with pytest.raises(SaleNotIssuableError, match="advance"):
            issue_and_post(
                document_id=document_id,
                actor_user_id=sales_world["user"],
                request_id="advance-1",
                capability_snapshot=SNAPSHOT,
            )
