"""An approved payroll run reaches the ledger -- `C12`, with accounts and amounts.

ADR-065 sections 7 and 8, verified through the engine rather than asserted: the
gross and the employer's contribution land on the personnel-cost account against
the payables; the withholdings move from the salary payable to the budgets; one
formula per person and component, the person on the line where the account
declares the slot. Rates are the nonsense of `test_payroll_run.py`, for the reason
given there -- what is under test is the chain, and the chain does not care.

Five claims:

1. **The entry follows the lines.** Every journal line equals a payroll line, on
   the account the role means, and the entry balances (`R11`).
2. **The person is on the line.** `employee_id` is stored where the account
   declares the slot, and the account got that declaration from the role
   catalogue, not from a fixture that knew the answer.
3. **Approving twice posts once** (`R19`): the second call is refused as not a
   draft, and posting the same fact again returns the first entry.
4. **A contract with no cost destination refuses the run, by name**, and the
   refusal rolls the approval back: the run is still a draft, no event exists.
5. **A closed month refuses the posting** (`R12`) and the approval with it.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date
from typing import Any

import pytest

from evidenta.accounting.events.models import AccountingEvent
from evidenta.accounting.ledger.models import JournalEntry, JournalLine
from evidenta.accounting.posting.services.payroll import (
    PayrollCostDestinationMissingError,
    post_payroll_run,
)
from evidenta.accounting.posting.services.reversal import post_reversal
from evidenta.accounting.slots.models import AccountRoleBinding
from evidenta.operations.payroll.models import EmploymentContract, PayrollLine, PayrollRunStatus
from evidenta.operations.payroll.services.runs import (
    PayrollRunNotDraftError,
    _fact_of,
    approve,
    create_run,
    run_in_context,
)
from evidenta.platform.api.errors import ApiError
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.isolation.payroll_ledger import seed_ledger_for_payroll
from tests.isolation.test_line_rounding import direction, source  # noqa: F401
from tests.isolation.test_payroll_run import (
    APPROVER,
    FIXTURE_AMOUNTS,
    FIXTURE_RATES,
    SOURCE_ID,
    a_contract,
    a_month,
)

pytestmark = pytest.mark.django_db(databases=["default", "migration", "refdata"])

#: One account per role the family binds. Codes are the plan's where an
#: assertion reads them; the roles come from the catalogue so the test cannot
#: bind a role the engine would not ask for.
ACCOUNT_CODES = {
    "DATORII_SALARIALE": "5311",
    "DATORII_CAS": "5331",
    "DATORII_CNAM": "5332",
    "IMPOZIT_VENIT_SALARIU": "5342",
    "CHELTUIELI_PERSONAL_ADMINISTRATIV": "7131",
    "CHELTUIELI_PERSONAL_COMERCIAL": "7121",
}

RATE_KEYS = (
    "cnas.employer_rate",
    "cnam.employee_rate",
    "income_tax.rate_individual",
    "labour.minimum_wage_monthly",
    "income_tax.exemption_personal",
)


def _rates(seed: Callable[..., None]) -> None:
    """The fixture parameters of `test_payroll_run.py`, active from 2020."""
    seed(
        "INSERT INTO fiscal_parameter_source (id, act_type, act_number, act_date,"
        " effective_from, created_at)"
        " VALUES (%s, 'test', 'X-1', '2019-12-31', '2020-01-01', now())"
        " ON CONFLICT (id) DO NOTHING",
        [SOURCE_ID],
    )
    for key in RATE_KEYS:
        value = FIXTURE_RATES.get(key, FIXTURE_AMOUNTS.get(key))
        assert value is not None, key
        seed(
            "INSERT INTO fiscal_parameter (id, parameter_key, scope, value_type, value,"
            " valid_from, margin_basis, margin_reference, status, source_id,"
            " source_confidence, provisional_reason, approved_by_user_id, approved_at,"
            " created_at, updated_at)"
            " VALUES (%s, %s, 'global', 'decimal', %s::jsonb, '2020-01-01',"
            " 'platform_convention', 'fixture — valoare fără acoperire în act',"
            " 'active', %s, 'provisional',"
            " 'fixture de test: valoare inventată, nu citită dintr-un act',"
            " %s, now(), now(), now())",
            [uuid.uuid4(), key, str(value), SOURCE_ID, APPROVER],
        )


@pytest.fixture
def payroll_world(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
    source: uuid.UUID,  # noqa: F811 -- the fiscal act fixture, imported to be found
) -> dict[str, Any]:
    """A company with an open March 2026, a numbering template, the conventions,
    the fixture rates, one account per payroll role, and every catalogue role bound
    through the real installer -- which is what declares the `employee` slot."""
    tenant = world["tenant_a"]
    company = company_of(tenant, "1002600000912", "Alpha Salarii")
    grant_company(tenant, company, world["user_a"], world["user_a"])
    direction(seed, world, "half_up")
    _rates(seed)
    accounts = seed_ledger_for_payroll(seed, tenant=tenant, company=company, user=world["user_a"])
    context = TenantContext(tenant_id=tenant, user_id=world["user_a"], request_id="payroll-posting")
    return {
        "tenant": tenant,
        "company": company,
        "user": world["user_a"],
        "context": context,
        "accounts": accounts,
        "codes": {account_id: code for code, account_id in accounts.items()},
    }


def _run(world: dict[str, Any], *, cost_destination: str = "administrative") -> Any:
    contract = a_contract(
        world, idnp="2001111111150", number="CIM-P1", cost_destination=cost_destination
    )
    a_month(world, contract)
    run = create_run(
        tenant_id=world["tenant"],
        company_id=world["company"],
        year=2026,
        month=3,
        accrual_date=date(2026, 3, 31),
    )
    assert run_in_context(run.id)["complete"] is True
    return run, contract


def _entry_lines(world: dict[str, Any], run_id: uuid.UUID) -> tuple[Any, list[Any]]:
    event = AccountingEvent.objects.get(
        source_document_type="payroll.run", source_document_id=run_id
    )
    assert event.status == "posted"
    entry = JournalEntry.objects.get(accounting_event_id=event.id)
    lines = JournalLine.objects.filter(journal_entry_id=entry.id).order_by("line_number")
    return entry, list(lines)


def test_the_entry_follows_the_lines_on_the_accounts_the_roles_mean(
    payroll_world: dict[str, Any],
) -> None:
    world = payroll_world
    with tenant_context(world["context"]):
        run, _contract = _run(world)
        register = approve(run_id=run.id, approver_user_id=world["user"])
        assert register["status"] == PayrollRunStatus.APPROVED
        assert register["posting"]["status"] == "posted"

        _entry, lines = _entry_lines(world, run.id)
        amounts = {
            line.component_key: line.amount
            for line in PayrollLine.objects.filter(run=run)
            if line.amount is not None
        }
        assert len(amounts) == 4, amounts
        gross, cas, cnam, tax = (
            amounts["salary.gross"],
            amounts["cas.employer"],
            amounts["cnam.employee"],
            amounts["income_tax.withheld"],
        )
    assert gross > 0 and cas > 0 and cnam > 0 and tax > 0

    codes = world["codes"]
    debits = {(codes[line.account_id], line.debit) for line in lines if line.debit > 0}
    credits = {(codes[line.account_id], line.credit) for line in lines if line.credit > 0}
    # ADR-065 section 8.5, row by row.
    assert debits == {("7131", gross), ("7131", cas), ("5311", cnam), ("5311", tax)}
    assert credits == {("5311", gross), ("5331", cas), ("5332", cnam), ("5342", tax)}
    assert sum(line.debit for line in lines) == sum(line.credit for line in lines)
    assert sum(line.debit for line in lines) == gross + cas + cnam + tax
    # And what is left on 5311 is the net -- the statement the payslip derives.
    on_5311 = sum(line.credit - line.debit for line in lines if codes[line.account_id] == "5311")
    assert on_5311 == gross - cnam - tax


def test_the_person_is_on_the_line_where_the_catalogue_declared_the_slot(
    payroll_world: dict[str, Any],
) -> None:
    world = payroll_world
    with tenant_context(world["context"]):
        run, contract = _run(world)
        employee_id = PayrollLine.objects.filter(run=run).values_list("employee_id", flat=True)[0]
        approve(run_id=run.id, approver_user_id=world["user"])
        _entry, lines = _entry_lines(world, run.id)
        bound = {
            row.role: row.account_id
            for row in AccountRoleBinding.objects.filter(company_id=world["company"])
        }
    codes = world["codes"]
    del contract
    for line in lines:
        code = codes[line.account_id]
        if code in ("5311", "7131"):
            assert line.employee_id == employee_id, code
        else:
            # The budgets' payables are per institution, not per person (section 8.4).
            assert line.employee_id is None, code
    # The five roles of ADR-065 section 7 are bound by the same installer as the rest.
    assert {"DATORII_SALARIALE", "DATORII_CAS", "DATORII_CNAM"} <= set(bound)


def test_approving_twice_posts_once(payroll_world: dict[str, Any]) -> None:
    world = payroll_world
    with tenant_context(world["context"]):
        run, _contract = _run(world)
        first = approve(run_id=run.id, approver_user_id=world["user"])
        with pytest.raises(PayrollRunNotDraftError):
            approve(run_id=run.id, approver_user_id=world["user"])
        # The same fact again, straight at the engine: the first entry, not a second.
        run.refresh_from_db()
        again = post_payroll_run(
            tenant_id=world["tenant"],
            company_id=world["company"],
            functional_currency="MDL",
            fact=_fact_of(run),
            actor_user_id=world["user"],
            request_id="payroll-posting-again",
            capability_snapshot={"version": 1, "on": "2026-03-31", "activated": [], "usable": []},
        )
        entry, _lines = _entry_lines(world, run.id)
        assert JournalEntry.objects.filter(company_id=world["company"]).count() == 1
    assert again.posted_now is False
    assert again.journal_entry_id == entry.id
    assert first["posting"]["accounting_event_id"] == str(again.accounting_event_id)


def test_a_contract_without_a_cost_destination_refuses_the_run_by_name(
    payroll_world: dict[str, Any], seed: Callable[..., None]
) -> None:
    world = payroll_world
    del seed
    with tenant_context(world["context"]):
        run, contract = _run(world)
        # Written before the column existed: the only way a contract has none.
        # Through the application connection -- the row is this transaction's
        # own, so a superuser statement from outside would not even see it.
        EmploymentContract.objects.filter(id=contract).update(cost_destination=None)
        with pytest.raises(PayrollCostDestinationMissingError) as refused:
            approve(run_id=run.id, approver_user_id=world["user"])
        assert "CIM-P1" in str(refused.value)
        run.refresh_from_db()
        assert run.status == PayrollRunStatus.DRAFT
        assert run.approved_at is None
        assert not AccountingEvent.objects.filter(source_document_id=run.id).exists()
        assert not JournalEntry.objects.filter(company_id=world["company"]).exists()


def test_a_closed_month_refuses_the_posting_and_the_approval_with_it(
    payroll_world: dict[str, Any], seed: Callable[..., None]
) -> None:
    world = payroll_world
    with tenant_context(world["context"]):
        run, _contract = _run(world)
    seed(
        "UPDATE period SET status = 'closed', closed_at = now() WHERE company_id = %s"
        " AND start_date = '2026-03-01'",
        [world["company"]],
    )
    with tenant_context(world["context"]):
        with pytest.raises(ApiError) as refused:
            approve(run_id=run.id, approver_user_id=world["user"])
        assert refused.value.code == "periods.period_not_open"
        run.refresh_from_db()
        assert run.status == PayrollRunStatus.DRAFT
        assert not JournalEntry.objects.filter(company_id=world["company"]).exists()


def test_an_approved_run_can_be_reversed_through_the_engine(payroll_world: dict[str, Any]) -> None:
    """`R14`: the storno of a payroll entry mirrors it and links both ways.

    The pair `payroll.run_approved_reversed` is registered beside the event, so
    the reversal service finds a treatment instead of refusing the type; the
    mirror puts every balance back -- 5311 per person included -- and names the
    entry it cancels.
    """
    world = payroll_world
    with tenant_context(world["context"]):
        run, _contract = _run(world)
        approve(run_id=run.id, approver_user_id=world["user"])
        entry, lines = _entry_lines(world, run.id)
        reversed_ = post_reversal(
            tenant_id=world["tenant"],
            company_id=world["company"],
            entry_id=entry.id,
            accounting_date=date(2026, 3, 31),
            reason="ore greșite pe pontaj",
            idempotency_key=f"payroll.run_approved_reversed:{run.id}:1",
            actor_user_id=world["user"],
            request_id="payroll-storno",
            capability_snapshot={"version": 1, "on": "2026-03-31", "activated": [], "usable": []},
        )
        mirror = JournalEntry.objects.get(id=reversed_.journal_entry_id)
        mirror_lines = list(JournalLine.objects.filter(journal_entry_id=mirror.id))
        assert mirror.reverses_entry_id == entry.id
    codes = world["codes"]
    original = sorted((codes[line.account_id], line.debit, line.credit) for line in lines)
    swapped = sorted((codes[line.account_id], line.credit, line.debit) for line in mirror_lines)
    assert original == swapped
    on_5311 = sum(
        line.credit - line.debit
        for line in [*lines, *mirror_lines]
        if codes[line.account_id] == "5311"
    )
    assert on_5311 == 0
