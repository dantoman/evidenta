"""People, contracts, amendments and the timesheet -- the general regime.

Under the application role throughout (`T1`), so every read goes through the
policies a request goes through.

What is being proved, and only the first is about tenancy:

1. **A company sees its own people and nobody else's.** The employer is the
   company, so the boundary is the company, not the tenant.
2. **The series answers, the column cannot** (ADR-067). "Which clause was in
   force in March" is read by walking the amendments; the contract row still
   holds what was signed, and both facts survive.
3. **The domain is a foreign key** (ADR-071). A relationship type that does not
   exist never reaches the table -- and the third value, the service
   relationship under an administrative act, is a first-class one.
4. **A termination without an order is refused**, by the service and by the
   database. The IRM19 deadline runs from the order's date, so a termination
   with nothing behind it is one that cannot be reported.
5. **A closed month is frozen in the database**, not in a service.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError, connection, transaction

from evidenta.operations.payroll.models import (
    Employee,
    EmploymentContract,
    TaxResidency,
    TimesheetDay,
)
from evidenta.operations.payroll.services.contracts import (
    ContractAlreadyEndedError,
    ContractMalformedError,
    add_amendment,
    clauses_in_force_on,
    contracts_of,
    create_contract,
    end_contract,
)
from evidenta.operations.payroll.services.people import (
    EmployeeDuplicateError,
    EmployeeMalformedError,
    create_employee,
    employees_of,
)
from evidenta.operations.payroll.services.timesheets import (
    TimesheetClosedError,
    TimesheetMalformedError,
    close_month,
    month_in_context,
    open_month,
    set_days,
)
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])


@pytest.fixture
def alpha(
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> dict[str, uuid.UUID]:
    company = company_of(world["tenant_a"], "1000000000001", "Alpha SRL")
    grant_company(world["tenant_a"], company, world["user_a"], world["user_a"])
    return {"tenant": world["tenant_a"], "user": world["user_a"], "company": company}


@pytest.fixture
def beta(
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> dict[str, uuid.UUID]:
    company = company_of(world["tenant_b"], "1000000000002", "Beta SRL")
    grant_company(world["tenant_b"], company, world["user_b"], world["user_b"])
    return {"tenant": world["tenant_b"], "user": world["user_b"], "company": company}


def context_of(world: dict[str, uuid.UUID], label: str) -> TenantContext:
    return TenantContext(tenant_id=world["tenant"], user_id=world["user"], request_id=label)


def a_person(world: dict[str, uuid.UUID], *, idnp: str = "2001234567890") -> Employee:
    return create_employee(
        tenant_id=world["tenant"],
        company_id=world["company"],
        last_name="Rusu",
        first_name="Ion",
        tax_residency=TaxResidency.RESIDENT,
        idnp=idnp,
    )


def a_contract(
    world: dict[str, uuid.UUID],
    employee: Employee,
    *,
    number: str = "CIM-001",
    relationship_type: str = "employment_contract",
    salary: str = "9000.0000",
) -> EmploymentContract:
    return create_contract(
        tenant_id=world["tenant"],
        company_id=world["company"],
        employee_id=employee.id,
        relationship_type=relationship_type,
        contract_number=number,
        signed_on=date(2026, 1, 5),
        effective_from=date(2026, 1, 8),
        hire_order_number="12-p",
        hire_order_date=date(2026, 1, 6),
        position_title="Contabil",
        base_salary=Decimal(salary),
        weekly_hours=Decimal("40.00"),
        cas_payer_point="1.1",
    )


def test_a_company_sees_its_own_people_and_no_others(
    alpha: dict[str, uuid.UUID], beta: dict[str, uuid.UUID]
) -> None:
    """The boundary is the company, because the legal employer is."""
    with tenant_context(context_of(alpha, "alpha")):
        a_person(alpha, idnp="2001234567890")
        mine = employees_of(alpha["company"])

    with tenant_context(context_of(beta, "beta")):
        a_person(beta, idnp="2009876543210")
        theirs = employees_of(beta["company"])
        # Asking for the other company's list from inside this context returns
        # nothing -- the policy, not a filter in the query.
        intruding = employees_of(alpha["company"])

    assert [row["idnp"] for row in mine] == ["2001234567890"]
    assert [row["idnp"] for row in theirs] == ["2009876543210"]
    assert intruding == []


def test_a_person_needs_exactly_one_identity(alpha: dict[str, uuid.UUID]) -> None:
    """The row the exception is made for is the row that would have no key at all."""
    with tenant_context(context_of(alpha, "alpha")):
        with pytest.raises(EmployeeMalformedError):
            create_employee(
                tenant_id=alpha["tenant"],
                company_id=alpha["company"],
                last_name="Fără",
                first_name="Identitate",
                tax_residency=TaxResidency.NON_RESIDENT,
            )

        with pytest.raises(EmployeeMalformedError):
            create_employee(
                tenant_id=alpha["tenant"],
                company_id=alpha["company"],
                last_name="Amândouă",
                first_name="Deodată",
                tax_residency=TaxResidency.RESIDENT,
                idnp="2001111111111",
                identity_document_type="passport",
                identity_document_number="AB0001",
            )

        # A non-resident with a document is fine, and is the case the exception
        # exists for.
        person = create_employee(
            tenant_id=alpha["tenant"],
            company_id=alpha["company"],
            last_name="Ionescu",
            first_name="Radu",
            tax_residency=TaxResidency.NON_RESIDENT,
            identity_document_type="passport",
            identity_document_number="RO123456",
        )
        assert person.idnp is None


def test_the_same_person_cannot_be_entered_twice(alpha: dict[str, uuid.UUID]) -> None:
    """Two rows for one person split the withholdings before anybody notices."""
    with tenant_context(context_of(alpha, "alpha")):
        a_person(alpha)
        with pytest.raises(EmployeeDuplicateError):
            a_person(alpha)


def test_a_relationship_type_that_does_not_exist_is_refused_with_a_code(
    alpha: dict[str, uuid.UUID],
) -> None:
    """ADR-071 section 3, at the service: `orice_bază_CAS` never gets that far."""
    with tenant_context(context_of(alpha, "alpha")):
        person = a_person(alpha)
        with pytest.raises(ContractMalformedError):
            a_contract(alpha, person, relationship_type="orice_bază_CAS")


def test_a_relationship_type_that_does_not_exist_never_reaches_the_table(
    alpha: dict[str, uuid.UUID],
) -> None:
    """The structural half, and it needs `SET CONSTRAINTS ALL IMMEDIATE` to be seen.

    Django declares foreign keys `DEFERRABLE INITIALLY DEFERRED`, so inside a test
    -- which never commits -- an unknown type would sail through and the assertion
    would prove nothing. Forcing the constraint immediate is what makes this a
    measurement of the key rather than of the service check above it.
    """
    with tenant_context(context_of(alpha, "alpha")):
        person = a_person(alpha)
        with pytest.raises(IntegrityError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            EmploymentContract.objects.create(
                tenant_id=alpha["tenant"],
                company_id=alpha["company"],
                employee_id=person.id,
                relationship_type_id="orice_bază_CAS",
                contract_number="CIM-999",
                signed_on=date(2026, 1, 5),
                effective_from=date(2026, 1, 8),
                hire_order_number="12-p",
                hire_order_date=date(2026, 1, 6),
                position_title="Contabil",
                base_salary=Decimal("9000.0000"),
                weekly_hours=Decimal("40.00"),
                cas_payer_point="1.1",
            )


def test_the_service_relationship_is_a_first_class_type(
    alpha: dict[str, uuid.UUID],
) -> None:
    """The third value, the one a two-value model would have pushed elsewhere.

    A public servant appointed by administrative act is not employed under a
    contract and *is* a salariat for art. 22. Recorded as `civil_contract`, the
    minimum-base invariant would not apply and the contribution would come out
    below the minimum -- balanced, silent, and wrong.
    """
    with tenant_context(context_of(alpha, "alpha")):
        person = a_person(alpha)
        contract = a_contract(
            alpha, person, relationship_type="service_relationship", number="RS-001"
        )
        assert contract.relationship_type_id == "service_relationship"


def test_a_changed_clause_produces_an_amendment_and_leaves_the_contract_readable(
    alpha: dict[str, uuid.UUID],
) -> None:
    """ADR-067: the contract is the head of a series, not a state.

    The signed salary is still 9000 after the raise. What was in force in June is
    read by walking the amendments -- and the answer says which amendment set it,
    because "9000 in March" is not defensible without "set by which document".
    """
    with tenant_context(context_of(alpha, "alpha")):
        person = a_person(alpha)
        contract = a_contract(alpha, person)

        add_amendment(
            contract_id=contract.id,
            amendment_number="1",
            signed_on=date(2026, 4, 28),
            effective_from=date(2026, 5, 1),
            order_number="45-p",
            order_date=date(2026, 4, 29),
            changed_clause="k",
            base_salary=Decimal("11000.0000"),
        )
        add_amendment(
            contract_id=contract.id,
            amendment_number="2",
            signed_on=date(2026, 8, 20),
            effective_from=date(2026, 9, 1),
            order_number="88-p",
            order_date=date(2026, 8, 21),
            changed_clause="d",
            position_title="Contabil-șef",
        )

        march = clauses_in_force_on(contract.id, date(2026, 3, 31))
        june = clauses_in_force_on(contract.id, date(2026, 6, 15))
        october = clauses_in_force_on(contract.id, date(2026, 10, 1))

        contract.refresh_from_db()

    assert march.base_salary == Decimal("9000.0000")
    assert march.set_by["base_salary"] == "CIM-001"
    assert june.base_salary == Decimal("11000.0000")
    assert june.set_by["base_salary"] == "1"
    assert june.position_title == "Contabil"
    assert october.position_title == "Contabil-șef"
    assert october.base_salary == Decimal("11000.0000")

    # The head of the series still says what was signed.
    assert contract.base_salary == Decimal("9000.0000")
    assert contract.position_title == "Contabil"


def test_an_amendment_names_the_clause_it_changes(alpha: dict[str, uuid.UUID]) -> None:
    """Art. 49 has nineteen clauses; three are columns here.

    Without the letter, an amendment to one of the other sixteen leaves no trace
    at all -- which is worse than not modelling it.
    """
    with tenant_context(context_of(alpha, "alpha")):
        person = a_person(alpha)
        contract = a_contract(alpha, person)
        with pytest.raises(ContractMalformedError):
            add_amendment(
                contract_id=contract.id,
                amendment_number="1",
                signed_on=date(2026, 4, 28),
                effective_from=date(2026, 5, 1),
                order_number="45-p",
                order_date=date(2026, 4, 29),
                changed_clause="  ",
            )


def test_an_ended_contract_leaves_the_default_list_and_keeps_its_row(
    alpha: dict[str, uuid.UUID],
) -> None:
    with tenant_context(context_of(alpha, "alpha")):
        person = a_person(alpha)
        contract = a_contract(alpha, person)

        end_contract(
            contract_id=contract.id,
            ended_on=date(2026, 6, 30),
            order_number="70-p",
            order_date=date(2026, 6, 25),
        )

        assert contracts_of(alpha["company"]) == []
        still_there = contracts_of(alpha["company"], include_ended=True)
        assert [row["contract_number"] for row in still_there] == ["CIM-001"]
        assert still_there[0]["termination_order_number"] == "70-p"

        with pytest.raises(ContractAlreadyEndedError):
            end_contract(
                contract_id=contract.id,
                ended_on=date(2026, 7, 31),
                order_number="80-p",
                order_date=date(2026, 7, 30),
            )


def test_an_end_date_without_an_order_is_refused_by_the_database(
    alpha: dict[str, uuid.UUID],
) -> None:
    """The service refuses it; this proves the database does too.

    A rule that lives only in a service is a rule a bulk update walks past, and
    an IRM19 line whose deadline runs from nothing cannot be filed.
    """
    with tenant_context(context_of(alpha, "alpha")):
        person = a_person(alpha)
        contract = a_contract(alpha, person)

        with pytest.raises(IntegrityError), transaction.atomic():
            EmploymentContract.objects.filter(id=contract.id).update(ended_on=date(2026, 6, 30))


def test_the_timesheet_totals_come_from_the_server(alpha: dict[str, uuid.UUID]) -> None:
    """`C19`. A total computed in the client can disagree with the register."""
    with tenant_context(context_of(alpha, "alpha")):
        person = a_person(alpha)
        contract = a_contract(alpha, person)
        sheet = open_month(
            tenant_id=alpha["tenant"],
            company_id=alpha["company"],
            year=2026,
            month=3,
            norm_hours=Decimal("168.00"),
        )
        month = set_days(
            timesheet_id=sheet.id,
            contract_id=contract.id,
            days=[
                {"work_date": "2026-03-02", "hours_worked": "8.00"},
                {"work_date": "2026-03-03", "hours_worked": "8.00", "night_hours": "2.00"},
                {"work_date": "2026-03-04", "hours_worked": "6.50"},
            ],
        )

    line = next(row for row in month["lines"] if row["contract_id"] == str(contract.id))
    assert line["hours_worked"] == "22.50"
    assert line["night_hours"] == "2.00"
    assert line["days_present"] == 3


def test_a_day_outside_the_month_is_refused(alpha: dict[str, uuid.UUID]) -> None:
    """Otherwise a day of March lands in the February sheet and neither total is right."""
    with tenant_context(context_of(alpha, "alpha")):
        person = a_person(alpha)
        contract = a_contract(alpha, person)
        sheet = open_month(
            tenant_id=alpha["tenant"],
            company_id=alpha["company"],
            year=2026,
            month=2,
            norm_hours=Decimal("160.00"),
        )
        with pytest.raises(TimesheetMalformedError):
            set_days(
                timesheet_id=sheet.id,
                contract_id=contract.id,
                days=[{"work_date": "2026-03-02", "hours_worked": "8.00"}],
            )


def test_night_hours_are_part_of_the_day_not_added_to_it(
    alpha: dict[str, uuid.UUID],
) -> None:
    with tenant_context(context_of(alpha, "alpha")):
        person = a_person(alpha)
        contract = a_contract(alpha, person)
        sheet = open_month(
            tenant_id=alpha["tenant"],
            company_id=alpha["company"],
            year=2026,
            month=3,
            norm_hours=Decimal("168.00"),
        )
        with pytest.raises(TimesheetMalformedError):
            set_days(
                timesheet_id=sheet.id,
                contract_id=contract.id,
                days=[
                    {
                        "work_date": "2026-03-02",
                        "hours_worked": "8.00",
                        "night_hours": "9.00",
                    }
                ],
            )


def test_a_closed_month_is_frozen_by_the_database(alpha: dict[str, uuid.UUID]) -> None:
    """The service refuses it with a code; the trigger refuses it at all.

    A day edited after the month closed changes a result already reported. That
    is not `R10` -- a timesheet is not a ledger -- but it is the same shape, and
    cheaper to impose in the database than to check in every caller.
    """
    with tenant_context(context_of(alpha, "alpha")):
        person = a_person(alpha)
        contract = a_contract(alpha, person)
        sheet = open_month(
            tenant_id=alpha["tenant"],
            company_id=alpha["company"],
            year=2026,
            month=3,
            norm_hours=Decimal("168.00"),
        )
        set_days(
            timesheet_id=sheet.id,
            contract_id=contract.id,
            days=[{"work_date": "2026-03-02", "hours_worked": "8.00"}],
        )
        close_month(timesheet_id=sheet.id)

        with pytest.raises(TimesheetClosedError):
            set_days(
                timesheet_id=sheet.id,
                contract_id=contract.id,
                days=[{"work_date": "2026-03-03", "hours_worked": "8.00"}],
            )

        # And past the service, straight at the table.
        with pytest.raises(Exception) as refused, transaction.atomic():
            TimesheetDay.objects.create(
                tenant_id=alpha["tenant"],
                company_id=alpha["company"],
                timesheet_id=sheet.id,
                contract_id=contract.id,
                work_date=date(2026, 3, 5),
                hours_worked=Decimal("8.00"),
            )
        assert "frozen" in str(refused.value)

        assert month_in_context(sheet.id)["status"] == "closed"
