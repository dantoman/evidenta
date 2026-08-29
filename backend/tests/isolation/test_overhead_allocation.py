"""Allocation of indirect production costs -- C5 of ADR-036 section 11, ADR-058.

Shape and arithmetic, never treatment: that variable costs enter in full and
constant ones by normal capacity with the remainder to expenses (pct. 30), that
the split follows whatever base the fact carries (pct. 31) and adds up to the
last ban, that each product's share carries the product as a dimension on the
side whose account declares it, that the rule is selected from the registry by
date, and that an empty base is refused rather than spread. Accounts are
fixtures bound to roles; the numbers are test values.

Under the application role (T1).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from evidenta.accounting.events.models import AccountingEvent
from evidenta.accounting.ledger.models import (
    EntryParameterStamp,
    JournalEntry,
    JournalFormula,
    JournalLine,
)
from evidenta.accounting.posting.services.production import (
    EVENT_TYPE,
    HANDLER_REF,
    ROLE_BASIC,
    ROLE_INDIRECT,
    ROLE_UNABSORBED,
    AllocationBaseEmptyError,
    AllocationFact,
    AllocationPayloadError,
    ProductShare,
    post_overhead_allocation,
)
from evidenta.accounting.slots.models import AccountRoleBinding
from evidenta.fiscal.parameters.services.resolution import FiscalResolutionError
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.isolation.test_formulas import seed_account
from tests.isolation.test_ledger import seed_period
from tests.isolation.test_line_rounding import SOURCE_ID, direction, scale, source  # noqa: F401
from tests.isolation.test_manual_entry import seed_template as seed_numbering

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

MDL = "MDL"
START, END = date(2026, 1, 1), date(2026, 1, 31)
SNAPSHOT: dict[str, Any] = {"version": 1, "on": "2026-01-01", "activated": [], "usable": []}


def absorption_rule(seed: Callable[..., None], world: dict[str, uuid.UUID]) -> None:
    seed(
        "INSERT INTO fiscal_logic_version (id, logic_key, implementation_ref, version,"
        " valid_from, source_id, regression_case_set, status, approved_by_user_id,"
        " approved_at, created_at, updated_at)"
        " VALUES (%s, 'production.overhead_absorption', 'normal_capacity_v1', '1',"
        " DATE '2014-01-01', %s, 'test.absorption', 'active', %s, now(), now(), now())",
        [uuid.uuid4(), SOURCE_ID, world["user_a"]],
    )


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="c5")


@pytest.fixture
def scene(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
    context: TenantContext,
    source: uuid.UUID,  # noqa: F811 -- the fiscal act fixture, imported to be found
) -> dict[str, Any]:
    """A company, January open, numbering, the conventions, the absorption rule,
    and three fixture accounts bound to the three roles -- the basic activity's
    declaring the `item` slot, as a plan would."""
    tenant = world["tenant_a"]
    company = company_of(tenant, "1002600000904", "Alpha Producție")
    grant_company(tenant, company, world["user_a"], world["user_a"])
    seed_period(seed, tenant, company)
    seed_numbering(seed, tenant, company)
    scale(seed, world, "accounting.amount_scale", 2)
    direction(seed, world, "half_up")
    absorption_rule(seed, world)
    accounts = {
        ROLE_INDIRECT: seed_account(seed, tenant, company, "821FIX"),
        ROLE_BASIC: seed_account(seed, tenant, company, "811FIX", slots=("item",)),
        ROLE_UNABSORBED: seed_account(seed, tenant, company, "714FIX"),
    }
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
    return {"tenant": tenant, "company": company, "user": world["user_a"], "accounts": accounts}


A, B, C = uuid.UUID(int=11), uuid.UUID(int=12), uuid.UUID(int=13)


def fact(**overrides: Any) -> AllocationFact:
    base: dict[str, Any] = {
        "allocation_id": uuid.uuid4(),
        "period_start": START,
        "period_end": END,
        "variable_costs": Decimal("1000"),
        "constant_costs": Decimal("500"),
        "normal_capacity": Decimal("1000"),
        "actual_volume": Decimal("1000"),
        "base_name": "salariile de bază ale muncitorilor",
        "products": (ProductShare(A, Decimal("3")), ProductShare(B, Decimal("1"))),
    }
    base.update(overrides)
    return AllocationFact(**base)


def allocate(scene: dict[str, Any], the_fact: AllocationFact) -> Any:
    return post_overhead_allocation(
        tenant_id=scene["tenant"],
        company_id=scene["company"],
        functional_currency=MDL,
        fact=the_fact,
        actor_user_id=scene["user"],
        request_id="c5",
        capability_snapshot=SNAPSHOT,
    )


def correspondences(
    entry_id: uuid.UUID,
) -> list[tuple[uuid.UUID, uuid.UUID, Decimal, uuid.UUID | None]]:
    return [
        (f.debit_account_id, f.credit_account_id, f.amount, f.slot_1_value_id)
        for f in JournalFormula.objects.filter(journal_entry_id=entry_id).order_by("id")
    ]


def test_at_normal_capacity_everything_enters_the_cost_by_the_base(
    scene: dict[str, Any], context: TenantContext
) -> None:
    """1000 variable + 500 constant, fully absorbed, split 3:1 -> 1125 / 375; no
    expense line; each product's share carries the product on the 811 side."""
    a = scene["accounts"]
    with tenant_context(context):
        result = allocate(scene, fact())
        assert result.journal_entry_id is not None
        assert correspondences(result.journal_entry_id) == [
            (a[ROLE_BASIC], a[ROLE_INDIRECT], Decimal("1125.0000"), A),
            (a[ROLE_BASIC], a[ROLE_INDIRECT], Decimal("375.0000"), B),
        ]
        entry = JournalEntry.objects.get(pk=result.journal_entry_id)
        assert entry.rule_ref == HANDLER_REF and entry.accounting_date == END
        # The dimension lands on the debit line -- 811 declares `item` -- and not
        # on the credit line, whose account declares nothing.
        debit_lines = JournalLine.objects.filter(
            journal_entry_id=entry.id, account_id=a[ROLE_BASIC]
        )
        assert {line.item_id for line in debit_lines} == {A, B}
        credit_lines = JournalLine.objects.filter(
            journal_entry_id=entry.id, account_id=a[ROLE_INDIRECT]
        )
        assert {line.item_id for line in credit_lines} == {None}
        assert [
            s.parameter_key for s in EntryParameterStamp.objects.filter(journal_entry_id=entry.id)
        ] == ["accounting.amount_scale"]
        assert AccountingEvent.objects.get(pk=result.accounting_event_id).event_type == EVENT_TYPE


def test_below_normal_capacity_the_constant_remainder_is_an_expense(
    scene: dict[str, Any], context: TenantContext
) -> None:
    """actual 800 of normal 1000: 500 x 0.8 = 400 absorbed, 100 to 714 (pct. 30(2))."""
    a = scene["accounts"]
    with tenant_context(context):
        result = allocate(scene, fact(actual_volume=Decimal("800")))
        assert correspondences(result.journal_entry_id) == [
            (a[ROLE_BASIC], a[ROLE_INDIRECT], Decimal("1050.0000"), A),
            (a[ROLE_BASIC], a[ROLE_INDIRECT], Decimal("350.0000"), B),
            (a[ROLE_UNABSORBED], a[ROLE_INDIRECT], Decimal("100.0000"), None),
        ]


def test_variable_costs_enter_in_full_whatever_the_capacity(
    scene: dict[str, Any], context: TenantContext
) -> None:
    a = scene["accounts"]
    with tenant_context(context):
        result = allocate(scene, fact(constant_costs=Decimal("0"), actual_volume=Decimal("10")))
        assert correspondences(result.journal_entry_id) == [
            (a[ROLE_BASIC], a[ROLE_INDIRECT], Decimal("750.0000"), A),
            (a[ROLE_BASIC], a[ROLE_INDIRECT], Decimal("250.0000"), B),
        ]


def test_the_split_adds_up_to_the_last_ban(scene: dict[str, Any], context: TenantContext) -> None:
    """100 over three equal bases: 33.33, 33.33 and 33.34 -- the last takes the
    residual, and the entry balances against 821 exactly."""
    a = scene["accounts"]
    with tenant_context(context):
        result = allocate(
            scene,
            fact(
                variable_costs=Decimal("100"),
                constant_costs=Decimal("0"),
                products=(
                    ProductShare(A, Decimal("1")),
                    ProductShare(B, Decimal("1")),
                    ProductShare(C, Decimal("1")),
                ),
            ),
        )
        shares = [amount for _, _, amount, _ in correspondences(result.journal_entry_id)]
        assert shares == [Decimal("33.3300"), Decimal("33.3300"), Decimal("33.3400")]
        assert sum(shares) == Decimal("100")
        assert a  # the accounts exist; the assertion is on the arithmetic


def test_an_empty_base_is_refused_not_spread_evenly(
    scene: dict[str, Any], context: TenantContext
) -> None:
    with tenant_context(context):
        with pytest.raises(AllocationBaseEmptyError):
            allocate(
                scene, fact(products=(ProductShare(A, Decimal("0")), ProductShare(B, Decimal("0"))))
            )
        with pytest.raises(AllocationPayloadError):
            allocate(scene, fact(normal_capacity=Decimal("0")))
        with pytest.raises(AllocationPayloadError):
            allocate(scene, fact(base_name="  "))
        # Refused before any event exists.
        assert not AccountingEvent.objects.filter(event_type=EVENT_TYPE).exists()


def test_nothing_to_allocate_records_the_event_and_no_entry(
    scene: dict[str, Any], context: TenantContext
) -> None:
    with tenant_context(context):
        result = allocate(scene, fact(variable_costs=Decimal("0"), constant_costs=Decimal("0")))
        assert result.journal_entry_id is None
        assert AccountingEvent.objects.get(pk=result.accounting_event_id).status == "posted"


def test_the_same_allocation_twice_posts_once(
    scene: dict[str, Any], context: TenantContext
) -> None:
    the_fact = fact(allocation_id=uuid.UUID(int=99))
    with tenant_context(context):
        first = allocate(scene, the_fact)
        second = allocate(scene, the_fact)
        assert first.journal_entry_id == second.journal_entry_id
        assert first.posted_now and not second.posted_now


def test_without_a_registered_rule_nothing_is_allocated(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
    context: TenantContext,
    source: uuid.UUID,  # noqa: F811
) -> None:
    """The formula is versioned logic (R17): with no row in the registry there is
    no rule for the period, and the refusal is the fiscal registry's."""
    tenant = world["tenant_a"]
    company = company_of(tenant, "1002600000905", "Alpha Fără Regulă")
    grant_company(tenant, company, world["user_a"], world["user_a"])
    seed_period(seed, tenant, company)
    scale(seed, world, "accounting.amount_scale", 2)
    direction(seed, world, "half_up")
    scene = {"tenant": tenant, "company": company, "user": world["user_a"]}
    with tenant_context(context), pytest.raises(FiscalResolutionError):
        allocate(scene, fact())
