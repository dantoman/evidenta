"""The unified monthly return -- generation, versioning, and `T1` in both directions.

No real rate here either: the fixture values are the nonsense ones from
`test_payroll_run.py`, for the reason stated there.

What is under test:

1. **One entity, three sections** (art. 5 para (1)): a header that freezes the
   company's codes, a totals section grouped on both dimensions the form groups
   on, and a nominal section over **insured persons**.
2. **Versions, never overwrites** (art. 188): a second primary return is refused,
   a correction is the next version and names the one it replaces, and a
   submitted return's rows are frozen by the database.
3. **Stored, not recomputed**: after a filed return, changing what the payroll
   says does not change what the return says.
4. **`T1`, both directions** -- and shown failing on a fixture before being
   believed, because on an empty database it would pass vacuously.
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

from evidenta.operations.payroll.models import PayrollLine, TaxResidency
from evidenta.operations.payroll.services.contracts import create_contract
from evidenta.operations.payroll.services.people import create_employee
from evidenta.operations.payroll.services.runs import approve, create_run
from evidenta.operations.payroll.services.timesheets import open_month, set_days
from evidenta.operations.tax.models import IpcDeclaration, IpcNominalLine, IpcTotalLine
from evidenta.operations.tax.services.ipc import (
    IpcEmptyError,
    IpcExistsError,
    correct,
    declaration_in_context,
    declarations_of,
    due_date,
    generate,
    submit,
)
from evidenta.operations.tax.services.reconciliation import reconcile
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration", "refdata"])

FIXTURE_VALUES = {
    "cnas.employer_rate": 50,
    "cnam.employee_rate": 25,
    "income_tax.rate_individual": 40,
    "labour.minimum_wage_monthly": 4000,
    "income_tax.exemption_personal": 1200,
}

SOURCE_ID = uuid.UUID("00000000-0000-0000-0000-0000000000f1")
APPROVER = uuid.UUID("00000000-0000-0000-0000-0000000000f2")


@pytest.fixture
def alpha(
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
    seed: Callable[..., None],
) -> dict[str, uuid.UUID]:
    company = company_of(world["tenant_a"], "1000000000031", "Alpha SRL")
    grant_company(world["tenant_a"], company, world["user_a"], world["user_a"])
    # The two classifier codes the header freezes. Fictitious, like every other
    # code in this file.
    seed(
        "UPDATE company SET cuatm_code = '0101', caem_code = '62.01' WHERE id = %s",
        [company],
    )
    return {"tenant": world["tenant_a"], "user": world["user_a"], "company": company}


def context_of(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant"], user_id=world["user"], request_id="ipc")


@pytest.fixture(autouse=True)
def parameters(seed: Callable[..., None], alpha: dict[str, uuid.UUID]) -> None:
    """Everything the calculation resolves, so the run can be approved at all.

    Approval refuses while a line has no amount, and a return is generated only
    from an approved run -- so a file about the return has to make the calculation
    complete first.
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
        " VALUES (%s, 'accounting.money_rounding', 'half_up', 'test-ipc',"
        " DATE '2020-01-01', %s, 'test.rounding', 'active', %s, now(), now(), now())",
        [uuid.uuid4(), SOURCE_ID, alpha["user"]],
    )
    for key, value in FIXTURE_VALUES.items():
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


def a_person(world: dict[str, uuid.UUID], *, idnp: str, number: str) -> uuid.UUID:
    employee = create_employee(
        tenant_id=world["tenant"],
        company_id=world["company"],
        last_name="Rusu",
        first_name=number,
        tax_residency=TaxResidency.RESIDENT,
        idnp=idnp,
    )
    create_contract(
        tenant_id=world["tenant"],
        company_id=world["company"],
        employee_id=employee.id,
        relationship_type="employment_contract",
        contract_number=number,
        signed_on=date(2025, 12, 20),
        effective_from=date(2026, 1, 1),
        hire_order_number="1-p",
        hire_order_date=date(2025, 12, 21),
        position_title="Contabil",
        base_salary=Decimal("10000.0000"),
        weekly_hours=Decimal("40.00"),
        cas_payer_point="1.1",
        budget_funded_employer=False,
    )
    return employee.id


def an_approved_month(world: dict[str, uuid.UUID], *, people: int = 1) -> list[uuid.UUID]:
    ids = [
        a_person(world, idnp=f"200222222220{index}", number=f"CIM-{index}")
        for index in range(1, people + 1)
    ]
    sheet = open_month(
        tenant_id=world["tenant"],
        company_id=world["company"],
        year=2026,
        month=3,
        norm_hours=Decimal("160.00"),
    )
    for contract in _contracts(world):
        set_days(
            timesheet_id=sheet.id,
            contract_id=contract,
            days=[
                {"work_date": f"2026-03-{day:02d}", "hours_worked": "8.00"} for day in range(2, 22)
            ],
        )
    run = create_run(
        tenant_id=world["tenant"],
        company_id=world["company"],
        year=2026,
        month=3,
        accrual_date=date(2026, 3, 31),
    )
    approve(run_id=run.id, approver_user_id=world["user"])
    return ids


def _contracts(world: dict[str, uuid.UUID]) -> list[uuid.UUID]:
    from evidenta.operations.payroll.models import EmploymentContract

    return list(
        EmploymentContract.objects.filter(company_id=world["company"]).values_list("id", flat=True)
    )


def a_declaration(world: dict[str, uuid.UUID]) -> dict[str, Any]:
    return generate(tenant_id=world["tenant"], company_id=world["company"], year=2026, month=3)


def test_the_deadline_is_the_twenty_fifth_of_the_following_month() -> None:
    """Art. 5 para (1) letter a), including across a year boundary."""
    assert due_date(2026, 3) == date(2026, 4, 25)
    assert due_date(2026, 12) == date(2027, 1, 25)


def test_the_return_is_one_entity_with_a_header_and_two_sections(
    alpha: dict[str, uuid.UUID],
) -> None:
    """Art. 5 para (1): the nominal record is part of the return, not a report of its own."""
    with tenant_context(context_of(alpha)):
        an_approved_month(alpha, people=2)
        declaration = a_declaration(alpha)

    assert declaration["version_number"] == 1
    assert declaration["due_on"] == "2026-04-25"
    # The header, frozen from the company as it was.
    assert declaration["header"] == {
        "fiscal_code": "1000000000031",
        "cuatm_code": "0101",
        "caem_code": "62.01",
    }
    # One totals row: one income source code, one tariff row.
    assert len(declaration["totals"]) == 1
    totals = declaration["totals"][0]
    assert totals["income_source_code"] == "SAL"
    assert totals["cas_tariff_code"] == "1.1b"
    assert totals["income_paid"] == "20000.00"
    assert totals["social_contribution"] == "10000.00"
    assert totals["health_insurance_withheld"] == "5000.00"
    # And two nominal rows, numbered.
    assert [row["line_number"] for row in declaration["nominal"]] == [1, 2]
    assert declaration["nominal"][0]["insured_income"] == "10000.00"


def test_the_category_classifier_is_absent_rather_than_guessed(
    alpha: dict[str, uuid.UUID],
) -> None:
    """Annex 3 is not obtained, so column 7 is empty rather than invented.

    A wrong category on a filed return is not an error the channel rejects; it is
    a correct answer to a different question, which is worse.
    """
    with tenant_context(context_of(alpha)):
        an_approved_month(alpha)
        declaration = a_declaration(alpha)

    assert declaration["nominal"][0]["insured_category_code"] is None


def test_a_second_primary_return_is_refused_and_a_correction_is_a_version(
    alpha: dict[str, uuid.UUID],
) -> None:
    """Art. 188: a change is a corrected return, never a second primary one."""
    with tenant_context(context_of(alpha)):
        an_approved_month(alpha)
        first = a_declaration(alpha)

        with pytest.raises(IpcExistsError):
            a_declaration(alpha)

        second = correct(declaration_id=uuid.UUID(first["id"]))

        assert second["version_number"] == 2
        assert second["corrects_id"] == first["id"]
        # Both stay readable, and the chain has one end.
        versions = [row["version_number"] for row in declarations_of(alpha["company"])]
        assert versions == [2, 1]


def test_a_submitted_return_is_frozen_by_the_database(
    alpha: dict[str, uuid.UUID],
) -> None:
    with tenant_context(context_of(alpha)):
        an_approved_month(alpha)
        declaration = a_declaration(alpha)
        submitted = submit(
            declaration_id=uuid.UUID(declaration["id"]), submitted_on=date(2026, 4, 20)
        )
        assert submitted["status"] == "submitted"

        row = IpcNominalLine.objects.filter(declaration_id=uuid.UUID(declaration["id"])).first()
        assert row is not None
        with pytest.raises(Exception) as refused, transaction.atomic():
            row.contribution = Decimal("1.00")
            row.save(update_fields=["contribution"])
        assert "frozen" in str(refused.value)


def test_the_return_reads_what_it_stored_rather_than_recomputing(
    alpha: dict[str, uuid.UUID],
) -> None:
    """Rule (b), demonstrated from the side that can actually be observed.

    "Stored, not recomputed" is a claim about the read path, and the way to see it
    is to make storage and computation disagree and ask which one answers. The
    payroll cannot be moved -- an approved run is frozen -- so the declaration is:
    while it is still a draft, one stored contribution is changed to a value the
    calculation never produced.

    The read comes back with the stored value. Had the return recomputed, the
    edit would have had no effect and the payroll's number would have won -- which
    is exactly what would happen to a filed return the day a rate changes.
    """
    with tenant_context(context_of(alpha)):
        an_approved_month(alpha)
        declaration = a_declaration(alpha)
        declaration_id = uuid.UUID(declaration["id"])

        assert declaration["nominal"][0]["contribution"] == "5000.00"
        # What the payroll says, and goes on saying.
        charge = PayrollLine.objects.get(company_id=alpha["company"], component_key="cas.employer")
        assert charge.amount == Decimal("5000.00")

        IpcNominalLine.objects.filter(declaration_id=declaration_id).update(
            contribution=Decimal("1.00")
        )
        after = declaration_in_context(declaration_id)

    assert after["nominal"][0]["contribution"] == "1.00"
    assert charge.amount == Decimal("5000.00")


def test_a_period_with_no_approved_payroll_is_refused_not_filed_empty(
    alpha: dict[str, uuid.UUID],
) -> None:
    """An empty return is a claim that nobody was insured, not an absence."""
    with tenant_context(context_of(alpha)), pytest.raises(IpcEmptyError):
        a_declaration(alpha)


def test_the_application_cannot_delete_a_return(alpha: dict[str, uuid.UUID]) -> None:
    """No DELETE privilege on the header: a filed return is an artefact."""
    with tenant_context(context_of(alpha)):
        an_approved_month(alpha)
        declaration = a_declaration(alpha)
        with pytest.raises(ProgrammingError), transaction.atomic():
            IpcDeclaration.objects.filter(id=uuid.UUID(declaration["id"])).delete()


# --- T1: the reconciliation, both directions ---------------------------------


def test_the_reconciliation_agrees_on_a_generated_return(
    alpha: dict[str, uuid.UUID],
) -> None:
    """The green case -- and it says how many people each side held.

    The counts are asserted because a reconciliation over an empty period agrees
    trivially, and "agrees" without them is indistinguishable from "there was
    nothing to compare".
    """
    with tenant_context(context_of(alpha)):
        an_approved_month(alpha, people=3)
        declaration = a_declaration(alpha)
        result = reconcile(declaration_id=uuid.UUID(declaration["id"]))

    assert result.agrees
    assert result.charged_count == 3
    assert result.declared_count == 3


def test_the_reconciliation_names_a_person_charged_and_not_declared(
    alpha: dict[str, uuid.UUID],
) -> None:
    """The first direction, shown **failing** on a fixture.

    A nominal row is removed from a draft return -- which the trigger allows,
    because the return is not filed -- and the reconciliation has to name exactly
    the person who fell out. Without this, the check would only ever have been
    seen passing.
    """
    with tenant_context(context_of(alpha)):
        people = an_approved_month(alpha, people=2)
        declaration = a_declaration(alpha)
        dropped = people[0]

        IpcNominalLine.objects.filter(
            declaration_id=uuid.UUID(declaration["id"]), person_id=dropped
        ).delete()

        result = reconcile(declaration_id=uuid.UUID(declaration["id"]))

    assert not result.agrees
    assert result.missing == (dropped,)
    assert result.extra == ()
    assert (result.charged_count, result.declared_count) == (2, 1)


def test_the_reconciliation_names_a_row_declared_without_a_charge(
    alpha: dict[str, uuid.UUID],
) -> None:
    """The converse, which is the half nobody writes.

    A nominal row with no charge behind it declares a period of insurance that did
    not happen -- and CNAS reads it as one. Same fixture, opposite direction.
    """
    with tenant_context(context_of(alpha)):
        an_approved_month(alpha, people=1)
        declaration = a_declaration(alpha)
        stranger = uuid.uuid4()

        existing = IpcNominalLine.objects.filter(
            declaration_id=uuid.UUID(declaration["id"])
        ).first()
        assert existing is not None
        IpcNominalLine.objects.create(
            tenant_id=alpha["tenant"],
            company_id=alpha["company"],
            declaration_id=uuid.UUID(declaration["id"]),
            line_number=99,
            person_id=stranger,
            last_name="Nedeclarat",
            first_name="Fără sarcină",
            idnp=None,
            personal_insurance_code=None,
            work_period_start=existing.work_period_start,
            work_period_end=existing.work_period_end,
            insured_category_code=None,
            tariff_rate=None,
            insured_income=Decimal("1000.00"),
            contribution=Decimal("500.00"),
        )

        result = reconcile(declaration_id=uuid.UUID(declaration["id"]))

    assert not result.agrees
    assert result.extra == (stranger,)
    assert result.missing == ()


def test_the_vacuous_agreement_cannot_be_reached_through_the_product(
    alpha: dict[str, uuid.UUID],
) -> None:
    """A reconciliation between two empty sets agrees. Nothing can produce one.

    The concern is real: an agreement over nothing is true and useless, and a
    boolean-only result would hide it. Two things answer it, and the second is
    the one that matters.

    **The counts are on the result**, so "we compared three and they matched" is
    distinguishable from "we compared nobody" by reading rather than by trusting.
    And **generation refuses an empty period** -- so a declaration whose
    reconciliation could be vacuous does not exist. Measured here rather than
    argued: the attempt is refused, and the frozen payroll refuses the other route
    to the same state.
    """
    with tenant_context(context_of(alpha)):
        # No approved run yet: the only way to a declaration with nobody in it.
        with pytest.raises(IpcEmptyError):
            a_declaration(alpha)

        # And once there is one, the charges cannot be taken away again -- the
        # approved run's lines are frozen by the database.
        an_approved_month(alpha, people=1)
        declaration = a_declaration(alpha)
        with pytest.raises(Exception) as refused, transaction.atomic():
            PayrollLine.objects.filter(company_id=alpha["company"]).update(amount=None)
        assert "frozen" in str(refused.value)

        result = reconcile(declaration_id=uuid.UUID(declaration["id"]))

    assert result.agrees
    assert (result.charged_count, result.declared_count) == (1, 1)


def test_another_company_sees_none_of_the_return(
    alpha: dict[str, uuid.UUID],
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> None:
    """The nominal section carries names, IDNPs and amounts. Same boundary as payroll."""
    with tenant_context(context_of(alpha)):
        an_approved_month(alpha)
        a_declaration(alpha)

    beta_company = company_of(world["tenant_b"], "1000000000032", "Beta SRL")
    grant_company(world["tenant_b"], beta_company, world["user_b"], world["user_b"])
    intruder = TenantContext(
        tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="intruder"
    )
    with tenant_context(intruder):
        assert declarations_of(alpha["company"]) == []
        assert IpcNominalLine.objects.count() == 0
        assert IpcTotalLine.objects.count() == 0
