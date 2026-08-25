"""The lineage chain, walked in both directions -- F1.3.3, R13.

    Journal Line -> Journal Entry -> Accounting Event -> Source Document -> Source

R13 requires the chain to exist and to be navigable **both ways** for every
financial effect. These tests walk it with real rows, real amounts and real
accounts -- not with the models, but through the public services each module
exposes, because that is how a caller will have to do it.

**No module answers the whole chain, and the test composes it.** A single
resolver would have to import every module's models, which is `D6` written as a
convenience. `ledger` answers "which entry, and which event"; `events` answers
"which document, and what else did that document cause".

**Where the chain honestly stops.** The last hop is a pair of columns and not a
joinable row: `source_document_id` carries no foreign key, because the document
lives in the module that produced it and a key would force `accounting` to know
that module's schema (`D2`). At F1 there are no business modules, so the chain
ends at the identifier. The test asserts that identifier round-trips rather than
pretending to dereference it.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from django.db import connection

from evidenta.accounting.events.services import lineage as event_lineage
from evidenta.accounting.ledger.models import JournalEntry, JournalLine
from evidenta.accounting.ledger.services import lineage as ledger_lineage
from evidenta.platform.rls.context import TenantContext, tenant_context

from .test_ledger import seed_event, seed_period

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

DOCUMENT_TYPE = "sales_invoice"


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="lineage")


@pytest.fixture
def company(
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> uuid.UUID:
    company_id = company_of(world["tenant_a"], "1002600000401", "Alpha Lineage")
    grant_company(world["tenant_a"], company_id, world["user_a"], world["user_a"])
    return company_id


@pytest.fixture
def accounts(
    seed: Callable[..., None], world: dict[str, uuid.UUID], company: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID]:
    """Two accounts, so the entry has a real debit and a real credit.

    Seeded rather than built through the chart service: this file is about
    lineage, and going through onboarding to get two accounts would make the
    failure of an unrelated module read as a lineage failure.
    """
    ids = (uuid.uuid4(), uuid.uuid4())
    # A receivable and a revenue account. `account_class` decides which statement
    # the balance lands in, so a wrong one moves money between the balance sheet
    # and the income statement rather than mislabelling a row.
    #
    # `origin = 'company'` rather than `'system'`: a system account must point at
    # the template row it came from (`company_account_system_has_template`), and
    # building a template here would drag chart publication into a test about
    # lineage. The distinction does not matter to the chain -- a line references
    # an account, whoever created it.
    for account_id, code, name, account_class, balance in (
        (ids[0], "2211", "Creanțe comerciale", "asset", "debit"),
        (ids[1], "6111", "Venituri din vânzări", "income", "credit"),
    ):
        seed(
            "INSERT INTO company_account (id, tenant_id, company_id, account_code, origin,"
            " name_ro, account_class, normal_balance, allows_subaccounts,"
            " currency_tracking, quantity_tracking, required_dimensions, is_blocked,"
            " valid_from, created_at, updated_at)"
            " VALUES (%s, %s, %s, %s, 'company', %s, %s, %s, false, false, false,"
            " '{}', false, '2020-01-01', now(), now())",
            [account_id, world["tenant_a"], company, code, name, account_class, balance],
        )
    return ids


@pytest.fixture
def posted(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    company: uuid.UUID,
    accounts: tuple[uuid.UUID, uuid.UUID],
    context: TenantContext,
) -> dict[str, object]:
    """One document, one event, one entry, two lines. The whole chain, once."""
    _, period_id = seed_period(seed, world["tenant_a"], company)
    event_id = seed_event(seed, world["tenant_a"], company, world["user_a"])
    document_id = uuid.uuid4()
    seed(
        "UPDATE accounting_event SET source_document_type = %s, source_document_id = %s,"
        " request_id = 'req-lineage' WHERE id = %s",
        [DOCUMENT_TYPE, document_id, event_id],
    )

    with tenant_context(context), connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL DEFERRED")
        entry = JournalEntry.objects.create(
            tenant_id=world["tenant_a"],
            company_id=company,
            entry_number="JE-LIN-1",
            accounting_date=date(2026, 1, 15),
            period_id=period_id,
            entry_type="standard",
            accounting_event_id=event_id,
            status="posted",
            posted_at=datetime.now(UTC),
            posted_by_user_id=world["user_a"],
            description="Factură emisă",
            total_debit=Decimal("1200.00"),
            total_credit=Decimal("1200.00"),
            request_id="req-lineage",
        )
        lines = [
            JournalLine.objects.create(
                tenant_id=world["tenant_a"],
                company_id=company,
                accounting_date=date(2026, 1, 15),
                document_date=date(2026, 1, 14),
                rate_date=date(2026, 1, 15),
                journal_entry_id=entry.id,
                line_number=number,
                account_id=account_id,
                debit=debit,
                credit=credit,
                currency="MDL",
                amount_currency=debit + credit,
                exchange_rate=Decimal("1"),
            )
            for number, account_id, debit, credit in (
                (1, accounts[0], Decimal("1200.00"), Decimal("0")),
                (2, accounts[1], Decimal("0"), Decimal("1200.00")),
            )
        ]
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

    return {
        "entry_id": entry.id,
        "line_ids": [line.id for line in lines],
        "event_id": event_id,
        "document_id": document_id,
        "period_id": period_id,
    }


# --- Forwards: from a figure to what caused it -------------------------------


def test_a_line_leads_to_the_document_that_caused_it(
    posted: dict[str, object], context: TenantContext
) -> None:
    """The direction an auditor asks for: this figure, why is it here.

    Composed from two modules' public services, with nothing imported from either
    module's models.
    """
    with tenant_context(context):
        origin = ledger_lineage.origin_of_line(int(posted["line_ids"][0]))  # type: ignore[index]
        assert origin is not None
        assert origin.journal_entry_id == posted["entry_id"]
        assert origin.accounting_event_id == posted["event_id"]

        source = event_lineage.origin_of_event(origin.accounting_event_id)
        assert source is not None
        assert source.source_document_type == DOCUMENT_TYPE
        assert source.source_document_id == posted["document_id"]


def test_the_chain_carries_the_amounts_and_the_accounts(
    posted: dict[str, object], accounts: tuple[uuid.UUID, uuid.UUID], context: TenantContext
) -> None:
    """R13 is about explaining a figure, so the figure has to survive the walk.

    A chain of identifiers that loses the amount answers "where did this come
    from" and not "is this right", which is the question an inspection actually
    asks.
    """
    with tenant_context(context):
        lines = list(
            JournalLine.objects.filter(
                journal_entry_id=uuid.UUID(str(posted["entry_id"]))
            ).order_by("line_number")
        )

    assert [line.account_id for line in lines] == list(accounts)
    assert lines[0].debit == Decimal("1200.0000")
    assert lines[1].credit == Decimal("1200.0000")
    assert sum(line.debit for line in lines) == sum(line.credit for line in lines)


def test_the_chain_records_the_capabilities_the_treatment_ran_under(
    posted: dict[str, object], context: TenantContext
) -> None:
    """R26 makes the profile an input to the treatment, so an entry cannot be
    justified years later without knowing which capabilities were active.
    """
    with tenant_context(context):
        source = event_lineage.origin_of_event(uuid.UUID(str(posted["event_id"])))
    assert source is not None
    assert source.capability_snapshot is not None


# --- Backwards: from a document to everything it caused ----------------------


def test_a_document_leads_to_every_effect_it_had(
    posted: dict[str, object], context: TenantContext
) -> None:
    """The reverse direction R13 requires, and the harder half.

    Forwards is a chain of foreign keys. Backwards crosses the one hop that has
    no key -- `source_document_id` -- so it depends on `acc_event_source_idx`
    existing, which is why that index was created with the table rather than
    added when a report needed it.
    """
    with tenant_context(context):
        event_ids = event_lineage.event_ids_of_document(
            DOCUMENT_TYPE, uuid.UUID(str(posted["document_id"]))
        )
        assert event_ids == [posted["event_id"]]

        entry_lines = ledger_lineage.line_ids_of_entry(uuid.UUID(str(posted["entry_id"])))
        assert entry_lines == posted["line_ids"]


def test_one_request_enumerates_everything_it_caused(
    posted: dict[str, object], context: TenantContext
) -> None:
    """Spec A section 9.3 -- a different question from the one above.

    "What did this invoice cause" is about a document; "what did this action
    cause" is about a moment. The second is what an audit asks when somebody
    says they pressed a button and something unexpected happened.
    """
    with tenant_context(context):
        assert event_lineage.event_ids_of_request("req-lineage") == [posted["event_id"]]


def test_an_entry_hands_over_to_the_events_module(
    posted: dict[str, object], context: TenantContext
) -> None:
    """The hop for a caller who starts at an entry rather than at a line."""
    with tenant_context(context):
        event_id = ledger_lineage.event_id_of_entry(uuid.UUID(str(posted["entry_id"])))
    assert event_id == posted["event_id"]


# --- The chain stops at the tenant boundary ----------------------------------


def test_another_tenant_walks_nowhere(
    posted: dict[str, object], world: dict[str, uuid.UUID]
) -> None:
    """Absence and invisibility answer the same way (IZ-04).

    Every hop returns nothing for a stranger, and nothing distinguishes "does not
    exist" from "is not yours" -- distinguishing them would be an enumeration
    oracle built by hand.
    """
    stranger = TenantContext(
        tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="lineage"
    )
    with tenant_context(stranger):
        assert ledger_lineage.origin_of_line(int(posted["line_ids"][0])) is None  # type: ignore[index]
        assert event_lineage.origin_of_event(uuid.UUID(str(posted["event_id"]))) is None
        assert (
            event_lineage.event_ids_of_document(
                DOCUMENT_TYPE, uuid.UUID(str(posted["document_id"]))
            )
            == []
        )
        assert event_lineage.event_ids_of_request("req-lineage") == []


def test_the_last_hop_is_an_identifier_and_the_test_says_so(
    posted: dict[str, object], context: TenantContext
) -> None:
    """The honest boundary of R13 at F1.

    `source_document_id` has no foreign key -- D2 -- and no business module
    exists to dereference it. What the chain guarantees today is that the
    identifier and its type survive the walk intact, so the module that owns the
    document can be asked. Asserting more would be asserting something the phase
    does not deliver.
    """
    with tenant_context(context):
        source = event_lineage.origin_of_event(uuid.UUID(str(posted["event_id"])))
    assert source is not None
    assert (source.source_document_type, source.source_document_id) == (
        DOCUMENT_TYPE,
        posted["document_id"],
    )
