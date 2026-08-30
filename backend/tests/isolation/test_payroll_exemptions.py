"""Exemptions -- the history point 18 makes necessary. Under the application role.

Four claims:

1. **The effective date is derived, and the database checks it.** Point 18 of the
   regulation approved by HG 697/2014: exemptions are granted or cancelled from
   the month *following* the one the application was filed in. The service derives
   it; the CHECK is what makes the rule survive a bulk import or a row written by
   hand.
2. **There is no `S`.** Art. 34 para (2) grants only the increased spouse
   exemption. A vocabulary that offered the ordinary one would let somebody claim
   an exemption the Fiscal Code does not give.
3. **The same dependent cannot be claimed twice by one employee** -- and two
   employees claiming for the same person stays allowed, because the law allows
   it and a constraint refusing it would be our invention.
4. **A withdrawal closes, it never deletes.** The month the exemption was granted
   in still recalculates the same way afterwards, which is what `R18` requires.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date

import pytest
from django.db import IntegrityError, transaction
from django.db.utils import ProgrammingError

from evidenta.operations.payroll.models import (
    ExemptionApplication,
    ExemptionEntitlement,
    TaxResidency,
)
from evidenta.operations.payroll.services.exemptions import (
    ExemptionMalformedError,
    ExemptionOverlapError,
    GrantRequest,
    add_dependent,
    exemptions_in_force_on,
    exemptions_of,
    file_application,
    month_after,
    withdraw,
)
from evidenta.operations.payroll.services.people import create_employee
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])


@pytest.fixture
def alpha(
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> dict[str, uuid.UUID]:
    company = company_of(world["tenant_a"], "1000000000011", "Alpha SRL")
    grant_company(world["tenant_a"], company, world["user_a"], world["user_a"])
    return {"tenant": world["tenant_a"], "user": world["user_a"], "company": company}


def context_of(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant"], user_id=world["user"], request_id="exemptions")


def a_person(world: dict[str, uuid.UUID], *, idnp: str = "2001234567891") -> uuid.UUID:
    return create_employee(
        tenant_id=world["tenant"],
        company_id=world["company"],
        last_name="Rusu",
        first_name="Ion",
        tax_residency=TaxResidency.RESIDENT,
        idnp=idnp,
    ).id


def test_the_effective_date_is_the_month_after_filing() -> None:
    """Point 18, including the year boundary -- a month after December is January."""
    assert month_after(date(2026, 3, 17)) == date(2026, 4, 1)
    assert month_after(date(2026, 12, 31)) == date(2027, 1, 1)
    assert month_after(date(2026, 1, 1)) == date(2026, 2, 1)


def test_an_application_grants_from_the_month_after_it_was_filed(
    alpha: dict[str, uuid.UUID],
) -> None:
    with tenant_context(context_of(alpha)):
        employee = a_person(alpha)
        result = file_application(
            tenant_id=alpha["tenant"],
            company_id=alpha["company"],
            employee_id=employee,
            filed_on=date(2026, 3, 17),
            declared_sole_workplace=True,
            grants=[GrantRequest(code="P")],
        )

        assert result["effective_from"] == "2026-04-01"
        # March is before it applies; April is not. The interval is what point 18
        # says, not what the filing date suggests.
        assert exemptions_in_force_on(employee, date(2026, 3, 31)) == []
        assert [row["code"] for row in exemptions_in_force_on(employee, date(2026, 4, 1))] == ["P"]


def test_the_database_refuses_an_effective_date_that_is_not_the_month_after(
    alpha: dict[str, uuid.UUID],
) -> None:
    """The service derives it; this proves a row cannot arrive any other way.

    A rule that lives only in a service is a rule an import walks past -- and an
    exemption granted a month early is a withholding that was wrong for a month,
    balanced and silent.
    """
    with tenant_context(context_of(alpha)):
        employee = a_person(alpha)
        with pytest.raises(IntegrityError), transaction.atomic():
            ExemptionApplication.objects.create(
                tenant_id=alpha["tenant"],
                company_id=alpha["company"],
                employee_id=employee,
                filed_on=date(2026, 3, 17),
                effective_from=date(2026, 3, 1),
                declared_sole_workplace=True,
            )


def test_there_is_no_ordinary_spouse_exemption(alpha: dict[str, uuid.UUID]) -> None:
    """`S` is not a code. Art. 34 para (2) grants only the increased one."""
    with tenant_context(context_of(alpha)):
        employee = a_person(alpha)
        with pytest.raises(ExemptionMalformedError):
            file_application(
                tenant_id=alpha["tenant"],
                company_id=alpha["company"],
                employee_id=employee,
                filed_on=date(2026, 3, 17),
                declared_sole_workplace=True,
                grants=[GrantRequest(code="S")],
            )


def test_a_dependent_exemption_names_a_person_and_a_personal_one_does_not(
    alpha: dict[str, uuid.UUID],
) -> None:
    with tenant_context(context_of(alpha)):
        employee = a_person(alpha)
        child = add_dependent(
            tenant_id=alpha["tenant"],
            company_id=alpha["company"],
            employee_id=employee,
            last_name="Rusu",
            first_name="Maria",
            idnp="2009999999991",
        )

        with pytest.raises(ExemptionMalformedError):
            file_application(
                tenant_id=alpha["tenant"],
                company_id=alpha["company"],
                employee_id=employee,
                filed_on=date(2026, 3, 17),
                declared_sole_workplace=True,
                grants=[GrantRequest(code="N")],
            )

        with pytest.raises(ExemptionMalformedError):
            file_application(
                tenant_id=alpha["tenant"],
                company_id=alpha["company"],
                employee_id=employee,
                filed_on=date(2026, 3, 17),
                declared_sole_workplace=True,
                grants=[GrantRequest(code="P", dependent_id=child.id)],
            )


def test_the_same_child_cannot_be_claimed_twice_by_one_employee(
    alpha: dict[str, uuid.UUID],
) -> None:
    """The constraint that needed the dependent to have an identifier at all."""
    with tenant_context(context_of(alpha)):
        employee = a_person(alpha)
        child = add_dependent(
            tenant_id=alpha["tenant"],
            company_id=alpha["company"],
            employee_id=employee,
            last_name="Rusu",
            first_name="Maria",
            idnp="2009999999992",
        )
        file_application(
            tenant_id=alpha["tenant"],
            company_id=alpha["company"],
            employee_id=employee,
            filed_on=date(2026, 3, 17),
            declared_sole_workplace=True,
            grants=[GrantRequest(code="N", dependent_id=child.id)],
        )

        with pytest.raises(ExemptionOverlapError):
            file_application(
                tenant_id=alpha["tenant"],
                company_id=alpha["company"],
                employee_id=employee,
                filed_on=date(2026, 5, 10),
                declared_sole_workplace=True,
                grants=[GrantRequest(code="N", dependent_id=child.id)],
            )


def test_two_employees_may_claim_for_the_same_person(alpha: dict[str, uuid.UUID]) -> None:
    """Both parents may claim for the same child. A UNIQUE there would be our invention.

    The dependents are two rows, one per employee, because the exemption is
    claimed by each of them separately -- and neither claim tells the other
    employer anything, which is exactly the state the law leaves.
    """
    with tenant_context(context_of(alpha)):
        mother = a_person(alpha, idnp="2001234567892")
        father = a_person(alpha, idnp="2001234567893")

        for parent in (mother, father):
            child = add_dependent(
                tenant_id=alpha["tenant"],
                company_id=alpha["company"],
                employee_id=parent,
                last_name="Rusu",
                first_name="Maria",
                idnp="2009999999993",
            )
            file_application(
                tenant_id=alpha["tenant"],
                company_id=alpha["company"],
                employee_id=parent,
                filed_on=date(2026, 3, 17),
                declared_sole_workplace=True,
                grants=[GrantRequest(code="N", dependent_id=child.id)],
            )

        assert len(exemptions_in_force_on(mother, date(2026, 5, 1))) == 1
        assert len(exemptions_in_force_on(father, date(2026, 5, 1))) == 1


def test_a_withdrawal_closes_from_the_month_after_and_keeps_the_row(
    alpha: dict[str, uuid.UUID],
) -> None:
    """`R18`: the months already granted still recalculate the same way."""
    with tenant_context(context_of(alpha)):
        employee = a_person(alpha)
        granted = file_application(
            tenant_id=alpha["tenant"],
            company_id=alpha["company"],
            employee_id=employee,
            filed_on=date(2026, 1, 10),
            declared_sole_workplace=True,
            grants=[GrantRequest(code="P")],
        )
        entitlement = granted["granted"][0]["id"]

        withdrawal = withdraw(
            tenant_id=alpha["tenant"],
            company_id=alpha["company"],
            employee_id=employee,
            filed_on=date(2026, 6, 5),
            entitlement_ids=[uuid.UUID(entitlement)],
        )

        assert withdrawal["effective_from"] == "2026-07-01"
        # In force through June, gone from July -- the half-open interval.
        assert len(exemptions_in_force_on(employee, date(2026, 6, 30))) == 1
        assert exemptions_in_force_on(employee, date(2026, 7, 1)) == []
        # And the row is still there, with both documents on it.
        history = exemptions_of(employee)
        assert len(history) == 1
        assert history[0]["valid_to"] == "2026-07-01"


def test_an_exemption_row_cannot_be_deleted_by_the_application(
    alpha: dict[str, uuid.UUID],
) -> None:
    """No DELETE privilege at all: a removed exemption changes a closed month."""
    with tenant_context(context_of(alpha)):
        employee = a_person(alpha)
        file_application(
            tenant_id=alpha["tenant"],
            company_id=alpha["company"],
            employee_id=employee,
            filed_on=date(2026, 1, 10),
            declared_sole_workplace=True,
            grants=[GrantRequest(code="M")],
        )

        # `ProgrammingError`, not a blind `Exception`: the refusal has to come
        # from the missing privilege. A constraint violation or a policy that
        # matched no rows would be a different failure wearing the same result.
        with pytest.raises(ProgrammingError), transaction.atomic():
            ExemptionEntitlement.objects.filter(employee_id=employee).delete()

        assert ExemptionEntitlement.objects.filter(employee_id=employee).count() == 1


def test_another_company_sees_none_of_it(
    alpha: dict[str, uuid.UUID],
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> None:
    """The exemption is as sensitive as the salary, and the boundary is the same."""
    with tenant_context(context_of(alpha)):
        employee = a_person(alpha)
        file_application(
            tenant_id=alpha["tenant"],
            company_id=alpha["company"],
            employee_id=employee,
            filed_on=date(2026, 1, 10),
            declared_sole_workplace=True,
            grants=[GrantRequest(code="P")],
        )

    beta_company = company_of(world["tenant_b"], "1000000000012", "Beta SRL")
    grant_company(world["tenant_b"], beta_company, world["user_b"], world["user_b"])
    intruder = TenantContext(
        tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="intruder"
    )
    with tenant_context(intruder):
        assert exemptions_of(employee) == []
        assert exemptions_in_force_on(employee, date(2026, 5, 1)) == []
