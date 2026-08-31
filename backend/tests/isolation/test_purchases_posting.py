"""A supplier invoice reaches the ledger through the engine -- ADR-073, step 5.

The mirror of `test_sales_posting`, and the assertions that differ are the ones
worth having:

1. **The expense account follows `cost_destination`.** Four destinations, four
   roles, and a default would have made every one of them land on administrative
   services -- balanced, `R11` green, and a production cost missing from the cost
   of production at every reporting date.
2. **The payable follows residence**, for the same reason the receivable does.
3. **Stock cannot be bought here at all**, and not because a code refuses it: no
   destination names an asset, so there is no value under which it could travel.
4. **Idempotent on the event** (`R19`): recording twice posts once. Distinct from
   `R20`, which stops the same supplier document becoming two documents -- that one
   is proved in `test_documents`.

Under the application role, like everything in this suite (`T1`).
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
    ROLE_ALTE_CHELTUIELI_DISTRIBUIRE,
    ROLE_CHELTUIELI_ADMINISTRATIVE,
    ROLE_DATORII_STRAINATATE,
    ROLE_DATORII_TARA,
)
from evidenta.accounting.slots.models import AccountRoleBinding
from evidenta.operations.purchases.services.documents import (
    CostDestinationInvalidError,
    open_purchase,
)
from evidenta.operations.purchases.services.recording import record_and_post
from evidenta.platform.documents.services.lines import LineInput, replace_lines
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.isolation.test_formulas import seed_account
from tests.isolation.test_ledger import seed_period
from tests.isolation.test_line_rounding import direction, scale, source  # noqa: F401
from tests.isolation.test_manual_entry import seed_template as seed_numbering

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

ON = date(2026, 1, 20)
THEIRS = date(2026, 1, 18)

SNAPSHOT: dict[str, Any] = {"version": 1, "on": "2026-01-01", "activated": [], "usable": []}

#: The plan codes are named here because two assertions read them: 7135 against
#: 7129 is what separates an administrative cost from a commercial one, and 5211
#: against 5212 what separates a domestic debt from a foreign one.
ROLE_ACCOUNT_CODES = {
    ROLE_DATORII_TARA: "5211",
    ROLE_DATORII_STRAINATATE: "5212",
    ROLE_CHELTUIELI_ADMINISTRATIVE: "7135",
    ROLE_ALTE_CHELTUIELI_DISTRIBUIRE: "7129",
}


@pytest.fixture
def purchases_world(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
    source: uuid.UUID,  # noqa: F811 -- the fiscal act fixture, imported to be found
) -> dict[str, Any]:
    """A company with an open January, numbering, conventions, four bindings, a supplier."""
    tenant = world["tenant_a"]
    company = company_of(tenant, "1002600000912", "Alpha Achiziții")
    grant_company(tenant, company, world["user_a"], world["user_a"])
    seed_period(seed, tenant, company)
    seed_numbering(seed, tenant, company)
    seed_numbering(seed, tenant, company, document_type="purchases.document")
    scale(seed, world, "accounting.amount_scale", 2)
    direction(seed, world, "half_up")

    context = TenantContext(
        tenant_id=tenant, user_id=world["user_a"], request_id="purchases-posting"
    )
    accounts = {
        role: seed_account(seed, tenant, company, code) for role, code in ROLE_ACCOUNT_CODES.items()
    }
    partner_id = uuid.uuid4()
    seed(
        "INSERT INTO partner (id, tenant_id, kind, legal_name, is_customer, is_supplier,"
        " is_active, created_at, updated_at)"
        " VALUES (%s, %s, 'legal_entity', 'Furnizor SRL', false, true, true, now(), now())",
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


def a_purchase(
    world: dict[str, Any],
    *,
    destination: str = "administrative",
    resident: bool = True,
    amount: str = "3000.00",
    reference: str = "AA 0001",
) -> uuid.UUID:
    document_id = open_purchase(
        company_id=world["company"],
        partner_id=world["partner"],
        document_date=ON,
        supplier_document_number=reference,
        supplier_document_date=THEIRS,
        cost_destination=destination,
        partner_resident=resident,
    )
    replace_lines(
        document_id,
        [
            LineInput(
                description="Servicii de audit",
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
    return document_id


def _accounts_of(entry_id: uuid.UUID) -> dict[str, uuid.UUID]:
    """The two sides of a two-line entry, by side rather than by order."""
    lines = list(JournalLine.objects.filter(journal_entry_id=entry_id))
    assert len(lines) == 2
    debit = next(line for line in lines if line.debit > 0)
    credit = next(line for line in lines if line.credit > 0)
    return {"debit": debit.account_id, "credit": credit.account_id}


def test_a_purchase_reaches_the_ledger_through_the_engine(
    purchases_world: dict[str, Any],
) -> None:
    with tenant_context(purchases_world["context"]):
        document_id = a_purchase(purchases_world)
        result = record_and_post(
            document_id=document_id,
            actor_user_id=purchases_world["user"],
            request_id="purchase-1",
            capability_snapshot=SNAPSHOT,
        )

        assert result.posted_now is True
        assert result.journal_entry_id is not None

        entry = JournalEntry.objects.get(id=result.journal_entry_id)
        lines = list(JournalLine.objects.filter(journal_entry_id=entry.id))

    assert len(lines) == 2
    assert sum(line.debit for line in lines) == sum(line.credit for line in lines)
    assert sum(line.debit for line in lines) == Decimal("3000.00")


def test_the_expense_account_follows_the_destination(
    purchases_world: dict[str, Any],
) -> None:
    """The assertion a default would have made pass on the wrong account.

    Two invoices from the same supplier, identical except for where the cost
    lands. Nothing on the document could have derived it: a service invoice does
    not say whether the service was administrative or commercial.
    """
    with tenant_context(purchases_world["context"]):
        administrative = record_and_post(
            document_id=a_purchase(purchases_world, destination="administrative", reference="A 1"),
            actor_user_id=purchases_world["user"],
            request_id="purchase-adm",
            capability_snapshot=SNAPSHOT,
        )
        commercial = record_and_post(
            document_id=a_purchase(purchases_world, destination="commercial", reference="A 2"),
            actor_user_id=purchases_world["user"],
            request_id="purchase-com",
            capability_snapshot=SNAPSHOT,
        )
        assert administrative.journal_entry_id is not None
        assert commercial.journal_entry_id is not None
        sides = (
            _accounts_of(administrative.journal_entry_id),
            _accounts_of(commercial.journal_entry_id),
        )

    accounts = purchases_world["accounts"]
    assert sides[0]["debit"] == accounts[ROLE_CHELTUIELI_ADMINISTRATIVE]
    assert sides[1]["debit"] == accounts[ROLE_ALTE_CHELTUIELI_DISTRIBUIRE]
    # And the payable did not move with it: one discriminator, one account.
    assert sides[0]["credit"] == sides[1]["credit"] == accounts[ROLE_DATORII_TARA]


def test_the_payable_follows_the_supplier_residence(
    purchases_world: dict[str, Any],
) -> None:
    with tenant_context(purchases_world["context"]):
        domestic = record_and_post(
            document_id=a_purchase(purchases_world, resident=True, reference="B 1"),
            actor_user_id=purchases_world["user"],
            request_id="purchase-dom",
            capability_snapshot=SNAPSHOT,
        )
        foreign = record_and_post(
            document_id=a_purchase(purchases_world, resident=False, reference="B 2"),
            actor_user_id=purchases_world["user"],
            request_id="purchase-for",
            capability_snapshot=SNAPSHOT,
        )
        assert domestic.journal_entry_id is not None
        assert foreign.journal_entry_id is not None
        sides = (_accounts_of(domestic.journal_entry_id), _accounts_of(foreign.journal_entry_id))

    accounts = purchases_world["accounts"]
    assert sides[0]["credit"] == accounts[ROLE_DATORII_TARA]
    assert sides[1]["credit"] == accounts[ROLE_DATORII_STRAINATATE]


def test_a_destination_outside_the_vocabulary_is_refused(
    purchases_world: dict[str, Any],
) -> None:
    """Refused where the document is opened, with a code of its own.

    Not at the handler: by the time the fact reaches the engine the document
    already exists, and a purchase whose cost has nowhere to land is a row
    somebody has to clean up. The vocabulary is closed in code, so the refusal is
    the same on both sides of the seam.
    """
    with tenant_context(purchases_world["context"]), pytest.raises(CostDestinationInvalidError):
        open_purchase(
            company_id=purchases_world["company"],
            partner_id=purchases_world["partner"],
            document_date=ON,
            supplier_document_number="C 1",
            supplier_document_date=THEIRS,
            cost_destination="stoc",
            partner_resident=True,
        )


def test_recording_twice_posts_once(purchases_world: dict[str, Any]) -> None:
    """`R19`, on the event and not on the endpoint."""
    with tenant_context(purchases_world["context"]):
        document_id = a_purchase(purchases_world, reference="D 1")
        first = record_and_post(
            document_id=document_id,
            actor_user_id=purchases_world["user"],
            request_id="purchase-first",
            capability_snapshot=SNAPSHOT,
        )
        second = record_and_post(
            document_id=document_id,
            actor_user_id=purchases_world["user"],
            request_id="purchase-second",
            capability_snapshot=SNAPSHOT,
        )
        events = AccountingEvent.objects.filter(
            company_id=purchases_world["company"], event_type="purchases.invoice_recorded"
        ).count()
        entries = JournalEntry.objects.filter(company_id=purchases_world["company"]).count()

    assert first.posted_now is True
    assert second.posted_now is False
    assert second.accounting_event_id == first.accounting_event_id
    assert events == 1
    assert entries == 1
