"""Opening balances -- F1.7.2, Spec B section 8, ADR-039 section 11.

Three things are being proved here, and only the first is about arithmetic.

**One route.** A company's balances reach the ledger through
``opening.balance_posted`` and the engine, exactly like a manual note and exactly
like the sales invoice that does not exist yet. There is no bulk writer and no
"seed the books" path -- so the assertions below are mostly about the route: that
an accounting event exists and the entry names it, that the batch is the source
document the R13 chain walks back to, that a replay produces no second trial
balance.

**Six sets, one entry.** GL, customers, suppliers, stock, assets, payroll. The
first five post; the analytical four *replace* their GL row rather than adding to
it, and the sixth does not post at all (`OD-04`).

**A start period that does not move.** Once a company's balances are posted, a
batch at another date is refused -- by the service with a code, and by the
database with a trigger, which is the barrier the 1C importer meets.

**Under the application role, like every test in this suite** (T1). Every read
the engine makes -- the period, the chart, the numbering template -- goes through
the policies a request goes through.

**No account code from the published chart appears.** The engine resolves
accounts by id and never reads a code; the fixture uses codes no chart uses. The
content of the general chart is `OD-23`, open, and a plausible `221` in a fixture
is that content arriving through the back door (R15).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from django.db import transaction
from django.db.utils import ProgrammingError

from evidenta.accounting.events.models import AccountingEvent, EventStatus
from evidenta.accounting.events.registry import REGISTRY, resolve_handler
from evidenta.accounting.events.services.lineage import origin_of_event
from evidenta.accounting.ledger.models import EntryStatus, EntryType, JournalEntry, JournalLine
from evidenta.accounting.opening.errors import (
    AccountMissingFromGlError,
    AnalyticalMismatchError,
    BatchNotDraftError,
    BatchNotFoundError,
    CounterpartInGlError,
    EmptyGlSetError,
    ForeignCurrencyBalanceError,
    GlOutOfBalanceError,
    IllegalBatchTransitionError,
    OpeningBalanceError,
    StartPeriodFixedError,
)
from evidenta.accounting.opening.models import (
    BatchSource,
    BatchStatus,
    OpeningBalanceBatch,
    OpeningBalanceGl,
    OpeningBalancePayrollCumulative,
)
from evidenta.accounting.opening.services.batches import (
    AssetRow,
    GlRow,
    InventoryRow,
    PartnerRow,
    PayrollRow,
    add_rows,
    create_batch,
    reject_batch,
    reopen_batch,
    validate_batch,
)
from evidenta.accounting.opening.services.posting import (
    ENTRY_TYPE,
    EVENT_TYPE,
    SOURCE_DOCUMENT_TYPE,
    SOURCE_MODULE,
    post_batch,
)
from evidenta.accounting.periods.errors import PeriodNotOpenError
from evidenta.accounting.posting.dimensions import MissingRequiredDimensionError
from evidenta.accounting.posting.invariants import AccountNotPostableError
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

#: The books open on the first day of the exercise. Everything is dated to it.
AS_OF = date(2026, 1, 1)

#: A date in a month that is closed -- the second period of the same exercise.
IN_CLOSED_MONTH = date(2026, 2, 10)

#: The profile as `platform.capabilities` writes it (R26). A company with nothing
#: activated is still a company, and the snapshot says so explicitly rather than
#: being absent -- an absent one is refused, which is the point of F1.4.1.
SNAPSHOT: dict[str, Any] = {
    "version": 1,
    "on": AS_OF.isoformat(),
    "activated": [],
    "usable": [],
}

MDL = "MDL"


def money(value: str) -> Decimal:
    return Decimal(value)


# --- the world ---------------------------------------------------------------


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="opening")


def seed_account(
    seed: Callable[..., None],
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    code: str,
    *,
    blocked: bool = False,
    requires: str = "{}",
) -> uuid.UUID:
    """One account of the company's own. `requires` is a Postgres array literal.

    What it requires it also declares as carried, in the same order (ADR-048):
    `company_account_required_within_slots` refuses an account that demands an
    axis it does not carry, and a fixture is not exempt from the plan's rule.
    """
    account_id = uuid.uuid4()
    slots = [name for name in requires.strip("{}").split(",") if name]
    padded: list[str | None] = [*slots, None, None, None, None][:4]
    seed(
        "INSERT INTO company_account (id, tenant_id, company_id, account_code,"
        " parent_id, origin, template_account_id, name_ro, account_class,"
        " normal_balance, allows_subaccounts, currency_tracking, quantity_tracking,"
        " required_dimensions, slot_1_dimension, slot_2_dimension, slot_3_dimension,"
        " slot_4_dimension, is_blocked, valid_from, valid_to, created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, NULL, 'company', NULL, %s, 'asset', 'debit',"
        " false, false, false, %s::text[], %s, %s, %s, %s, %s, '2020-01-01', NULL, now(), now())",
        [
            account_id,
            tenant_id,
            company_id,
            code,
            f"Cont de fixture {code}",
            requires,
            *padded,
            blocked,
        ],
    )
    return account_id


def seed_period(
    seed: Callable[..., None],
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    year_id: uuid.UUID,
    *,
    period_no: int,
    start: str,
    end: str,
    status: str,
) -> uuid.UUID:
    period_id = uuid.uuid4()
    closed_at = "now()" if status in ("closed", "locked") else "NULL"
    seed(
        "INSERT INTO period (id, tenant_id, company_id, fiscal_year_id, period_no,"
        " start_date, end_date, status, reopened_count, closed_at, created_at, updated_at)"
        f" VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, {closed_at}, now(), now())",
        [period_id, tenant_id, company_id, year_id, period_no, start, end, status],
    )
    return period_id


def seed_company_world(
    seed: Callable[..., None],
    tenant: uuid.UUID,
    user: uuid.UUID,
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
    *,
    idno: str,
    name: str,
) -> dict[str, uuid.UUID]:
    """One company with an exercise, two months, a chart and a numbering template."""
    company = company_of(tenant, idno, name)
    grant_company(tenant, company, user, user)

    year_id = uuid.uuid4()
    seed(
        "INSERT INTO fiscal_year (id, tenant_id, company_id, code, start_date, end_date,"
        " status, created_at, updated_at)"
        " VALUES (%s, %s, %s, '2026', '2026-01-01', '2026-12-31', 'open', now(), now())",
        [year_id, tenant, company],
    )
    seed(
        # See the note in `test_operation_templates`: the regime and the validity
        # window are stated, never defaulted.
        "INSERT INTO numbering_template (id, tenant_id, company_id, document_type,"
        " series, prefix, suffix, separator, digits, include_year, year_format,"
        " reset_policy, regime, valid_from, created_at, updated_at)"
        " VALUES (%s, %s, %s, 'journal_entry', '', 'SI', '', '-', 4, true, 'yyyy',"
        " 'yearly', 'own', DATE '2000-01-01', now(), now())",
        [uuid.uuid4(), tenant, company],
    )

    return {
        "tenant": tenant,
        "company": company,
        "user": user,
        "open_period": seed_period(
            seed,
            tenant,
            company,
            year_id,
            period_no=1,
            start="2026-01-01",
            end="2026-01-31",
            status="open",
        ),
        "closed_period": seed_period(
            seed,
            tenant,
            company,
            year_id,
            period_no=2,
            start="2026-02-01",
            end="2026-02-28",
            status="closed",
        ),
        # Two ordinary accounts, the technical counterpart, and one of each shape
        # the analytical sets need. `FIXTURE-*` codes, never a code from a real
        # chart -- see the module docstring.
        "cash": seed_account(seed, tenant, company, "FIXTURE-CASH"),
        "equity": seed_account(seed, tenant, company, "FIXTURE-EQ"),
        "counterpart": seed_account(seed, tenant, company, "FIXTURE-TECH"),
        "receivable": seed_account(seed, tenant, company, "FIXTURE-RECV"),
        "payable": seed_account(seed, tenant, company, "FIXTURE-PAY"),
        "stock": seed_account(seed, tenant, company, "FIXTURE-STOCK"),
        "asset_cost": seed_account(seed, tenant, company, "FIXTURE-ASSET"),
        "asset_depreciation": seed_account(seed, tenant, company, "FIXTURE-DEPR"),
        "blocked": seed_account(seed, tenant, company, "FIXTURE-BLOCKED", blocked=True),
        "needs_partner": seed_account(
            seed, tenant, company, "FIXTURE-NEEDSP", requires="{partner}"
        ),
    }


@pytest.fixture
def scene(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> dict[str, uuid.UUID]:
    return seed_company_world(
        seed,
        world["tenant_a"],
        world["user_a"],
        company_of,
        grant_company,
        idno="1002600000701",
        name="Alpha Solduri",
    )


# --- building a batch --------------------------------------------------------


def open_batch(scene: dict[str, uuid.UUID], on: date = AS_OF) -> OpeningBalanceBatch:
    return create_batch(
        company_id=scene["company"],
        as_of_date=on,
        source=BatchSource.MANUAL,
        counterpart_account_id=scene["counterpart"],
        created_by_user_id=scene["user"],
    )


def simple_batch(scene: dict[str, uuid.UUID], amount: str = "1000.0000") -> OpeningBalanceBatch:
    """The smallest correct batch: one debit, one credit, nothing analytical."""
    batch = open_batch(scene)
    add_rows(
        batch.id,
        gl=[
            GlRow(account_id=scene["cash"], debit=money(amount)),
            GlRow(account_id=scene["equity"], credit=money(amount)),
        ],
    )
    return batch


def post(
    scene: dict[str, uuid.UUID],
    batch: OpeningBalanceBatch,
    *,
    key: str = "opening-1",
) -> Any:
    return post_batch(
        batch_id=batch.id,
        functional_currency=MDL,
        idempotency_key=key,
        actor_user_id=scene["user"],
        request_id="opening-test",
        capability_snapshot=dict(SNAPSHOT),
    )


def lines_of(entry_id: uuid.UUID) -> list[JournalLine]:
    return list(JournalLine.objects.filter(journal_entry_id=entry_id).order_by("line_number"))


# --- the route ---------------------------------------------------------------


def test_a_batch_reaches_the_ledger_through_an_accounting_event(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The whole criterion of ADR-039 section 11 in one assertion.

    Not "an entry exists" -- an entry exists, **names the event that produced
    it**, and is typed `opening`. Balances written straight into `journal_entry`
    would look identical in a trial balance and would answer "where did these
    numbers come from" with nothing.
    """
    with tenant_context(context):
        batch = simple_batch(scene)
        validate_batch(batch.id, MDL)
        result = post(scene, batch)

        entry = JournalEntry.objects.get(id=result.journal_entry_id)
        event = AccountingEvent.objects.get(id=result.accounting_event_id)

        assert result.posted_now is True
        assert entry.accounting_event_id == event.id
        assert entry.status == EntryStatus.POSTED
        assert entry.entry_type == ENTRY_TYPE == EntryType.OPENING
        assert entry.accounting_date == AS_OF
        assert entry.period_id == scene["open_period"]
        assert entry.description == "Solduri inițiale la 2026-01-01"
        assert event.event_type == EVENT_TYPE
        assert event.source_module == SOURCE_MODULE
        assert event.status == EventStatus.POSTED


def test_the_batch_is_the_source_document_the_chain_walks_back_to(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """R13, and the one hop the manual note cannot make.

    `Journal Line -> Journal Entry -> Accounting Event -> Source Document ->
    Sursa`. A manual note stops at an identifier with no table behind it; an
    opening batch resolves to a row that still holds every figure that was loaded.
    """
    with tenant_context(context):
        batch = simple_batch(scene)
        validate_batch(batch.id, MDL)
        result = post(scene, batch)

        origin = origin_of_event(result.accounting_event_id)
        assert origin is not None
        assert origin.source_module == SOURCE_MODULE
        assert origin.source_document_type == SOURCE_DOCUMENT_TYPE
        assert origin.source_document_id == batch.id

        assert OpeningBalanceBatch.objects.filter(id=origin.source_document_id).exists()


def test_the_batch_records_the_entry_it_produced(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        batch = simple_batch(scene)
        validate_batch(batch.id, MDL)
        result = post(scene, batch)

        stored = OpeningBalanceBatch.objects.get(id=batch.id)
        assert stored.status == BatchStatus.POSTED
        assert stored.posted_at is not None
        assert stored.validated_at is not None
        assert stored.journal_entry_id == result.journal_entry_id


def test_the_entry_is_numbered_from_the_company_template(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """ADR-022: the number comes from the company's own template, not a counter
    this module keeps."""
    with tenant_context(context):
        batch = simple_batch(scene)
        validate_batch(batch.id, MDL)
        result = post(scene, batch)

        entry = JournalEntry.objects.get(id=result.journal_entry_id)
        assert entry.entry_number == "SI-2026-0001"


# --- the technical opening account -------------------------------------------


def test_every_balance_faces_the_technical_account(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Spec B section 8.3. Pairwise, and that is what makes Cartea Mare readable.

    Each balance is followed by its mirror on the technical account, so every
    account's correspondence column names the opening account rather than an
    unrelated creditor that happened to be next in the entry.
    """
    with tenant_context(context):
        batch = simple_batch(scene, "1000.0000")
        validate_batch(batch.id, MDL)
        result = post(scene, batch)

        lines = lines_of(result.journal_entry_id)
        assert [line.account_id for line in lines] == [
            scene["cash"],
            scene["counterpart"],
            scene["equity"],
            scene["counterpart"],
        ]
        assert lines[0].debit == money("1000.0000")
        assert lines[1].credit == money("1000.0000")
        assert lines[2].credit == money("1000.0000")
        assert lines[3].debit == money("1000.0000")


def test_the_technical_account_ends_with_a_zero_balance(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """ "Verificarea lui este testul ca importul e complet" -- Spec B section 8.3.

    Measured on the ledger rather than argued: the sum of what the technical
    account received equals the sum of what it gave, over an entry that carries
    all five posting sets at once.
    """
    with tenant_context(context):
        batch = full_batch(scene)
        validate_batch(batch.id, MDL)
        result = post(scene, batch)

        technical = [
            line
            for line in lines_of(result.journal_entry_id)
            if line.account_id == scene["counterpart"]
        ]
        assert technical, "the technical account received no line at all"
        assert sum(line.debit for line in technical) == sum(line.credit for line in technical)

        entry = JournalEntry.objects.get(id=result.journal_entry_id)
        assert entry.total_debit == entry.total_credit


def test_a_quantity_does_not_cross_to_the_technical_account(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """A quantity on the opening account would be stock on an account that holds
    none."""
    with tenant_context(context):
        batch = full_batch(scene)
        validate_batch(batch.id, MDL)
        result = post(scene, batch)

        for line in lines_of(result.journal_entry_id):
            if line.account_id == scene["counterpart"]:
                assert line.quantity is None
                assert line.uom_id is None


# --- the six sets ------------------------------------------------------------


def full_batch(scene: dict[str, uuid.UUID]) -> OpeningBalanceBatch:
    """One batch carrying all six sets, with every control total consistent.

    GL:  cash 1000 D, stock 700 D, asset cost 500 D, receivable 300 D
         equity 1900 C, payable 400 C, depreciation 200 C
    Debit 2500, credit 2500.
    """
    batch = open_batch(scene)
    ids = {
        "partner_a": uuid.uuid4(),
        "partner_b": uuid.uuid4(),
        "item": uuid.uuid4(),
        "warehouse": uuid.uuid4(),
        "uom": uuid.uuid4(),
        "asset": uuid.uuid4(),
        "employee": uuid.uuid4(),
    }
    batch.fixture_ids = ids  # type: ignore[attr-defined]

    add_rows(
        batch.id,
        gl=[
            GlRow(account_id=scene["cash"], debit=money("1000.0000")),
            GlRow(account_id=scene["stock"], debit=money("700.0000")),
            GlRow(account_id=scene["asset_cost"], debit=money("500.0000")),
            GlRow(account_id=scene["receivable"], debit=money("300.0000")),
            GlRow(account_id=scene["equity"], credit=money("1900.0000")),
            GlRow(account_id=scene["payable"], credit=money("400.0000")),
            GlRow(account_id=scene["asset_depreciation"], credit=money("200.0000")),
        ],
        receivables=[
            PartnerRow(
                account_id=scene["receivable"],
                partner_id=ids["partner_a"],
                debit=money("300.0000"),
                document_type="factura",
                document_number="AA-0001",
                document_date=date(2025, 11, 30),
                due_date=date(2026, 1, 30),
            )
        ],
        payables=[
            PartnerRow(
                account_id=scene["payable"],
                partner_id=ids["partner_b"],
                credit=money("400.0000"),
                document_number="BB-0002",
            )
        ],
        inventory=[
            InventoryRow(
                account_id=scene["stock"],
                item_id=ids["item"],
                uom_id=ids["uom"],
                quantity=money("7.000000"),
                total_cost=money("700.0000"),
                warehouse_id=ids["warehouse"],
                lot="L-2025-11",
                unit_cost=money("100.000000"),
            )
        ],
        assets=[
            AssetRow(
                asset_id=ids["asset"],
                cost_account_id=scene["asset_cost"],
                depreciation_account_id=scene["asset_depreciation"],
                entry_cost=money("500.0000"),
                accumulated_depreciation=money("200.0000"),
                in_service_date=date(2024, 5, 1),
                remaining_months=36,
            )
        ],
        payroll=[
            PayrollRow(
                employee_id=ids["employee"],
                code="FIXTURE-INCOME",
                amount=money("12345.6700"),
                from_date=date(2026, 1, 1),
            )
        ],
    )
    return batch


def test_an_undecomposed_gl_row_posts_as_it_stands(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        batch = full_batch(scene)
        validate_batch(batch.id, MDL)
        result = post(scene, batch)

        cash = [
            line for line in lines_of(result.journal_entry_id) if line.account_id == scene["cash"]
        ]
        assert len(cash) == 1
        assert cash[0].debit == money("1000.0000")
        assert cash[0].partner_id is None


def test_an_analytical_set_replaces_its_gl_row_and_carries_the_dimension(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The whole reason the sets are decompositions and not additions.

    The receivable account posts **once**, with the partner on it -- not once
    from the GL set and once from the customer set, which would double every
    receivable in the company.
    """
    with tenant_context(context):
        batch = full_batch(scene)
        ids = batch.fixture_ids  # type: ignore[attr-defined]
        validate_batch(batch.id, MDL)
        result = post(scene, batch)

        receivable = [
            line
            for line in lines_of(result.journal_entry_id)
            if line.account_id == scene["receivable"]
        ]
        assert len(receivable) == 1
        assert receivable[0].debit == money("300.0000")
        assert receivable[0].partner_id == ids["partner_a"]

        payable = [
            line
            for line in lines_of(result.journal_entry_id)
            if line.account_id == scene["payable"]
        ]
        assert len(payable) == 1
        assert payable[0].credit == money("400.0000")
        assert payable[0].partner_id == ids["partner_b"]


def test_stock_carries_item_warehouse_quantity_and_unit(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """`journal_line` may hold a quantity only together with its unit
    (`journal_line_quantity_has_unit`), which is why the set requires both."""
    with tenant_context(context):
        batch = full_batch(scene)
        ids = batch.fixture_ids  # type: ignore[attr-defined]
        validate_batch(batch.id, MDL)
        result = post(scene, batch)

        stock = [
            line for line in lines_of(result.journal_entry_id) if line.account_id == scene["stock"]
        ]
        assert len(stock) == 1
        assert stock[0].debit == money("700.0000")
        assert stock[0].item_id == ids["item"]
        assert stock[0].warehouse_id == ids["warehouse"]
        assert stock[0].quantity == money("7.000000")
        assert stock[0].uom_id == ids["uom"]


def test_an_asset_posts_cost_and_depreciation_on_two_accounts(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Two numbers, kept apart. A single net book value would post correctly and
    lose what every depreciation calculation from F2 onwards needs."""
    with tenant_context(context):
        batch = full_batch(scene)
        ids = batch.fixture_ids  # type: ignore[attr-defined]
        validate_batch(batch.id, MDL)
        result = post(scene, batch)

        lines = lines_of(result.journal_entry_id)
        cost = [line for line in lines if line.account_id == scene["asset_cost"]]
        depreciation = [line for line in lines if line.account_id == scene["asset_depreciation"]]

        assert len(cost) == len(depreciation) == 1
        assert cost[0].debit == money("500.0000")
        assert depreciation[0].credit == money("200.0000")
        assert cost[0].asset_id == depreciation[0].asset_id == ids["asset"]


def test_an_asset_with_no_depreciation_posts_one_line(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """A zero leg produces no line rather than a zero one -- the ledger refuses a
    line with no amount, and an asset bought last month has no depreciation."""
    with tenant_context(context):
        batch = open_batch(scene)
        asset_id = uuid.uuid4()
        add_rows(
            batch.id,
            gl=[
                GlRow(account_id=scene["asset_cost"], debit=money("500.0000")),
                GlRow(account_id=scene["equity"], credit=money("500.0000")),
            ],
            assets=[
                AssetRow(
                    asset_id=asset_id,
                    cost_account_id=scene["asset_cost"],
                    depreciation_account_id=scene["asset_depreciation"],
                    entry_cost=money("500.0000"),
                    in_service_date=date(2025, 12, 1),
                )
            ],
        )
        validate_batch(batch.id, MDL)
        result = post(scene, batch)

        lines = lines_of(result.journal_entry_id)
        assert not [line for line in lines if line.account_id == scene["asset_depreciation"]]
        assert all(line.debit + line.credit > 0 for line in lines)


def test_payroll_cumulatives_are_stored_and_never_posted(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """`OD-04`, as behaviour rather than as a comment.

    Cumulatives are not balances -- they are the base an IPC calculation
    continues from when payroll is activated mid-year. They ride with the batch,
    frozen and auditable, and nothing in this module interprets `code`.
    """
    with tenant_context(context):
        batch = full_batch(scene)
        ids = batch.fixture_ids  # type: ignore[attr-defined]
        validate_batch(batch.id, MDL)
        result = post(scene, batch)

        stored = list(OpeningBalancePayrollCumulative.objects.filter(batch_id=batch.id))
        assert len(stored) == 1
        assert stored[0].code == "FIXTURE-INCOME"
        assert stored[0].amount == money("12345.6700")

        for line in lines_of(result.journal_entry_id):
            assert line.employee_id is None
        assert not JournalLine.objects.filter(
            journal_entry_id=result.journal_entry_id, employee_id=ids["employee"]
        ).exists()


def test_the_lines_carry_the_functional_currency_at_rate_one(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """ADR-039 section 3: the identity case, not a conversion. Nothing multiplies,
    so no rounding rule is involved -- which is what keeps `DNB-08` out of it."""
    with tenant_context(context):
        batch = simple_batch(scene)
        validate_batch(batch.id, MDL)
        result = post(scene, batch)

        for line in lines_of(result.journal_entry_id):
            assert line.currency == MDL
            assert line.exchange_rate == Decimal(1)
            assert line.amount_currency == line.debit + line.credit
            assert line.accounting_date == line.document_date == line.rate_date == AS_OF


# --- the checks of Spec B section 8.2 ----------------------------------------


def test_an_unbalanced_gl_set_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        batch = open_batch(scene)
        add_rows(
            batch.id,
            gl=[
                GlRow(account_id=scene["cash"], debit=money("1000.0000")),
                GlRow(account_id=scene["equity"], credit=money("999.0000")),
            ],
        )
        with pytest.raises(GlOutOfBalanceError) as refusal:
            validate_batch(batch.id, MDL)
        assert refusal.value.code == "opening.gl_out_of_balance"
        assert not JournalEntry.objects.exists()


def test_a_decomposition_that_disagrees_with_its_control_total_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Spec B section 8.2, second bullet. The one check the engine cannot make:
    by the time it sees the lines, the analytical rows *are* the balance."""
    with tenant_context(context):
        batch = open_batch(scene)
        add_rows(
            batch.id,
            gl=[
                GlRow(account_id=scene["receivable"], debit=money("300.0000")),
                GlRow(account_id=scene["equity"], credit=money("300.0000")),
            ],
            receivables=[
                PartnerRow(
                    account_id=scene["receivable"],
                    partner_id=uuid.uuid4(),
                    debit=money("290.0000"),
                )
            ],
        )
        with pytest.raises(AnalyticalMismatchError) as refusal:
            validate_batch(batch.id, MDL)
        assert refusal.value.code == "opening.analytical_mismatch"


def test_detail_for_an_account_absent_from_the_gl_set_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """A different defect from a mismatch, and told apart on purpose: a mismatch
    means one of two numbers is wrong, this means the trial balance is
    incomplete."""
    with tenant_context(context):
        batch = open_batch(scene)
        add_rows(
            batch.id,
            gl=[
                GlRow(account_id=scene["cash"], debit=money("300.0000")),
                GlRow(account_id=scene["equity"], credit=money("300.0000")),
            ],
            receivables=[
                PartnerRow(
                    account_id=scene["receivable"],
                    partner_id=uuid.uuid4(),
                    debit=money("300.0000"),
                )
            ],
        )
        with pytest.raises(AccountMissingFromGlError) as refusal:
            validate_batch(batch.id, MDL)
        assert refusal.value.code == "opening.account_missing_from_gl"


def test_a_batch_with_no_gl_rows_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Including one carrying only payroll cumulatives.

    Refused rather than posted as an entry with no lines. Mid-year payroll
    activation is a real case Spec B section 8.1 names -- and it arrives with the
    company's balances at that date, which is a GL set.
    """
    with tenant_context(context):
        batch = open_batch(scene)
        add_rows(
            batch.id,
            payroll=[
                PayrollRow(
                    employee_id=uuid.uuid4(),
                    code="FIXTURE-INCOME",
                    amount=money("100.0000"),
                    from_date=AS_OF,
                )
            ],
        )
        with pytest.raises(EmptyGlSetError) as refusal:
            validate_batch(batch.id, MDL)
        assert refusal.value.code == "opening.empty_gl_set"


def test_the_technical_account_may_not_carry_a_gl_balance(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Otherwise its balance after posting is not zero, and the completeness test
    stops being a test."""
    with tenant_context(context):
        batch = open_batch(scene)
        add_rows(
            batch.id,
            gl=[
                GlRow(account_id=scene["counterpart"], debit=money("100.0000")),
                GlRow(account_id=scene["equity"], credit=money("100.0000")),
            ],
        )
        with pytest.raises(CounterpartInGlError) as refusal:
            validate_batch(batch.id, MDL)
        assert refusal.value.code == "opening.counterpart_in_gl"


def test_a_foreign_currency_balance_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Refused, not converted and not stored unchecked. The conversion needs a
    rounding rule (`DNB-08`, open); four numbers whose relation nothing verified
    would be unreconcilable in an append-only ledger."""
    with tenant_context(context):
        batch = open_batch(scene)
        add_rows(
            batch.id,
            gl=[
                GlRow(
                    account_id=scene["cash"],
                    debit=money("1000.0000"),
                    currency="EUR",
                    amount_currency=money("50.0000"),
                ),
                GlRow(account_id=scene["equity"], credit=money("1000.0000")),
            ],
        )
        with pytest.raises(ForeignCurrencyBalanceError) as refusal:
            validate_batch(batch.id, MDL)
        assert refusal.value.code == "opening.foreign_currency_unsupported"


def test_a_blocked_account_is_refused_by_the_engine(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The chart's answer, with the engine's code -- not a second implementation
    of "may this account receive a posting"."""
    with tenant_context(context):
        batch = open_batch(scene)
        add_rows(
            batch.id,
            gl=[
                GlRow(account_id=scene["blocked"], debit=money("100.0000")),
                GlRow(account_id=scene["equity"], credit=money("100.0000")),
            ],
        )
        with pytest.raises(AccountNotPostableError) as refusal:
            validate_batch(batch.id, MDL)
        assert refusal.value.code == "posting.account_not_postable"


def test_a_gl_row_on_an_account_that_requires_a_dimension_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """F1.1.3 reached through the opening path.

    A synthetic figure on an account whose postings must name a partner is
    exactly the case the analytical sets exist for -- so the refusal is the
    product telling the accountant to load the customer set, not a limitation.
    """
    with tenant_context(context):
        batch = open_batch(scene)
        add_rows(
            batch.id,
            gl=[
                GlRow(account_id=scene["needs_partner"], debit=money("100.0000")),
                GlRow(account_id=scene["equity"], credit=money("100.0000")),
            ],
        )
        with pytest.raises(MissingRequiredDimensionError) as refusal:
            validate_batch(batch.id, MDL)
        assert refusal.value.code == "posting.missing_required_dimension"


def test_the_same_account_decomposed_satisfies_the_dimension(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The other half of the previous test, without which it would only prove
    that the check refuses everything."""
    with tenant_context(context):
        batch = open_batch(scene)
        partner = uuid.uuid4()
        add_rows(
            batch.id,
            gl=[
                GlRow(account_id=scene["needs_partner"], debit=money("100.0000")),
                GlRow(account_id=scene["equity"], credit=money("100.0000")),
            ],
            receivables=[
                PartnerRow(
                    account_id=scene["needs_partner"],
                    partner_id=partner,
                    debit=money("100.0000"),
                )
            ],
        )
        validate_batch(batch.id, MDL)
        result = post(scene, batch)

        line = JournalLine.objects.get(
            journal_entry_id=result.journal_entry_id, account_id=scene["needs_partner"]
        )
        assert line.partner_id == partner


def test_a_batch_dated_into_a_closed_month_is_refused_at_creation(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Refused early, with the period module's own code. An accountant who typed
    five thousand rows into a batch dated into a closed month should find out
    before the last one."""
    with tenant_context(context):
        with pytest.raises(PeriodNotOpenError) as refusal:
            open_batch(scene, IN_CLOSED_MONTH)
        assert refusal.value.code == "periods.period_not_open"


# --- the freeze and the lifecycle --------------------------------------------


def test_rows_cannot_be_added_after_validation(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        batch = simple_batch(scene)
        validate_batch(batch.id, MDL)
        with pytest.raises(BatchNotDraftError) as refusal:
            add_rows(batch.id, gl=[GlRow(account_id=scene["cash"], debit=money("1.0000"))])
        assert refusal.value.code == "opening.batch_not_draft"


def test_the_database_refuses_a_row_on_a_validated_batch(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The barrier that holds when the service is bypassed.

    The 1C importer and any data migration write through the ORM or through SQL,
    not through `add_rows`; without this trigger "validated" would mean "was
    correct at some point".
    """
    with tenant_context(context):
        batch = simple_batch(scene)
        validate_batch(batch.id, MDL)
        with pytest.raises(ProgrammingError), transaction.atomic():
            OpeningBalanceGl.objects.create(
                tenant_id=batch.tenant_id,
                company_id=batch.company_id,
                batch=batch,
                account_id=scene["cash"],
                debit=money("1.0000"),
                credit=Decimal(0),
            )


def test_the_database_refuses_deleting_a_row_of_a_validated_batch(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """DELETE is granted on the line tables so a draft can be corrected; the
    trigger is what decides which delete goes through."""
    with tenant_context(context):
        batch = simple_batch(scene)
        row = OpeningBalanceGl.objects.filter(batch=batch).first()
        assert row is not None
        validate_batch(batch.id, MDL)
        with pytest.raises(ProgrammingError), transaction.atomic():
            row.delete()


def test_a_draft_row_can_still_be_deleted(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The control for the previous test: without it, the trigger could be
    refusing everything and both tests would still pass."""
    with tenant_context(context):
        batch = simple_batch(scene)
        row = OpeningBalanceGl.objects.filter(batch=batch).first()
        assert row is not None
        row.delete()
        assert OpeningBalanceGl.objects.filter(batch=batch).count() == 1


def test_reopening_a_validated_batch_unfreezes_it(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        batch = simple_batch(scene)
        validate_batch(batch.id, MDL)
        reopen_batch(batch.id)
        add_rows(batch.id, gl=[GlRow(account_id=scene["stock"], debit=money("1.0000"))])
        assert OpeningBalanceGl.objects.filter(batch=batch).count() == 3


def test_a_rejected_batch_cannot_be_validated(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        batch = simple_batch(scene)
        reject_batch(batch.id, "cifrele au venit din exercițiul greșit")
        with pytest.raises(IllegalBatchTransitionError) as refusal:
            validate_batch(batch.id, MDL)
        assert refusal.value.code == "opening.illegal_batch_transition"

        stored = OpeningBalanceBatch.objects.get(id=batch.id)
        assert stored.status == BatchStatus.REJECTED
        assert stored.rejected_reason == "cifrele au venit din exercițiul greșit"


def test_a_draft_batch_cannot_be_posted(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Posting an unchecked batch would make `validated` decorative."""
    with tenant_context(context):
        batch = simple_batch(scene)
        with pytest.raises(IllegalBatchTransitionError):
            post(scene, batch)
        assert not JournalEntry.objects.exists()


def test_the_database_refuses_editing_a_posted_batch(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """R10 reaches the batch too: it produced an entry in an append-only ledger,
    so it is corrected with a reversal and a new batch, not edited in place."""
    with tenant_context(context):
        batch = simple_batch(scene)
        validate_batch(batch.id, MDL)
        post(scene, batch)

        stored = OpeningBalanceBatch.objects.get(id=batch.id)
        stored.source = BatchSource.ONEC_IMPORT
        with pytest.raises(ProgrammingError), transaction.atomic():
            stored.save(update_fields=["source"])


# --- idempotency -------------------------------------------------------------


def test_the_same_key_twice_produces_one_entry(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        batch = simple_batch(scene)
        validate_batch(batch.id, MDL)
        first = post(scene, batch)
        second = post(scene, batch, key="opening-1")

        assert second.journal_entry_id == first.journal_entry_id
        assert second.posted_now is False
        assert JournalEntry.objects.count() == 1
        assert AccountingEvent.objects.count() == 1


def test_a_second_key_on_a_posted_batch_produces_no_second_entry(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The case the event layer alone cannot catch.

    A different idempotency key is a different event, so nothing at that level
    would object -- and the company's whole trial balance would be loaded twice.
    The batch is what answers, before the event is touched.
    """
    with tenant_context(context):
        batch = simple_batch(scene)
        validate_batch(batch.id, MDL)
        first = post(scene, batch)
        second = post(scene, batch, key="a-completely-different-key")

        assert second.journal_entry_id == first.journal_entry_id
        assert second.accounting_event_id == first.accounting_event_id
        assert second.posted_now is False
        assert JournalEntry.objects.count() == 1
        assert AccountingEvent.objects.count() == 1


def test_a_replay_consumes_no_second_document_number(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """A consumed number is a permanent gap in the register (ADR-022), so a
    service that deduplicated only the write would still leave one."""
    with tenant_context(context):
        batch = simple_batch(scene)
        validate_batch(batch.id, MDL)
        post(scene, batch)
        post(scene, batch)

        assert list(JournalEntry.objects.values_list("entry_number", flat=True)) == ["SI-2026-0001"]


# --- the start period does not move (ADR-039 section 11) ---------------------


def test_a_later_batch_at_another_date_is_refused_at_creation(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        batch = simple_batch(scene)
        validate_batch(batch.id, MDL)
        post(scene, batch)

        with pytest.raises(StartPeriodFixedError) as refusal:
            open_batch(scene, date(2026, 1, 20))
        assert refusal.value.code == "opening.start_period_fixed"


def test_a_batch_created_before_the_first_posting_cannot_post_at_another_date(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The order that gets past a check made only at creation.

    Both batches are created while nothing has posted, so creation cannot object.
    The refusal has to be at posting, and it is.
    """
    with tenant_context(context):
        second = open_batch(scene, date(2026, 1, 20))
        add_rows(
            second.id,
            gl=[
                GlRow(account_id=scene["cash"], debit=money("5.0000")),
                GlRow(account_id=scene["equity"], credit=money("5.0000")),
            ],
        )
        validate_batch(second.id, MDL)

        first = simple_batch(scene)
        validate_batch(first.id, MDL)
        post(scene, first)

        with pytest.raises(StartPeriodFixedError) as refusal:
            post(scene, second, key="opening-2")
        assert refusal.value.code == "opening.start_period_fixed"
        assert JournalEntry.objects.count() == 1


def test_the_database_refuses_a_batch_at_another_date(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The barrier the 1C importer and any data migration meet.

    Written through the ORM rather than through `create_batch`, which is exactly
    how a converter would write it.
    """
    with tenant_context(context):
        batch = simple_batch(scene)
        validate_batch(batch.id, MDL)
        post(scene, batch)

        with pytest.raises(ProgrammingError), transaction.atomic():
            OpeningBalanceBatch.objects.create(
                tenant_id=scene["tenant"],
                company_id=scene["company"],
                as_of_date=date(2026, 1, 20),
                source=BatchSource.ONEC_IMPORT,
                counterpart_account_id=scene["counterpart"],
                created_by_user_id=scene["user"],
            )


def test_a_second_batch_at_the_same_date_is_allowed(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Spec B section 8.3 keeps the correction path open: reversal and a new
    batch. What ADR-039 closes is moving the date, not loading again."""
    with tenant_context(context):
        batch = simple_batch(scene)
        validate_batch(batch.id, MDL)
        post(scene, batch)

        again = open_batch(scene, AS_OF)
        assert again.as_of_date == AS_OF
        assert again.status == BatchStatus.DRAFT


def test_another_company_of_the_same_tenant_chooses_its_own_start(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    context: TenantContext,
    scene: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> None:
    """The rule is per company, not per tenant. A holding whose second subsidiary
    joined a month later would otherwise be unable to load its books at all."""
    other = seed_company_world(
        seed,
        world["tenant_a"],
        world["user_a"],
        company_of,
        grant_company,
        idno="1002600000702",
        name="Alpha Doi",
    )
    with tenant_context(context):
        batch = simple_batch(scene)
        validate_batch(batch.id, MDL)
        post(scene, batch)

        theirs = open_batch(other, date(2026, 1, 20))
        assert theirs.as_of_date == date(2026, 1, 20)


# --- isolation ---------------------------------------------------------------


def test_tenant_b_sees_neither_the_batch_nor_its_rows(
    context: TenantContext, world: dict[str, uuid.UUID], scene: dict[str, uuid.UUID]
) -> None:
    """IZ-04: absence, not refusal. The batch, its rows and the entry it produced
    are all invisible, and "not found" is the only answer that does not leak the
    existence of another tenant's row."""
    with tenant_context(context):
        batch = simple_batch(scene)
        validate_batch(batch.id, MDL)
        result = post(scene, batch)

    intruder = TenantContext(
        tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="intruder"
    )
    with tenant_context(intruder):
        assert not OpeningBalanceBatch.objects.filter(id=batch.id).exists()
        assert not OpeningBalanceGl.objects.filter(batch_id=batch.id).exists()
        assert not JournalEntry.objects.filter(id=result.journal_entry_id).exists()
        assert not JournalLine.objects.filter(journal_entry_id=result.journal_entry_id).exists()


def test_a_batch_of_another_tenant_is_not_found(
    context: TenantContext, world: dict[str, uuid.UUID], scene: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        batch = simple_batch(scene)

    intruder = TenantContext(
        tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="intruder"
    )
    with tenant_context(intruder):
        with pytest.raises(BatchNotFoundError) as refusal:
            validate_batch(batch.id, MDL)
        assert refusal.value.code == "opening.batch_not_found"


# --- amounts, and the vocabulary ---------------------------------------------


def test_a_float_amount_is_refused(context: TenantContext, scene: dict[str, uuid.UUID]) -> None:
    """`0.1` is not a tenth in binary, and a trial balance that accepted one would
    balance by luck. Refused where the caller can still see the value it came
    from, rather than converted here."""
    with tenant_context(context):
        batch = open_batch(scene)
        with pytest.raises(OpeningBalanceError) as refusal:
            add_rows(
                batch.id,
                gl=[GlRow(account_id=scene["cash"], debit=0.1)],  # type: ignore[arg-type]
            )
        assert refusal.value.code == "opening.refused"
        assert not OpeningBalanceGl.objects.filter(batch=batch).exists()


def test_a_fifth_decimal_is_refused(context: TenantContext, scene: dict[str, uuid.UUID]) -> None:
    """`numeric(20,4)` would round it on INSERT, and which way it rounds is
    `DNB-08` -- so the value is refused, not altered."""
    with tenant_context(context):
        batch = open_batch(scene)
        with pytest.raises(OpeningBalanceError):
            add_rows(batch.id, gl=[GlRow(account_id=scene["cash"], debit=money("1.00001"))])


def test_the_type_is_registered_and_resolvable() -> None:
    """ADR-038: the module registers its own type at the import of its AppConfig,
    so the vocabulary does not depend on import order. Without this the boot check
    would see a different registry than the one that serves."""
    handler = resolve_handler(EVENT_TYPE, AS_OF, frozenset())
    assert handler.__name__ == "record_opening_lines"
    assert REGISTRY[EVENT_TYPE].payload_fields == ("batch_id", "as_of_date")
