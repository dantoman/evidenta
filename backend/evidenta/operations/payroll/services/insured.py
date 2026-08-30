"""The insured population of a period -- ADR-069, and the interface is the wide one.

**"Insured persons" is not a subset of "employees".** Art. 19 para (7) second
sentence makes the provider under a civil contract an insured person with a
personal account, appearing **by name** in the nominal declaration. Today this
population happens to hold only employees, because civil contracts are step 8 --
but a query written on `employee` and widened later is not an extension, it is a
rewrite of every caller (ADR-069, measured).

So the signature is the wide one from the start, and the word in it is the wide
one: a **charge**, borne by somebody, in a period. What produces the charge today
is a payroll line; what produces it tomorrow may not be.

**This is the public service `tax` reads.** `D4` forbids payroll importing tax and
says nothing about the reverse -- the declaration reads the population through
here, never through payroll's models (`D6`).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import Sum

from evidenta.operations.payroll.models import PayrollLine, PayrollRunStatus
from evidenta.operations.payroll.services.runs import (
    CAS_EMPLOYER,
    CNAM_EMPLOYEE,
    GROSS,
    INCOME_TAX,
)

#: The income source code of a salary. `SAL` is the code the ECO mapping of the
#: IPC instruction names (point 9: 111110 for SAL); the full classifier is
#: Ordinul MF nr. 126/2017 and is **not** in this repository, so nothing here
#: derives a second code from anything.
SALARY_SOURCE_CODE = "SAL"


@dataclass(frozen=True, slots=True)
class InsuredCharge:
    """One person's charge for one period, as the declaration needs it."""

    person_id: uuid.UUID
    last_name: str
    first_name: str
    idnp: str | None
    personal_insurance_code: str | None
    work_period_start: date
    work_period_end: date

    #: The base the contribution was charged on -- not the gross where art. 22
    #: raised it to the minimum. The declaration carries the base, which is why
    #: the two are separate fields rather than one.
    insured_income: Decimal
    contribution: Decimal
    tariff_rate: Decimal | None

    #: Which row of the tariff table this belongs to: point 1.1 letter a) for a
    #: budget-funded employer, letter b) otherwise.
    cas_tariff_code: str

    income_source_code: str
    income_paid: Decimal
    income_tax_withheld: Decimal
    health_insurance_withheld: Decimal


@dataclass
class _Accumulator:
    """One person's lines, summed as they arrive.

    A small mutable holder rather than a dictionary of sums: the fields are named
    once, the types are the ones the dataclass declares, and adding a component
    later is a field rather than a key nobody checks.
    """

    line: PayrollLine
    gross: Decimal = Decimal(0)
    contribution: Decimal = Decimal(0)
    health: Decimal = Decimal(0)
    income_tax: Decimal = Decimal(0)
    basis: Decimal = Decimal(0)
    rate: Decimal | None = None

    def add(self, line: PayrollLine) -> None:
        if line.amount is None:
            return
        if line.component_key == GROSS:
            self.gross += line.amount
        elif line.component_key == CAS_EMPLOYER:
            self.contribution += line.amount
            self.basis = line.basis if line.basis is not None else line.amount
            self.rate = line.rate
        elif line.component_key == CNAM_EMPLOYEE:
            self.health += line.amount
        elif line.component_key == INCOME_TAX:
            self.income_tax += line.amount

    def charge(self, person_id: uuid.UUID) -> InsuredCharge:
        return InsuredCharge(
            person_id=person_id,
            last_name=self.line.employee.last_name,
            first_name=self.line.employee.first_name,
            idnp=self.line.employee.idnp,
            personal_insurance_code=self.line.employee.social_insurance_code,
            work_period_start=self.line.work_period_start,
            work_period_end=self.line.work_period_end,
            insured_income=self.basis,
            contribution=self.contribution,
            tariff_rate=self.rate,
            # Point 1.1 letter a) for a budget-funded employer, letter b)
            # otherwise -- the split by sector, not by category (`OD-107`).
            cas_tariff_code="1.1a" if self.line.contract.budget_funded_employer else "1.1b",
            income_source_code=SALARY_SOURCE_CODE,
            income_paid=self.gross,
            income_tax_withheld=self.income_tax,
            health_insurance_withheld=self.health,
        )


def insured_charges(*, company_id: uuid.UUID, year: int, month: int) -> list[InsuredCharge]:
    """Everyone with a social-contribution charge in the period, with their amounts.

    Read from **approved** runs only: a draft run can still hold lines with no
    amount, and a declaration built from one would carry a hole that nothing
    downstream could distinguish from a zero.

    Ordered by name, so the nominal section's numbering is stable between two
    generations of the same period -- a row order that changed would make two
    versions of one declaration look different where they are not.
    """
    lines = (
        PayrollLine.objects.filter(
            company_id=company_id,
            work_period_start__year=year,
            work_period_start__month=month,
            run__status=PayrollRunStatus.APPROVED,
        )
        .select_related("employee", "contract")
        .order_by("employee__last_name", "employee__first_name")
    )

    charges: dict[uuid.UUID, _Accumulator] = {}
    for line in lines:
        entry = charges.get(line.employee_id)
        if entry is None:
            entry = _Accumulator(line=line)
            charges[line.employee_id] = entry
        entry.add(line)

    return [entry.charge(person_id) for person_id, entry in charges.items() if entry.contribution]


def charged_person_ids(*, company_id: uuid.UUID, year: int, month: int) -> set[uuid.UUID]:
    """Just the identities, read straight from the lines.

    Deliberately **not** built on `insured_charges`: the reconciliation compares a
    declaration against this, and a comparison whose two sides come from one
    function is an echo, not a check -- the shape `P1` was measured to have.
    """
    rows = (
        PayrollLine.objects.filter(
            company_id=company_id,
            work_period_start__year=year,
            work_period_start__month=month,
            component_key=CAS_EMPLOYER,
            amount__isnull=False,
            run__status=PayrollRunStatus.APPROVED,
        )
        .values("employee_id")
        .annotate(total=Sum("amount"))
    )
    return {row["employee_id"] for row in rows if row["total"]}
