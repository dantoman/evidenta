"""The contract as head of a series -- ADR-067.

**"Which clause was in force on date D" is read by walking the series**, never
from a column. That is the whole reason `EmploymentContractAmendment` exists: any
change to any clause of art. 49 para (1) of the Labour Code requires a signed
amendment, and a contract overwritten in place can neither show what was in force
in March nor that the change was consented to. `R18` asks the first of those of
every recalculation of a past month.

**The employer's order is the generating fact of the reporting**, not the
contract (IRM19 instruction, points 2 and 3). So both a hire and an amendment
carry an order number and an order date, and a termination cannot be recorded
without one -- the database refuses it too.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.db import IntegrityError, transaction

from evidenta.fiscal.registry.services.relationships import relationship_types
from evidenta.operations.payroll.models import (
    EMPLOYER_CAS_POINTS,
    CostDestination,
    Employee,
    EmploymentContract,
    EmploymentContractAmendment,
)
from evidenta.platform.api.errors import ApiError
from evidenta.platform.audit.services.recording import record


class ContractMalformedError(ApiError):
    code = "payroll.contract_malformed"
    status = 422


class ContractDuplicateError(ApiError):
    code = "payroll.contract_number_taken"
    status = 409


class ContractNotFoundError(ApiError):
    code = "payroll.contract_not_found"
    status = 404


class ContractAlreadyEndedError(ApiError):
    code = "payroll.contract_already_ended"
    status = 409


@dataclass(frozen=True, slots=True)
class Clauses:
    """What was in force on a date, and which amendment last set each field.

    The provenance is half the answer. "The salary was 9000 in March" is not
    defensible on its own; "9000, set by amendment 2 of 12.02" is.
    """

    position_title: str
    base_salary: Decimal
    weekly_hours: Decimal
    set_by: dict[str, str]


def create_contract(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    employee_id: uuid.UUID,
    relationship_type: str,
    contract_number: str,
    signed_on: date,
    effective_from: date,
    hire_order_number: str,
    hire_order_date: date,
    position_title: str,
    base_salary: Decimal,
    weekly_hours: Decimal,
    cas_payer_point: str,
    budget_funded_employer: bool,
    cost_destination: str,
    effective_to: date | None = None,
) -> EmploymentContract:
    """Open a work relationship. Every clause the calculation reads is required.

    `relationship_type` is checked here **for two reasons, and the second is not
    cosmetic**. The first is the message: naming the three real forms beats a
    constraint name. The second is *when*: Django declares its foreign keys
    `DEFERRABLE INITIALLY DEFERRED`, so an unknown type does not fail at INSERT --
    it fails at commit, which is the end of the request, far from the caller and
    with no stable code (`C10`). The key remains the structural guarantee ADR-071
    argues for; this is what turns a 500 at commit into a 422 here.
    """
    number = (contract_number or "").strip()
    if not number:
        raise ContractMalformedError("a contract has a number")
    known = {row.code for row in relationship_types()}
    if relationship_type not in known:
        raise ContractMalformedError(
            f"{relationship_type!r} is not a form of work relationship the acts "
            f"distinguish. Point 1.1 of annex 1 to Law 489/1999 names three: "
            f"{', '.join(sorted(known))}"
        )
    if cas_payer_point not in EMPLOYER_CAS_POINTS:
        raise ContractMalformedError(
            f"{cas_payer_point!r} is not a CAS payer category an employer carries. "
            f"Annex 1 to Law 489/1999 names the employer at points "
            f"{', '.join(EMPLOYER_CAS_POINTS)}; the rest are categories individuals "
            f"pay for themselves"
        )
    if cost_destination not in CostDestination.values:
        raise ContractMalformedError(
            f"{cost_destination!r} is not a cost destination. A person's pay is one of "
            f"{', '.join(CostDestination.values)} (ADR-065 section 7.1), and the choice "
            f"names the expense account, so it is stated rather than assumed"
        )
    if base_salary is None or base_salary < 0:
        raise ContractMalformedError("a salary is not negative")
    if weekly_hours is None or weekly_hours <= 0:
        raise ContractMalformedError(
            "the weekly hours are required: art. 22 para (1) wants the minimum "
            "base proportional to time worked, and a handler that multiplies base "
            "by rate misses it"
        )
    if effective_to is not None and effective_to < effective_from:
        raise ContractMalformedError("a fixed term ends after it starts")

    if not Employee.objects.filter(id=employee_id, company_id=company_id).exists():
        raise ContractMalformedError("no such person in this company")

    try:
        with transaction.atomic():
            contract = EmploymentContract.objects.create(
                tenant_id=tenant_id,
                company_id=company_id,
                employee_id=employee_id,
                relationship_type_id=relationship_type,
                contract_number=number,
                signed_on=signed_on,
                effective_from=effective_from,
                effective_to=effective_to,
                hire_order_number=(hire_order_number or "").strip(),
                hire_order_date=hire_order_date,
                position_title=(position_title or "").strip(),
                base_salary=base_salary,
                weekly_hours=weekly_hours,
                cas_payer_point=cas_payer_point,
                budget_funded_employer=budget_funded_employer,
                cost_destination=cost_destination,
            )
    except IntegrityError as exc:
        raise ContractDuplicateError(f"contract {number} already exists in this company") from exc

    record(
        action="payroll.contract_created",
        entity_type="employment_contract",
        entity_id=contract.id,
        company_id=company_id,
        new_value={"number": number, "relationship_type": relationship_type},
    )
    return contract


def add_amendment(
    *,
    contract_id: uuid.UUID,
    amendment_number: str,
    signed_on: date,
    effective_from: date,
    order_number: str,
    order_date: date,
    changed_clause: str,
    note: str = "",
    position_title: str | None = None,
    base_salary: Decimal | None = None,
    weekly_hours: Decimal | None = None,
) -> EmploymentContractAmendment:
    """Record one signed amendment. The clause it changes is named, always.

    A `None` column means *this amendment did not touch that clause*. An
    amendment to a clause this module does not model is still recordable --
    `changed_clause` plus `note` -- rather than invisible, which is the failure a
    fixed set of columns would produce.
    """
    contract = EmploymentContract.objects.filter(id=contract_id).first()
    if contract is None:
        raise ContractNotFoundError("no such contract in this context")

    clause = (changed_clause or "").strip()
    if not clause:
        raise ContractMalformedError(
            "an amendment names the clause of art. 49 para (1) it changes: without "
            "it, a change to a clause this module does not model leaves no trace"
        )
    if effective_from < contract.effective_from:
        raise ContractMalformedError("an amendment takes effect after the contract does")
    if base_salary is not None and base_salary < 0:
        raise ContractMalformedError("a salary is not negative")
    if weekly_hours is not None and weekly_hours <= 0:
        raise ContractMalformedError("weekly hours are positive")

    try:
        with transaction.atomic():
            amendment = EmploymentContractAmendment.objects.create(
                tenant_id=contract.tenant_id,
                company_id=contract.company_id,
                contract=contract,
                amendment_number=(amendment_number or "").strip(),
                signed_on=signed_on,
                effective_from=effective_from,
                order_number=(order_number or "").strip(),
                order_date=order_date,
                changed_clause=clause,
                note=note or "",
                position_title=position_title,
                base_salary=base_salary,
                weekly_hours=weekly_hours,
            )
    except IntegrityError as exc:
        raise ContractDuplicateError(
            f"amendment {amendment_number} already exists on this contract"
        ) from exc

    record(
        action="payroll.amendment_created",
        entity_type="employment_contract_amendment",
        entity_id=amendment.id,
        company_id=contract.company_id,
        new_value={"contract": str(contract.id), "clause": clause},
    )
    return amendment


def end_contract(
    *,
    contract_id: uuid.UUID,
    ended_on: date,
    order_number: str,
    order_date: date,
) -> EmploymentContract:
    """Close a relationship. The order is required, not decorative.

    The IRM19 deadline for a termination runs from the date on the order, so a
    termination with no order behind it is one that cannot be reported. The
    database carries the same rule, which is why this cannot be worked around by
    writing the row another way.
    """
    contract = EmploymentContract.objects.filter(id=contract_id).first()
    if contract is None:
        raise ContractNotFoundError("no such contract in this context")
    if contract.ended_on is not None:
        raise ContractAlreadyEndedError(
            f"contract {contract.contract_number} already ended on {contract.ended_on}"
        )
    if ended_on < contract.effective_from:
        raise ContractMalformedError("a contract ends after it starts")
    if not (order_number or "").strip():
        raise ContractMalformedError(
            "an ending is ordered: the ten-working-day IRM19 deadline runs from the "
            "date on the order, not from the last day worked"
        )

    contract.ended_on = ended_on
    contract.termination_order_number = order_number.strip()
    contract.termination_order_date = order_date
    contract.save(update_fields=["ended_on", "termination_order_number", "termination_order_date"])

    record(
        action="payroll.contract_ended",
        entity_type="employment_contract",
        entity_id=contract.id,
        company_id=contract.company_id,
        new_value={"ended_on": str(ended_on), "order": order_number},
    )
    return contract


def clauses_in_force_on(contract_id: uuid.UUID, on: date) -> Clauses:
    """Walk the series. This is the only way to answer the question.

    Amendments apply in order of their effective date; each one overwrites only
    the clauses it names. Two amendments effective the same day are applied in
    signing order, then by number -- a deterministic order, because "whichever
    the database returned first" is an answer that changes between runs.
    """
    contract = EmploymentContract.objects.filter(id=contract_id).first()
    if contract is None:
        raise ContractNotFoundError("no such contract in this context")

    position = contract.position_title
    salary = contract.base_salary
    hours = contract.weekly_hours
    set_by = {
        "position_title": contract.contract_number,
        "base_salary": contract.contract_number,
        "weekly_hours": contract.contract_number,
    }

    amendments = contract.amendments.filter(effective_from__lte=on).order_by(
        "effective_from", "signed_on", "amendment_number"
    )
    for amendment in amendments:
        if amendment.position_title is not None:
            position = amendment.position_title
            set_by["position_title"] = amendment.amendment_number
        if amendment.base_salary is not None:
            salary = amendment.base_salary
            set_by["base_salary"] = amendment.amendment_number
        if amendment.weekly_hours is not None:
            hours = amendment.weekly_hours
            set_by["weekly_hours"] = amendment.amendment_number

    return Clauses(position_title=position, base_salary=salary, weekly_hours=hours, set_by=set_by)


def contracts_of(
    company_id: uuid.UUID, *, employee_id: uuid.UUID | None = None, include_ended: bool = False
) -> list[dict[str, Any]]:
    rows = EmploymentContract.objects.filter(company_id=company_id).select_related("employee")
    if employee_id is not None:
        rows = rows.filter(employee_id=employee_id)
    if not include_ended:
        rows = rows.filter(ended_on__isnull=True)
    return [as_dict(row) for row in rows.order_by("-effective_from", "contract_number")]


def contract_in_context(contract_id: uuid.UUID) -> dict[str, Any]:
    contract = EmploymentContract.objects.filter(id=contract_id).select_related("employee").first()
    if contract is None:
        raise ContractNotFoundError("no such contract in this context")

    payload = as_dict(contract)
    payload["amendments"] = [
        {
            "id": str(amendment.id),
            "amendment_number": amendment.amendment_number,
            "signed_on": str(amendment.signed_on),
            "effective_from": str(amendment.effective_from),
            "order_number": amendment.order_number,
            "order_date": str(amendment.order_date),
            "changed_clause": amendment.changed_clause,
            "note": amendment.note,
            "position_title": amendment.position_title,
            "base_salary": _amount(amendment.base_salary),
            "weekly_hours": _amount(amendment.weekly_hours),
        }
        for amendment in contract.amendments.order_by("effective_from", "amendment_number")
    ]
    return payload


def as_dict(contract: EmploymentContract) -> dict[str, Any]:
    return {
        "id": str(contract.id),
        "employee_id": str(contract.employee_id),
        "employee_name": f"{contract.employee.last_name} {contract.employee.first_name}",
        "relationship_type": contract.relationship_type_id,
        "contract_number": contract.contract_number,
        "signed_on": str(contract.signed_on),
        "effective_from": str(contract.effective_from),
        "effective_to": str(contract.effective_to) if contract.effective_to else None,
        "ended_on": str(contract.ended_on) if contract.ended_on else None,
        "hire_order_number": contract.hire_order_number,
        "hire_order_date": str(contract.hire_order_date),
        "termination_order_number": contract.termination_order_number,
        "termination_order_date": (
            str(contract.termination_order_date) if contract.termination_order_date else None
        ),
        "position_title": contract.position_title,
        "base_salary": _amount(contract.base_salary),
        "weekly_hours": _amount(contract.weekly_hours),
        "cas_payer_point": contract.cas_payer_point,
        "budget_funded_employer": contract.budget_funded_employer,
        "cost_destination": contract.cost_destination,
    }


def _amount(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def set_cost_destination(*, contract_id: uuid.UUID, cost_destination: str) -> dict[str, Any]:
    """State where an existing contract's cost goes -- ADR-065 section 7.1.

    For the contracts written before the column existed, and for a person who
    moves between administration and production. Nothing already posted moves: a
    run reads the destination when it is approved, and the entry keeps what it
    read (`R10`); the next run reads the new one.
    """
    if cost_destination not in CostDestination.values:
        raise ContractMalformedError(
            f"{cost_destination!r} is not a cost destination; one of "
            f"{', '.join(CostDestination.values)} is"
        )
    contract = EmploymentContract.objects.filter(id=contract_id).first()
    if contract is None:
        raise ContractNotFoundError("no such contract in this context")
    previous = contract.cost_destination
    contract.cost_destination = cost_destination
    contract.save(update_fields=["cost_destination", "updated_at"])
    record(
        action="payroll.contract_cost_destination_set",
        entity_type="employment_contract",
        entity_id=contract.id,
        company_id=contract.company_id,
        new_value={"from": previous, "to": cost_destination},
    )
    return contract_in_context(contract.id)
