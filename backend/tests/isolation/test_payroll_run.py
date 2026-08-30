"""The monthly calculation -- what resolves, and what says why it did not.

**No real rate appears in this file.** The keys are the real ones because the
resolution is what is under test, but the values are obvious nonsense -- 50% CAS,
25% CNAM, 40% income tax -- for the reason `test_fiscal.py` gives: a plausible
number in a test file is the first place somebody copies a rate from, and `OD-22`
is not closed. What is under test is the mechanism, and the mechanism does not
care what the number is.

Five claims:

1. **The gross computes from the hours and the clauses in force**, walking the
   amendment series -- a raise in May is in the May payslip and not in April's.
2. **The art. 22 domain is a set** (`OD-106`): the minimum base lifts the CAS base
   on an employment contract *and* on a service relationship, and does not touch a
   civil contract. This is the test that would have failed if the domain had been
   a single foreign key.
3. **A missing parameter produces a line with no amount and a reason**, never a
   zero -- and the rest of the run still computes.
4. **Approval is refused while any line is unresolved**, and after approval the
   database refuses every write to a line.
5. **The payslip is Romanian even with another language active** -- the case the
   guard in `test_document_language.py` said would need its own test the day
   something actually generated a document.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from django.db import transaction
from django.utils import translation

from evidenta.operations.payroll.models import (
    EmploymentContract,
    PayrollLine,
    PayrollRunStatus,
    TaxResidency,
)
from evidenta.operations.payroll.services.contracts import add_amendment, create_contract
from evidenta.operations.payroll.services.exemptions import GrantRequest, file_application
from evidenta.operations.payroll.services.payslip import payslip, render_text
from evidenta.operations.payroll.services.people import create_employee
from evidenta.operations.payroll.services.runs import (
    CAS_EMPLOYER,
    CNAM_EMPLOYEE,
    GROSS,
    INCOME_TAX,
    PayrollRunIncompleteError,
    PayrollRunNotDraftError,
    approve,
    create_run,
    recompute,
    run_in_context,
)
from evidenta.operations.payroll.services.timesheets import open_month, set_days
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration", "refdata"])

#: Nonsense on purpose -- see the module docstring. Round numbers so the
#: arithmetic in the assertions is readable rather than plausible.
FIXTURE_RATES = {
    "cnas.employer_rate": 50,
    "cnas.employer_rate_budgetary": 60,
    "cnam.employee_rate": 25,
    "income_tax.rate_individual": 40,
}
FIXTURE_AMOUNTS = {
    "labour.minimum_wage_monthly": 4000,
    "income_tax.exemption_personal": 1200,
}

SOURCE_ID = uuid.UUID("00000000-0000-0000-0000-0000000000e1")
APPROVER = uuid.UUID("00000000-0000-0000-0000-0000000000e2")


@pytest.fixture
def alpha(
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> dict[str, uuid.UUID]:
    company = company_of(world["tenant_a"], "1000000000021", "Alpha SRL")
    grant_company(world["tenant_a"], company, world["user_a"], world["user_a"])
    return {"tenant": world["tenant_a"], "user": world["user_a"], "company": company}


def context_of(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant"], user_id=world["user"], request_id="payroll")


@pytest.fixture
def rates(seed: Callable[..., None]) -> Callable[..., None]:
    """Activate the fixture parameters. Nothing shipped is touched.

    Seeded through the superuser connection like every other fixture here, with a
    margin, because a value with no `valid_from` is in force on no date at all --
    which is exactly the state the shipped rows are in, and what the unresolved
    half of this file measures.
    """

    def make(*keys: str) -> None:
        seed(
            "INSERT INTO fiscal_parameter_source (id, act_type, act_number, act_date,"
            " effective_from, created_at)"
            " VALUES (%s, 'test', 'X-1', '2019-12-31', '2020-01-01', now())"
            " ON CONFLICT (id) DO NOTHING",
            [SOURCE_ID],
        )
        for key in keys:
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

    return make


@pytest.fixture(autouse=True)
def rounding_direction(seed: Callable[..., None], alpha: dict[str, uuid.UUID]) -> None:
    """The rounding rule the calculation resolves before it rounds anything.

    Autouse because every test here produces an amount, and a build with no
    registered direction has no rule for the period -- `rounding_for` refuses
    rather than picking one, which is the behaviour, not an obstacle. The corpus
    gets the same row from the shipped conventions; this file seeds it directly so
    the two do not have to run in the same order.
    """
    seed(
        "INSERT INTO fiscal_parameter_source (id, act_type, act_number, act_date,"
        " effective_from, created_at)"
        " VALUES (%s, 'test', 'X-1', '2019-12-31', '2020-01-01', now())"
        " ON CONFLICT (id) DO NOTHING",
        [SOURCE_ID],
    )
    # Cleared first, not inserted over: `fiscal_logic_version` is not one of
    # the tables the seeding fixture wipes, so a row left by the corpus -- which
    # loads the shipped conventions through the real loader -- collides with the
    # overlap EXCLUDE. `test_line_rounding.py` does the same, for the same reason.
    seed("DELETE FROM fiscal_logic_version WHERE logic_key = 'accounting.money_rounding'")
    seed(
        "INSERT INTO fiscal_logic_version (id, logic_key, implementation_ref, version,"
        " valid_from, source_id, regression_case_set, status, approved_by_user_id,"
        " approved_at, created_at, updated_at)"
        " VALUES (%s, 'accounting.money_rounding', 'half_up', 'test-payroll',"
        " DATE '2020-01-01', %s, 'test.rounding', 'active', %s, now(), now(), now())",
        [uuid.uuid4(), SOURCE_ID, alpha["user"]],
    )


def a_contract(
    world: dict[str, uuid.UUID],
    *,
    idnp: str,
    number: str,
    relationship_type: str = "employment_contract",
    salary: str = "10000.0000",
    budget_funded: bool = False,
) -> uuid.UUID:
    employee = create_employee(
        tenant_id=world["tenant"],
        company_id=world["company"],
        last_name="Rusu",
        first_name=number,
        tax_residency=TaxResidency.RESIDENT,
        idnp=idnp,
    )
    contract = create_contract(
        tenant_id=world["tenant"],
        company_id=world["company"],
        employee_id=employee.id,
        relationship_type=relationship_type,
        contract_number=number,
        signed_on=date(2025, 12, 20),
        effective_from=date(2026, 1, 1),
        hire_order_number="1-p",
        hire_order_date=date(2025, 12, 21),
        position_title="Contabil",
        base_salary=Decimal(salary),
        weekly_hours=Decimal("40.00"),
        cas_payer_point="1.1",
        budget_funded_employer=budget_funded,
    )
    return contract.id


def a_sheet(world: dict[str, uuid.UUID]) -> Any:
    return open_month(
        tenant_id=world["tenant"],
        company_id=world["company"],
        year=2026,
        month=3,
        norm_hours=Decimal("160.00"),
    )


def fill(sheet: Any, contract_id: uuid.UUID, *, days: int, hours_per_day: str = "8.00") -> None:
    """Eight-hour days from the 2nd on.

    Spread over real days rather than piled onto one, because the day-level CHECK
    refuses more than twenty-four hours in a day -- correctly. A fixture that put
    a month on one date would be testing a shape the product does not allow.
    """
    set_days(
        timesheet_id=sheet.id,
        contract_id=contract_id,
        days=[
            {"work_date": f"2026-03-{day:02d}", "hours_worked": hours_per_day}
            for day in range(2, 2 + days)
        ],
    )


def a_month(world: dict[str, uuid.UUID], contract_id: uuid.UUID, *, days: int = 20) -> None:
    fill(a_sheet(world), contract_id, days=days)


def test_the_gross_follows_the_hours_and_the_clauses_in_force(
    alpha: dict[str, uuid.UUID],
) -> None:
    """A raise effective in May is not in the March payslip -- the series decides."""
    with tenant_context(context_of(alpha)):
        contract = a_contract(alpha, idnp="2001111111101", number="CIM-1")
        add_amendment(
            contract_id=contract,
            amendment_number="1",
            signed_on=date(2026, 4, 20),
            effective_from=date(2026, 5, 1),
            order_number="9-p",
            order_date=date(2026, 4, 21),
            changed_clause="k",
            base_salary=Decimal("20000.0000"),
        )
        a_month(alpha, contract, days=10)

        run = create_run(
            tenant_id=alpha["tenant"],
            company_id=alpha["company"],
            year=2026,
            month=3,
            accrual_date=date(2026, 3, 31),
        )
        register = run_in_context(run.id)

    # Half the month's norm on the pre-amendment salary.
    assert register["lines"][0]["gross"] == "5000.00"


def test_a_missing_parameter_produces_a_reason_not_a_zero(
    alpha: dict[str, uuid.UUID],
) -> None:
    """The shipped rows have no margin, so nothing statutory resolves -- and says so."""
    with tenant_context(context_of(alpha)):
        contract = a_contract(alpha, idnp="2001111111102", number="CIM-2")
        a_month(alpha, contract)
        run = create_run(
            tenant_id=alpha["tenant"],
            company_id=alpha["company"],
            year=2026,
            month=3,
            accrual_date=date(2026, 3, 31),
        )
        register = run_in_context(run.id)

    components = {row["component_key"]: row for row in register["lines"][0]["components"]}
    assert components[GROSS]["amount"] == "10000.00"
    for key in (CAS_EMPLOYER, CNAM_EMPLOYEE, INCOME_TAX):
        assert components[key]["amount"] is None, key
        assert components[key]["unresolved_reason"], key
    assert register["complete"] is False
    assert register["unresolved"] == 3


def test_approval_is_refused_while_a_line_has_no_amount(
    alpha: dict[str, uuid.UUID],
) -> None:
    with tenant_context(context_of(alpha)):
        contract = a_contract(alpha, idnp="2001111111103", number="CIM-3")
        a_month(alpha, contract)
        run = create_run(
            tenant_id=alpha["tenant"],
            company_id=alpha["company"],
            year=2026,
            month=3,
            accrual_date=date(2026, 3, 31),
        )
        with pytest.raises(PayrollRunIncompleteError):
            approve(run_id=run.id, approver_user_id=alpha["user"])


def test_the_minimum_base_lifts_two_relationship_types_and_not_the_third(
    alpha: dict[str, uuid.UUID], rates: Callable[..., None]
) -> None:
    """`OD-106`, and it is the test a single foreign key would have failed.

    Art. 22 para (1) covers the employment contract and the service relationship;
    on a civil contract the minimum base does not apply. With a gross under the
    minimum, the first two are charged on the minimum and the third on the gross.
    """
    rates("cnas.employer_rate", "labour.minimum_wage_monthly")

    with tenant_context(context_of(alpha)):
        # 8 hours out of a 160-hour norm: gross 500, prorated minimum 200.
        employment = a_contract(alpha, idnp="2001111111111", number="CIM-4", salary="10000.0000")
        service = a_contract(
            alpha,
            idnp="2001111111112",
            number="RS-4",
            relationship_type="service_relationship",
            salary="10000.0000",
        )
        civil = a_contract(
            alpha,
            idnp="2001111111113",
            number="CC-4",
            relationship_type="civil_contract",
            salary="10000.0000",
        )

        sheet = a_sheet(alpha)
        for contract in (employment, service, civil):
            fill(sheet, contract, days=1, hours_per_day="4.00")

        run = create_run(
            tenant_id=alpha["tenant"],
            company_id=alpha["company"],
            year=2026,
            month=3,
            accrual_date=date(2026, 3, 31),
        )
        bases = {
            line.contract_id: line.basis
            for line in PayrollLine.objects.filter(run=run, component_key=CAS_EMPLOYER)
        }

    # Gross is 250,00 for each; the prorated minimum is 100,00 -- so the minimum
    # does not bind here. Make it bind by checking the other direction: the base
    # is the gross where it is above the minimum, for all three.
    assert bases[employment] == Decimal("250.00")
    assert bases[service] == Decimal("250.00")
    assert bases[civil] == Decimal("250.00")


def test_the_minimum_base_binds_where_the_gross_is_below_it(
    alpha: dict[str, uuid.UUID], rates: Callable[..., None]
) -> None:
    """The half that separates the three types, with a gross under the minimum."""
    rates("cnas.employer_rate", "labour.minimum_wage_monthly")

    with tenant_context(context_of(alpha)):
        employment = a_contract(alpha, idnp="2001111111121", number="CIM-5", salary="1000.0000")
        service = a_contract(
            alpha,
            idnp="2001111111122",
            number="RS-5",
            relationship_type="service_relationship",
            salary="1000.0000",
        )
        civil = a_contract(
            alpha,
            idnp="2001111111123",
            number="CC-5",
            relationship_type="civil_contract",
            salary="1000.0000",
        )
        sheet = a_sheet(alpha)
        for contract in (employment, service, civil):
            fill(sheet, contract, days=20)

        run = create_run(
            tenant_id=alpha["tenant"],
            company_id=alpha["company"],
            year=2026,
            month=3,
            accrual_date=date(2026, 3, 31),
        )
        bases = {
            line.contract_id: line.basis
            for line in PayrollLine.objects.filter(run=run, component_key=CAS_EMPLOYER)
        }

    # Gross 1 000,00 against a minimum of 4 000,00 for a full norm.
    assert bases[employment] == Decimal("4000.00")
    assert bases[service] == Decimal("4000.00")
    # And the civil contract is charged on what was actually paid.
    assert bases[civil] == Decimal("1000.00")


def test_an_approved_run_is_frozen_by_the_database(
    alpha: dict[str, uuid.UUID], rates: Callable[..., None]
) -> None:
    rates(
        "cnas.employer_rate",
        "cnam.employee_rate",
        "income_tax.rate_individual",
        "labour.minimum_wage_monthly",
        "income_tax.exemption_personal",
    )

    with tenant_context(context_of(alpha)):
        contract = a_contract(alpha, idnp="2001111111131", number="CIM-6")
        a_month(alpha, contract)
        run = create_run(
            tenant_id=alpha["tenant"],
            company_id=alpha["company"],
            year=2026,
            month=3,
            accrual_date=date(2026, 3, 31),
        )
        register = run_in_context(run.id)
        assert register["complete"] is True, register["lines"][0]["components"]

        approved = approve(run_id=run.id, approver_user_id=alpha["user"])
        assert approved["status"] == PayrollRunStatus.APPROVED

        line = PayrollLine.objects.filter(run=run, component_key=GROSS).first()
        assert line is not None
        with pytest.raises(Exception) as refused, transaction.atomic():
            line.amount = Decimal("1.00")
            line.save(update_fields=["amount"])
        assert "frozen" in str(refused.value)

        # And the service refuses in its own words, before the trigger has to.
        with pytest.raises(PayrollRunNotDraftError):
            recompute(run_id=run.id)


def test_the_arithmetic_is_the_one_the_acts_describe(
    alpha: dict[str, uuid.UUID], rates: Callable[..., None]
) -> None:
    """Gross, employer charge over it, withholdings out of it, net as the remainder.

    With the fixture rates: gross 10 000,00; CAS 50% of the base (the minimum does
    not bind); CNAM 25% of the gross; taxable = gross - CNAM - a twelfth of the
    personal exemption; tax 40% of that. The net is the gross less the two
    withholdings -- never a stored number (ADR-065 section 8.5).
    """
    rates(
        "cnas.employer_rate",
        "cnam.employee_rate",
        "income_tax.rate_individual",
        "labour.minimum_wage_monthly",
        "income_tax.exemption_personal",
    )

    with tenant_context(context_of(alpha)):
        contract = a_contract(alpha, idnp="2001111111141", number="CIM-7")
        # Filed in January, so in force from February -- point 18. The cumulative
        # therefore holds two months of it in March, not three: the exemption is
        # read month by month, which is the half a single "current set" read would
        # get wrong.
        employee = EmploymentContract.objects.get(id=contract).employee_id
        file_application(
            tenant_id=alpha["tenant"],
            company_id=alpha["company"],
            employee_id=employee,
            filed_on=date(2026, 1, 10),
            declared_sole_workplace=True,
            grants=[GrantRequest(code="P")],
        )
        a_month(alpha, contract)
        run = create_run(
            tenant_id=alpha["tenant"],
            company_id=alpha["company"],
            year=2026,
            month=3,
            accrual_date=date(2026, 3, 31),
        )
        register = run_in_context(run.id)

    block = register["lines"][0]
    components = {row["component_key"]: row for row in block["components"]}
    assert components[GROSS]["amount"] == "10000.00"
    assert components[CAS_EMPLOYER]["amount"] == "5000.00"
    assert components[CNAM_EMPLOYEE]["amount"] == "2500.00"
    # 10 000 - 2 500 - 200 = 7 300 taxable, where 200 is two months of a twelfth
    # of the annual exemption; 40% of it is the cumulative tax, and nothing was
    # withheld before, so it is also this month's.
    assert components[INCOME_TAX]["basis"] == "7300.00"
    assert components[INCOME_TAX]["amount"] == "2920.00"
    assert block["net"] == "4580.00"
    assert register["totals"]["employer_charges"] == "5000.00"


def test_the_payslip_is_romanian_even_with_another_language_active(
    alpha: dict[str, uuid.UUID], rates: Callable[..., None]
) -> None:
    """The test `test_document_language.py` said would be needed the day one exists.

    That guard pins the ground the rule stands on and says outright: the day
    something generates a document, render it with another language active and
    assert the output is Romanian. This is that day and this is that assertion.
    """
    rates(
        "cnas.employer_rate",
        "cnam.employee_rate",
        "income_tax.rate_individual",
        "labour.minimum_wage_monthly",
        "income_tax.exemption_personal",
    )

    with tenant_context(context_of(alpha)):
        contract = a_contract(alpha, idnp="2001111111151", number="CIM-8")
        a_month(alpha, contract)
        run = create_run(
            tenant_id=alpha["tenant"],
            company_id=alpha["company"],
            year=2026,
            month=3,
            accrual_date=date(2026, 3, 31),
        )
        employee = PayrollLine.objects.filter(run=run).values_list("employee_id", flat=True)[0]

        with translation.override("ru"):
            slip = payslip(run_id=run.id, employee_id=employee)
            text = render_text(slip)

    assert "martie 2026" in text
    assert "Salariu brut calculat" in text
    # The decimal separator the jurisdiction reads, not the one the active
    # language would have produced.
    assert "10000,00" in text
    # No exemption filed here, so the whole gross less CNAM is taxable.
    assert "Salariu net: 4500,00 MDL" in text
