"""The monthly payroll calculation -- ADR-065, ADR-061, ADR-044.

**What resolves, resolves; what does not, says so.** A rate whose margin was
never established does not apply on any date (`OD-92`), and the two honest
answers to that are a refusal or a line with no amount and a reason. This module
takes the second: the gross computes, the register is usable, and every statutory
line that could not be produced names the parameter it needed. A zero would be
the third answer and it is the wrong one -- *a rate that is missing is not a rate
of zero*, which the resolver already says in those words.

Approval is where the incompleteness stops being harmless: a run with any
unresolved line cannot be approved, so nothing incomplete becomes a declared
fact.

**Two dates, and they answer different questions** (ADR-065 section 6, ADR-044
section 6). The *work period* is the month worked -- it selects the hours, the
clauses in force and the exemptions in force. The *accrual date* is when the pay
was calculated -- it selects the parameters and the rounding rule. A March salary
calculated in June accrues in June; that is a fact of June, not a recalculation
of March.

**Art. 22's domain is a set, read from the table** (`OD-106`). The minimum base
applies to employment contracts *and* service relationships, and not to civil
contracts. A membership test against a set, never an equality against one type.

**Nothing here posts.** The run produces amounts; turning them into journal lines
is the Posting Engine's, through accounting events (`R9`), and the account roles
that requires are ADR-065 section 7.
"""

from __future__ import annotations

import calendar
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Sum

from evidenta.accounting.currency.money import rounding_for
from evidenta.accounting.opening.services.cumulatives import opening_cumulative
from evidenta.fiscal.parameters.services.resolution import (
    FiscalResolutionError,
    resolve_parameter,
)
from evidenta.fiscal.registry.services.relationships import (
    MINIMUM_BASE_INVARIANT,
    invariant_domain,
)
from evidenta.operations.payroll.models import (
    EmploymentContract,
    LineNature,
    PayrollLine,
    PayrollRun,
    PayrollRunStatus,
    Timesheet,
    TimesheetDay,
)
from evidenta.operations.payroll.services.contracts import clauses_in_force_on
from evidenta.operations.payroll.services.exemptions import exemptions_in_force_on
from evidenta.platform.api.errors import ApiError
from evidenta.platform.audit.services.recording import record

#: The component keys this build produces. Codes, not labels -- what they are
#: called in the interface lives in the resource files (`C32`).
GROSS = "salary.gross"
CAS_EMPLOYER = "cas.employer"
CNAM_EMPLOYEE = "cnam.employee"
INCOME_TAX = "income_tax.withheld"

#: The exemption codes, mapped to the parameter that carries the annual amount.
#: There is no `S`: art. 34 para (2) grants only the increased spouse exemption
#: (ADR-065 section 5), and the parameter `income_tax.exemption_spouse_ordinary`
#: exists at zero precisely so its absence cannot be mistaken for an oversight.
EXEMPTION_PARAMETERS = {
    "P": "income_tax.exemption_personal",
    "M": "income_tax.exemption_personal_increased",
    "Sm": "income_tax.exemption_spouse_increased",
    "N": "income_tax.exemption_dependant",
    "H": "income_tax.exemption_dependant_disabled",
}

#: Cumulative codes, the vocabulary ADR-061 fixed. Shared with the opening
#: balances so a mid-year onboarding continues the same series rather than
#: starting a parallel one.
CUM_TAXABLE = "income_tax.taxable_income"
CUM_EXEMPTIONS = "income_tax.exemptions_granted"
CUM_WITHHELD = "income_tax.withheld"


class PayrollRunError(ApiError):
    code = "payroll.run_malformed"
    status = 422


class PayrollRunExistsError(ApiError):
    code = "payroll.run_exists"
    status = 409


class PayrollRunNotFoundError(ApiError):
    code = "payroll.run_not_found"
    status = 404


class PayrollRunNotDraftError(ApiError):
    code = "payroll.run_not_draft"
    status = 409


class PayrollRunIncompleteError(ApiError):
    """Approval refused while a line has no amount.

    Its own code (`C10`): "this cannot be approved yet because three rates are
    missing" is a different thing to do about than "what you sent is wrong".
    """

    code = "payroll.run_incomplete"
    status = 409


@dataclass(frozen=True, slots=True)
class Amount:
    """A computed component, with what produced it."""

    value: Decimal
    basis: Decimal | None = None
    rate: Decimal | None = None
    parameter_id: uuid.UUID | None = None
    parameter_key: str | None = None


@dataclass(frozen=True, slots=True)
class Unresolved:
    """A component that could not be computed, and why -- never a zero."""

    reason: str


Component = Amount | Unresolved


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    last = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def _rate_of(parameter_key: str, on: date) -> Component:
    """A percentage parameter, as a rate, or the reason it is not available.

    The reason names the key and the date, because "a rate is missing" sends
    somebody looking at the wrong thing when what is missing is the *margin*: the
    value may well be recorded and simply have no date it can be said to apply
    from (`OD-92`).
    """
    try:
        parameter = resolve_parameter(parameter_key, on)
    except FiscalResolutionError as exc:
        return Unresolved(
            f"{parameter_key}: {exc.code} pe {on}. Valoarea poate exista fără marginea "
            f"care o pune în vigoare — un parametru fără `valid_from` citabil nu se "
            f"aplică la nicio dată (OD-92). Suma nu se inventează."
        )
    return Amount(
        value=Decimal(str(parameter.value)) / Decimal(100),
        rate=Decimal(str(parameter.value)),
        parameter_id=parameter.id,
        parameter_key=parameter_key,
    )


def _annual_of(parameter_key: str, on: date) -> Component:
    try:
        parameter = resolve_parameter(parameter_key, on)
    except FiscalResolutionError as exc:
        return Unresolved(f"{parameter_key}: {exc.code} pe {on}")
    return Amount(
        value=Decimal(str(parameter.value)),
        parameter_id=parameter.id,
        parameter_key=parameter_key,
    )


def create_run(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    year: int,
    month: int,
    accrual_date: date,
) -> PayrollRun:
    """Open a run over the month's timesheet, and compute it.

    The timesheet is found by month rather than passed in: there is exactly one
    per company and month, and a caller choosing which sheet to compute from
    would be able to choose the wrong one.
    """
    sheet = Timesheet.objects.filter(company_id=company_id, year=year, month=month).first()
    if sheet is None:
        raise PayrollRunError(
            f"there is no timesheet for {year}-{month:02d}: the hours are the input "
            f"of the calculation, not something it can assume"
        )
    if PayrollRun.objects.filter(company_id=company_id, year=year, month=month).exists():
        raise PayrollRunExistsError(f"{year}-{month:02d} already has a run")

    with transaction.atomic():
        run = PayrollRun.objects.create(
            tenant_id=tenant_id,
            company_id=company_id,
            timesheet=sheet,
            year=year,
            month=month,
            accrual_date=accrual_date,
        )
        _compute(run)

    record(
        action="payroll.run_created",
        entity_type="payroll_run",
        entity_id=run.id,
        company_id=company_id,
        new_value={"year": year, "month": month, "accrual_date": str(accrual_date)},
    )
    return run


def recompute(*, run_id: uuid.UUID) -> dict[str, Any]:
    """Throw the lines away and calculate again. Only while draft.

    Replacing rather than patching: a recalculation that merged would leave a
    line behind for a contract that stopped being in scope, and that line would
    be indistinguishable from a real one.
    """
    run = PayrollRun.objects.filter(id=run_id).first()
    if run is None:
        raise PayrollRunNotFoundError("no such payroll run in this context")
    if run.status != PayrollRunStatus.DRAFT:
        raise PayrollRunNotDraftError(
            f"{run.year}-{run.month:02d} is {run.status}; its lines are frozen"
        )

    with transaction.atomic():
        run.lines.all().delete()
        _compute(run)

    record(
        action="payroll.run_recomputed",
        entity_type="payroll_run",
        entity_id=run.id,
        company_id=run.company_id,
    )
    return run_in_context(run.id)


def approve(*, run_id: uuid.UUID, approver_user_id: uuid.UUID) -> dict[str, Any]:
    """Freeze the run. Refused while any line has no amount.

    This is the point of the nullable amount: an incomplete calculation is
    perfectly fine as a draft -- it shows the gross, the hours and what is
    missing -- and must never become the basis of a declaration. The database
    holds the other half: after approval the trigger refuses every write to a
    line.
    """
    run = PayrollRun.objects.filter(id=run_id).first()
    if run is None:
        raise PayrollRunNotFoundError("no such payroll run in this context")
    if run.status != PayrollRunStatus.DRAFT:
        raise PayrollRunNotDraftError(f"{run.year}-{run.month:02d} is already {run.status}")

    unresolved = list(run.lines.filter(amount__isnull=True).values_list("component_key", flat=True))
    if unresolved:
        raise PayrollRunIncompleteError(
            f"{len(unresolved)} lines have no amount ({', '.join(sorted(set(unresolved)))}). "
            f"A run is approved when it is complete; approving one with gaps would "
            f"make a declaration out of what was not calculated"
        )

    run.status = PayrollRunStatus.APPROVED
    run.approved_by_user_id = approver_user_id
    run.approved_at = datetime.now(UTC)
    run.save(update_fields=["status", "approved_by_user_id", "approved_at"])

    record(
        action="payroll.run_approved",
        entity_type="payroll_run",
        entity_id=run.id,
        company_id=run.company_id,
        new_value={"year": run.year, "month": run.month},
    )
    return run_in_context(run.id)


def _compute(run: PayrollRun) -> None:
    """Produce the lines. Everything below is arithmetic over resolved inputs."""
    start, end = _month_bounds(run.year, run.month)
    rounding = rounding_for(run.accrual_date)
    sheet = run.timesheet
    domain = invariant_domain(MINIMUM_BASE_INVARIANT)

    contracts = EmploymentContract.objects.filter(
        company_id=run.company_id, effective_from__lte=end
    ).select_related("employee")

    rows: list[PayrollLine] = []
    for contract in contracts:
        if contract.ended_on is not None and contract.ended_on < start:
            continue

        hours = TimesheetDay.objects.filter(timesheet=sheet, contract=contract).aggregate(
            total=Sum("hours_worked")
        )["total"]
        if not hours:
            # No hours is not zero pay recorded: it is nothing accrued. A row of
            # zeroes would enter the nominal declaration as a person with income.
            continue

        clauses = clauses_in_force_on(contract.id, end)
        gross = rounding.quantize(
            clauses.base_salary * Decimal(hours) / Decimal(sheet.norm_hours), 2
        )

        rows.append(
            _line(
                run,
                contract,
                LineNature.SALARY_ACCRUAL,
                GROSS,
                Amount(value=gross, basis=clauses.base_salary),
                start,
                end,
            )
        )
        rows.append(
            _line(
                run,
                contract,
                LineNature.EMPLOYER_CHARGE,
                CAS_EMPLOYER,
                _cas_employer(contract, gross, hours, sheet, run.accrual_date, rounding, domain),
                start,
                end,
            )
        )
        cnam = _proportional(CNAM_EMPLOYEE, "cnam.employee_rate", gross, run.accrual_date, rounding)
        rows.append(
            _line(run, contract, LineNature.EMPLOYEE_WITHHOLDING, CNAM_EMPLOYEE, cnam, start, end)
        )
        rows.append(
            _line(
                run,
                contract,
                LineNature.EMPLOYEE_WITHHOLDING,
                INCOME_TAX,
                _income_tax(run, contract, gross, cnam, end, rounding),
                start,
                end,
            )
        )

    PayrollLine.objects.bulk_create(rows)


def _line(
    run: PayrollRun,
    contract: EmploymentContract,
    nature: str,
    component_key: str,
    component: Component,
    start: date,
    end: date,
) -> PayrollLine:
    # Narrowed with `isinstance` rather than a boolean, so the two shapes stay
    # separated for the type checker as well as for the reader: an amount carries
    # its provenance, a refusal carries only a reason, and nothing reads across.
    if isinstance(component, Amount):
        computed: dict[str, Any] = {
            "amount": component.value,
            "unresolved_reason": None,
            "basis": component.basis,
            "rate": component.rate,
            "parameter_id": component.parameter_id,
            "parameter_key": component.parameter_key,
        }
    else:
        computed = {
            "amount": None,
            "unresolved_reason": component.reason,
            "basis": None,
            "rate": None,
            "parameter_id": None,
            "parameter_key": None,
        }

    return PayrollLine(
        tenant_id=run.tenant_id,
        company_id=run.company_id,
        run=run,
        contract=contract,
        employee_id=contract.employee_id,
        nature=nature,
        component_key=component_key,
        work_period_start=start,
        work_period_end=end,
        accrual_date=run.accrual_date,
        **computed,
    )


def _proportional(
    component_key: str,
    parameter_key: str,
    basis: Decimal,
    on: date,
    rounding: Any,
) -> Component:
    rate = _rate_of(parameter_key, on)
    if isinstance(rate, Unresolved):
        return rate
    return Amount(
        value=rounding.quantize(basis * rate.value, 2),
        basis=basis,
        rate=rate.rate,
        parameter_id=rate.parameter_id,
        parameter_key=rate.parameter_key,
    )


def _cas_employer(
    contract: EmploymentContract,
    gross: Decimal,
    hours: Decimal,
    sheet: Timesheet,
    on: date,
    rounding: Any,
    domain: frozenset[str],
) -> Component:
    """The employer's contribution, over a base art. 22 may raise.

    **The domain is a membership test, not an equality** (`OD-106`). Art. 22 para
    (1) covers employment contracts and service relationships; on a civil
    contract the minimum base does not apply at all, and applying it there would
    inflate a real liability -- balanced, `R11` green, invisible.

    **Which rate** follows point 1.1's split by employer sector: 29% budgetary,
    24% private. The category is of the relationship (ADR-068), and so is the
    sector flag it selects with.
    """
    parameter_key = (
        "cnas.employer_rate_budgetary" if contract.budget_funded_employer else "cnas.employer_rate"
    )
    rate = _rate_of(parameter_key, on)
    if isinstance(rate, Unresolved):
        return rate

    basis = gross
    if contract.relationship_type_id in domain:
        minimum = _minimum_base(hours, sheet, on, rounding)
        if isinstance(minimum, Unresolved):
            return minimum
        basis = max(gross, minimum.value)

    return Amount(
        value=rounding.quantize(basis * rate.value, 2),
        basis=basis,
        rate=rate.rate,
        parameter_id=rate.parameter_id,
        parameter_key=rate.parameter_key,
    )


def _minimum_base(hours: Decimal, sheet: Timesheet, on: date, rounding: Any) -> Component:
    """Art. 22 para (1): the base is not below the minimum wage, in proportion to time worked.

    The proportion is the point: a half-time employee does not owe a full month's
    minimum. The second half of the article -- at part time, not less than 25% of
    the contribution at the minimum wage -- is **not implemented here** and must
    not be silently skipped, so its absence is part of the reason returned when
    the parameter is missing, and it is `F2.B2`'s remaining work when it is not.
    """
    wage = _annual_of("labour.minimum_wage_monthly", on)
    if isinstance(wage, Unresolved):
        return Unresolved(
            f"art. 22 alin. (1) cere ca baza să nu fie sub salariul minim, proporţional "
            f"timpului lucrat — iar {wage.reason}. Fără el, baza CAS nu se poate stabili: "
            f"nici brutul, nici minimul nu se pot alege ca răspuns."
        )
    return Amount(
        value=rounding.quantize(wage.value * Decimal(hours) / Decimal(sheet.norm_hours), 2),
        parameter_id=wage.parameter_id,
        parameter_key=wage.parameter_key,
    )


def _income_tax(
    run: PayrollRun,
    contract: EmploymentContract,
    gross: Decimal,
    cnam: Component,
    end: date,
    rounding: Any,
) -> Component:
    """The cumulative method -- HG 697/2014 point 38, not a monthly approximation.

    Point 38 computes **from the start of the fiscal year**: cumulative taxable
    income, cumulative exemptions, cumulative tax, minus what was already
    withheld. The monthly shortcut agrees with it only while nothing varies, and
    "agrees in the simple case" is precisely the kind of plausible wrong number
    this project refuses.

    The exemptions are read **by date** (`exemptions_in_force_on`), month by
    month, because point 18 makes them a history: an exemption granted in May was
    not in force in April, and a run that read today's set would grant it for the
    whole year.
    """
    if isinstance(cnam, Unresolved):
        return Unresolved(
            f"impozitul se calculează pe venitul din care s-a scăzut prima CNAM, iar "
            f"aceea nu s-a putut calcula: {cnam.reason}"
        )

    rate = _rate_of("income_tax.rate_individual", run.accrual_date)
    if isinstance(rate, Unresolved):
        return rate

    year_start = date(run.year, 1, 1)
    prior = PayrollLine.objects.filter(
        company_id=run.company_id,
        employee_id=contract.employee_id,
        work_period_start__gte=year_start,
        work_period_end__lt=date(run.year, run.month, 1),
        run__status=PayrollRunStatus.APPROVED,
    )
    prior_gross = prior.filter(component_key=GROSS).aggregate(t=Sum("amount"))["t"] or Decimal(0)
    prior_cnam = prior.filter(component_key=CNAM_EMPLOYEE).aggregate(t=Sum("amount"))[
        "t"
    ] or Decimal(0)
    prior_tax = prior.filter(component_key=INCOME_TAX).aggregate(t=Sum("amount"))["t"] or Decimal(0)

    opening_taxable = opening_cumulative(
        company_id=run.company_id,
        employee_id=contract.employee_id,
        code=CUM_TAXABLE,
        year=run.year,
    )
    opening_exempt = opening_cumulative(
        company_id=run.company_id,
        employee_id=contract.employee_id,
        code=CUM_EXEMPTIONS,
        year=run.year,
    )
    opening_withheld = opening_cumulative(
        company_id=run.company_id,
        employee_id=contract.employee_id,
        code=CUM_WITHHELD,
        year=run.year,
    )

    exemptions = _cumulative_exemptions(contract.employee_id, run, end)
    if isinstance(exemptions, Unresolved):
        return exemptions

    taxable = (
        opening_taxable
        + prior_gross
        + gross
        - prior_cnam
        - cnam.value
        - opening_exempt
        - exemptions.value
    )
    if taxable < 0:
        taxable = Decimal(0)

    cumulative_tax = rounding.quantize(taxable * rate.value, 2)
    withheld_so_far = opening_withheld + prior_tax
    due = cumulative_tax - withheld_so_far
    if due < 0:
        # A negative month means the year has over-withheld so far. Refunding is
        # a decision this module does not get to take, so it withholds nothing
        # and the surplus stays visible in the cumulative -- rather than a
        # negative line, which ADR-061 forbids on the amount anyway.
        due = Decimal(0)

    return Amount(
        value=due,
        basis=taxable,
        rate=rate.rate,
        parameter_id=rate.parameter_id,
        parameter_key=rate.parameter_key,
    )


def _cumulative_exemptions(employee_id: uuid.UUID, run: PayrollRun, end: date) -> Component:
    """Exemptions granted from the start of the year to this month, month by month.

    A twelfth of the annual amount per month in force, which is how point 38
    accumulates them. Read per month rather than once, because point 18 makes the
    set a history: what applied in April is not what applies in September.
    """
    total = Decimal(0)
    for month in range(1, run.month + 1):
        _, month_end = _month_bounds(run.year, month)
        if month_end > end:
            break
        for entitlement in exemptions_in_force_on(employee_id, month_end):
            parameter_key = EXEMPTION_PARAMETERS.get(entitlement["code"])
            if parameter_key is None:
                return Unresolved(
                    f"codul de scutire {entitlement['code']!r} nu are parametru asociat"
                )
            annual = _annual_of(parameter_key, run.accrual_date)
            if isinstance(annual, Unresolved):
                return Unresolved(
                    f"scutirile intră cumulativ în baza impozitului (HG 697/2014 pct. 38) "
                    f"și {annual.reason}"
                )
            total += annual.value / Decimal(12)
    return Amount(value=total)


def runs_of(company_id: uuid.UUID) -> list[dict[str, Any]]:
    return [
        {
            "id": str(run.id),
            "year": run.year,
            "month": run.month,
            "accrual_date": str(run.accrual_date),
            "status": run.status,
        }
        for run in PayrollRun.objects.filter(company_id=company_id).order_by("-year", "-month")
    ]


def run_in_context(run_id: uuid.UUID) -> dict[str, Any]:
    """The payroll register: one block per person, **totalled on the server** (`C19`).

    The net is derived here and not stored: it is the gross less the
    withholdings, which is the same statement ADR-065 section 8.5 verifies
    against the ledger. A stored net would be a fourth number free to disagree
    with the other three.
    """
    run = PayrollRun.objects.filter(id=run_id).first()
    if run is None:
        raise PayrollRunNotFoundError("no such payroll run in this context")

    people: dict[str, dict[str, Any]] = {}
    for line in run.lines.select_related("employee", "contract").order_by(
        "employee__last_name", "component_key"
    ):
        block = people.setdefault(
            str(line.employee_id),
            {
                "employee_id": str(line.employee_id),
                "employee_name": f"{line.employee.last_name} {line.employee.first_name}",
                "contract_number": line.contract.contract_number,
                "components": [],
                "gross": None,
                "withheld": Decimal(0),
                "employer_charges": Decimal(0),
                "net": None,
                "complete": True,
            },
        )
        block["components"].append(
            {
                "component_key": line.component_key,
                "nature": line.nature,
                "amount": str(line.amount) if line.amount is not None else None,
                "basis": str(line.basis) if line.basis is not None else None,
                "rate": str(line.rate) if line.rate is not None else None,
                "parameter_key": line.parameter_key,
                "unresolved_reason": line.unresolved_reason,
            }
        )
        if line.amount is None:
            block["complete"] = False
            continue
        if line.component_key == GROSS:
            block["gross"] = line.amount
        elif line.nature == LineNature.EMPLOYEE_WITHHOLDING:
            block["withheld"] += line.amount
        elif line.nature == LineNature.EMPLOYER_CHARGE:
            block["employer_charges"] += line.amount

    lines = []
    total_gross = Decimal(0)
    total_withheld = Decimal(0)
    total_charges = Decimal(0)
    for block in people.values():
        gross = block["gross"] or Decimal(0)
        block["net"] = str(gross - block["withheld"]) if block["complete"] else None
        block["gross"] = str(gross)
        block["withheld"] = str(block["withheld"])
        block["employer_charges"] = str(block["employer_charges"])
        total_gross += gross
        lines.append(block)
        if block["complete"]:
            total_withheld += Decimal(block["withheld"])
            total_charges += Decimal(block["employer_charges"])

    unresolved = run.lines.filter(amount__isnull=True).count()
    return {
        "id": str(run.id),
        "year": run.year,
        "month": run.month,
        "accrual_date": str(run.accrual_date),
        "status": run.status,
        "lines": lines,
        "totals": {
            "gross": str(total_gross),
            "withheld": str(total_withheld),
            "employer_charges": str(total_charges),
            "net": str(total_gross - total_withheld),
        },
        "unresolved": unresolved,
        "complete": unresolved == 0,
    }
