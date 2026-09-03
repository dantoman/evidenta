"""A payroll run in the ledger -- ADR-065 sections 7 and 8, one formula per person and component.

**The form is the act's and it is small** (ADR-065 section 8.5). The gross is a
personnel cost against the salary payable; the employer's contribution is the same
cost against the social-insurance payable; what is withheld from the employee moves
from the salary payable to the budget it is owed to. Four formulas per person, and
what remains on 5311 is the net -- the same statement the payslip derives.

**Nothing here knows an account code** (`R15`, ADR-036 section 5.1). The handler
asks for roles; `bind_roles` turns them into accounts through the company's own
bindings at the posting's date, or refuses with the binding's code.

**The destination selects the role, not the binding** (ADR-065 section 7.1, the
second road). The contract says whether the person is administrative, commercial,
or production, and that value names which cost role is asked for. The vocabulary
is code because it is the form of the posting (`R28`); which account the role
means stays data. A line whose contract states no destination is refused by name
-- never defaulted, because a default here balances and is wrong.

**The employee rides on the formula as a dimension** (ADR-065 section 8, ADR-048
section 3.1). It lands on a line only where the account declares the slot; the
role catalogue declares `employee` on 5311 and the two personnel-cost accounts
when the roles are bound, which is what section 8.4 said was missing.

**Granularity is not configurable** (section 8.3): one formula per employee and
component. `merge()` never folds two people, because the slot differs.

**The component vocabulary is the event's contract**, not an import from the
payroll module (`D2`): the payload names `salary.gross`, `cas.employer`,
`cnam.employee`, `income_tax.withheld`, and a key this table does not know is a
refusal -- a new component is classified explicitly, in code, before it posts.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction

from evidenta.accounting.events.registry import (
    HANDLERS,
    EventType,
    HandlerVersion,
    register,
)
from evidenta.accounting.events.services.emission import emit
from evidenta.accounting.events.services.lifecycle import mark_failed, mark_posted
from evidenta.accounting.ledger.services.writing import ParameterStamp, entry_id_of_event
from evidenta.accounting.posting.formula import DimensionValue, RoleFormula, bind_roles
from evidenta.accounting.posting.invariants import Origin
from evidenta.accounting.posting.resolution import selected_treatment
from evidenta.accounting.posting.services.commercial import TREASURY_ROLES
from evidenta.accounting.posting.services.formulas import post_formulas
from evidenta.accounting.posting.services.reversal import (
    HANDLER_REF as REVERSAL_HANDLER_REF,
)
from evidenta.accounting.posting.services.reversal import (
    REVERSAL_SUFFIX,
)
from evidenta.fiscal.parameters.services.resolution import resolve_parameter
from evidenta.platform.api.errors import ApiError
from evidenta.platform.numbering.services.allocation import NumberingError

SOURCE_MODULE = "payroll"
SOURCE_DOCUMENT_TYPE = "payroll.run"

EVENT_RUN_APPROVED = "payroll.run_approved"
HANDLER_RUN_APPROVED = "payroll.run_approved.v1"

ROLE_DATORII_SALARIALE = "DATORII_SALARIALE"
ROLE_DATORII_CAS = "DATORII_CAS"
ROLE_DATORII_CNAM = "DATORII_CNAM"
ROLE_IMPOZIT_VENIT_SALARIU = "IMPOZIT_VENIT_SALARIU"
ROLE_PERSONAL_ADMINISTRATIV = "CHELTUIELI_PERSONAL_ADMINISTRATIV"
ROLE_PERSONAL_COMERCIAL = "CHELTUIELI_PERSONAL_COMERCIAL"
ROLE_PRODUCTIE_DE_BAZA = "PRODUCTIE_DE_BAZA"
ROLE_COSTURI_INDIRECTE = "COSTURI_INDIRECTE_PRODUCTIE"

EMPLOYEE_DIMENSION = "employee"

#: The contract's destination -> the cost role asked for (ADR-065 section 7.1).
#: The two production destinations reuse the roles the production family already
#: binds (section 7: "ambele destinatii de productie refolosesc rolurile existente").
COST_ROLES = {
    "administrative": ROLE_PERSONAL_ADMINISTRATIV,
    "commercial": ROLE_PERSONAL_COMERCIAL,
    "production_direct": ROLE_PRODUCTIE_DE_BAZA,
    "production_indirect": ROLE_COSTURI_INDIRECTE,
}

#: Marker for "the cost role of the contract's destination".
COST = "<cost>"

#: component key -> (debit role, credit role, Romanian description of the line).
#: The descriptions are accounting text (`C33`), fixed here rather than translated.
COMPONENT_TREATMENTS: dict[str, tuple[str, str, str]] = {
    "salary.gross": (COST, ROLE_DATORII_SALARIALE, "Salariu brut calculat"),
    "cas.employer": (
        COST,
        ROLE_DATORII_CAS,
        "Contribuții de asigurări sociale de stat ale angajatorului",
    ),
    "cnam.employee": (
        ROLE_DATORII_SALARIALE,
        ROLE_DATORII_CNAM,
        "Prime de asigurare obligatorie de asistență medicală reținute",
    ),
    "income_tax.withheld": (
        ROLE_DATORII_SALARIALE,
        ROLE_IMPOZIT_VENIT_SALARIU,
        "Impozit pe venit reținut din salariu",
    ),
}

PAYROLL_ROLES = (
    ROLE_DATORII_SALARIALE,
    ROLE_DATORII_CAS,
    ROLE_DATORII_CNAM,
    ROLE_IMPOZIT_VENIT_SALARIU,
    ROLE_PERSONAL_ADMINISTRATIV,
    ROLE_PERSONAL_COMERCIAL,
    ROLE_PRODUCTIE_DE_BAZA,
    ROLE_COSTURI_INDIRECTE,
)

PAYLOAD_FIELDS = (
    "run_id",
    "year",
    "month",
    "accrual_date",
    "work_period_start",
    "work_period_end",
    "lines",
)

LINE_FIELDS = (
    "employee_id",
    "contract_id",
    "contract_number",
    "component_key",
    "amount",
    "cost_destination",
)


class PayrollPostingError(ApiError):
    code = "payroll.posting_malformed"
    status = 422


class PayrollComponentUnknownError(ApiError):
    """A component the treatment table does not classify.

    Refused rather than skipped: a skipped component is a gross without its
    charge, and the entry balances anyway.
    """

    code = "payroll.component_not_classified"
    status = 422


class PayrollCostDestinationMissingError(ApiError):
    """A contract that never said where its cost goes (ADR-065 section 7.1)."""

    code = "payroll.cost_destination_missing"
    status = 422


@dataclass(frozen=True, slots=True)
class PayrollLineFact:
    employee_id: uuid.UUID
    contract_id: uuid.UUID
    contract_number: str
    component_key: str
    amount: Decimal
    cost_destination: str | None

    def as_payload(self) -> dict[str, Any]:
        return {
            "employee_id": str(self.employee_id),
            "contract_id": str(self.contract_id),
            "contract_number": self.contract_number,
            "component_key": self.component_key,
            "amount": str(self.amount),
            "cost_destination": self.cost_destination,
        }


@dataclass(frozen=True, slots=True)
class PayrollRunFact:
    """What the payroll module states about an approved run -- the event's payload.

    ``parameters`` is every fiscal parameter a line stood on, distinct, for the
    stamps of ADR-047: the entry records what it was calculated on, because the
    parameter itself will not remember.
    """

    run_id: uuid.UUID
    year: int
    month: int
    accrual_date: date
    work_period_start: date
    work_period_end: date
    lines: tuple[PayrollLineFact, ...]
    parameters: tuple[tuple[uuid.UUID, str], ...]
    description: str

    def as_payload(self) -> dict[str, Any]:
        return {
            "run_id": str(self.run_id),
            "year": self.year,
            "month": self.month,
            "accrual_date": self.accrual_date.isoformat(),
            "work_period_start": self.work_period_start.isoformat(),
            "work_period_end": self.work_period_end.isoformat(),
            "lines": [line.as_payload() for line in self.lines],
        }


@dataclass(frozen=True, slots=True)
class PayrollPostingResult:
    accounting_event_id: uuid.UUID
    journal_entry_id: uuid.UUID | None
    formulas: int
    posted_now: bool


def _decimal(value: Any, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PayrollPostingError(f"{field} is {value!r}, not an amount") from exc


def _uuid(value: Any, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise PayrollPostingError(f"{field} is {value!r}, not an id") from exc


def recognise_payroll_run(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    accounting_date: date,
    functional_currency: str,
    payload: dict[str, Any],
) -> tuple[RoleFormula, ...]:
    """The pure treatment: per person and component, the pair of roles the act names.

    Pure in the sense the registry needs -- it reads the payload and returns
    formulas, touching no table. A zero amount produces no formula: a formula is
    strictly positive, and an income tax brought to zero by the exemptions is a
    fact of the calculation, not a movement.
    """
    del tenant_id, company_id

    lines = payload.get("lines")
    if not isinstance(lines, list) or not lines:
        raise PayrollPostingError("a run posts its lines; one without any has nothing to post")
    document_date = date.fromisoformat(str(payload["accrual_date"]))

    formulas: list[RoleFormula] = []
    for number, line in enumerate(lines, start=1):
        if not isinstance(line, dict):
            raise PayrollPostingError(f"line {number} is not an object")
        missing = [field for field in LINE_FIELDS if field not in line]
        if missing:
            raise PayrollPostingError(f"line {number} lacks {', '.join(missing)}")
        key = str(line["component_key"])
        treatment = COMPONENT_TREATMENTS.get(key)
        if treatment is None:
            raise PayrollComponentUnknownError(
                f"line {number}: component {key!r} has no posting treatment; "
                f"{sorted(COMPONENT_TREATMENTS)} do. A new component is classified in "
                f"code before it posts, not skipped"
            )
        amount = _decimal(line["amount"], f"line {number} amount")
        if amount < 0:
            raise PayrollPostingError(
                f"line {number}: {key} is {amount}; a payroll amount is not negative, its "
                f"direction is the pair of roles"
            )
        if amount == 0:
            continue
        debit_role, credit_role, description = treatment
        if debit_role == COST:
            destination = line.get("cost_destination")
            if destination not in COST_ROLES:
                raise PayrollCostDestinationMissingError(
                    f"contract {line.get('contract_number')!r} does not say where its cost "
                    f"goes ({destination!r}); one of {sorted(COST_ROLES)} selects the "
                    f"expense account, so it is stated on the contract, not assumed here "
                    f"(ADR-065 section 7.1)"
                )
            debit_role = COST_ROLES[str(destination)]
        employee = _uuid(line["employee_id"], f"line {number} employee_id")
        formulas.append(
            RoleFormula(
                debit_role=debit_role,
                credit_role=credit_role,
                amount=amount,
                currency=functional_currency,
                amount_currency=amount,
                exchange_rate=Decimal(1),
                rate_date=accounting_date,
                document_date=document_date,
                dimensions=(DimensionValue(EMPLOYEE_DIMENSION, employee),),
                description=f"{description} — {line['contract_number']}",
            )
        )
    return tuple(formulas)


HANDLERS[HANDLER_RUN_APPROVED] = recognise_payroll_run

register(
    EventType(
        name=EVENT_RUN_APPROVED,
        payload_fields=PAYLOAD_FIELDS,
        account_roles=PAYROLL_ROLES,
        handlers=(HandlerVersion(implementation_ref=HANDLER_RUN_APPROVED, valid_from=date.min),),
        description=(
            "An approved payroll run: gross and employer charges on personnel cost, "
            "withholdings from the salary payable to the budgets, one formula per person."
        ),
    )
)


def _stamps(
    parameters: Sequence[tuple[uuid.UUID, str]], accounting_date: date
) -> tuple[ParameterStamp, ...]:
    """One stamp per parameter the run stood on, as the row stands now (ADR-047).

    Resolved again by key on the accounting date, the way the settlement handler
    stamps the scale: the row is the same one the calculation read (`R18`, one
    row in force per date), and its confidence column is what the entry records.
    A key that no longer resolves is a refusal, not a missing stamp -- the run
    computed on a row the ledger cannot name.
    """
    now = datetime.now(UTC)
    stamps = []
    for parameter_id, key in parameters:
        row = resolve_parameter(key, accounting_date)
        if uuid.UUID(str(row.pk)) != parameter_id:
            raise PayrollPostingError(
                f"parameter {key!r} resolves to {row.pk} on {accounting_date}, but the run "
                f"computed on {parameter_id}; a run is posted on the parameters it read, "
                f"so it is recomputed first"
            )
        stamps.append(
            ParameterStamp(
                parameter_id=parameter_id,
                parameter_key=key,
                effective_date=accounting_date,
                confidence=row.source_confidence,
                resolved_at=now,
            )
        )
    return tuple(stamps)


def post_payroll_run(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    functional_currency: str,
    fact: PayrollRunFact,
    actor_user_id: uuid.UUID,
    request_id: str,
    capability_snapshot: dict[str, Any],
    occurred_at: datetime | None = None,
) -> PayrollPostingResult:
    """Record the approved run as an event and post it -- the shape every family uses.

    Emit under an idempotency key (`R19`, on the event and not on the endpoint):
    the run's identity plus the event type, because a run is approved once and a
    re-posting after a reversal is a different event. Select the treatment by
    date and profile (`R17`, `R26`); run the pure handler; bind the roles; post;
    mark. The accounting date is the accrual date (ADR-065 section 6), the work
    period rides on the payload for the declaration that reads it later.
    """
    event, created = emit(
        tenant_id=tenant_id,
        company_id=company_id,
        event_type=EVENT_RUN_APPROVED,
        source_module=SOURCE_MODULE,
        source_document_type=SOURCE_DOCUMENT_TYPE,
        source_document_id=fact.run_id,
        occurred_at=occurred_at or datetime.now(UTC),
        accounting_date=fact.accrual_date,
        idempotency_key=f"{EVENT_RUN_APPROVED}:{fact.run_id}",
        payload=fact.as_payload(),
        capability_snapshot=capability_snapshot,
        actor_user_id=actor_user_id,
        request_id=request_id,
    )
    if not created:
        posted = entry_id_of_event(event.id)
        if posted is not None or event.status == "posted":
            return PayrollPostingResult(event.id, posted, 0, posted_now=False)

    treatment = selected_treatment(EVENT_RUN_APPROVED, fact.accrual_date, capability_snapshot)
    produced = treatment.handler(
        tenant_id=tenant_id,
        company_id=company_id,
        accounting_date=fact.accrual_date,
        functional_currency=functional_currency,
        payload=event.payload,
    )
    formulas: Sequence[RoleFormula] = tuple(produced)
    if not formulas:
        # Every amount was zero: a month of unpaid leave. The event stands as the
        # record that the run was approved; there is no movement to write.
        mark_posted(event.id)
        return PayrollPostingResult(event.id, None, 0, posted_now=True)

    try:
        with transaction.atomic():
            bound = bind_roles(company_id, fact.accrual_date, formulas)
            result = post_formulas(
                tenant_id=tenant_id,
                company_id=company_id,
                accounting_date=fact.accrual_date,
                functional_currency=functional_currency,
                accounting_event_id=event.id,
                origin=Origin(
                    module=SOURCE_MODULE,
                    document_type=SOURCE_DOCUMENT_TYPE,
                    document_id=fact.run_id,
                ),
                rule_ref=treatment.ref,
                description=fact.description,
                request_id=request_id,
                actor_user_id=actor_user_id,
                formulas=bound,
                parameter_stamps=_stamps(fact.parameters, fact.accrual_date),
            )
    except (ApiError, NumberingError) as refusal:
        mark_failed(event.id, code=refusal.code, detail={"event_type": EVENT_RUN_APPROVED})
        raise
    mark_posted(event.id)
    return PayrollPostingResult(event.id, result.journal_entry_id, result.formulas, posted_now=True)


# --- The payment of the net ---------------------------------------------------
#
# What the run left on 5311 per person leaves through the till or the bank
# account, and the person rides on the debit line exactly as on the accrual
# (ADR-065 section 8): the two together are what makes the balance of 5311 per
# employee readable. The treasury side is ADR-073 section 5 -- the account is the
# instrument's, `cash` or `bank`, and the map from the word to the role is the
# same one the treasury family uses, imported so there is one and not two.

SOURCE_DOCUMENT_TYPE_PAYMENT = "payroll.payment"

EVENT_SALARIES_PAID = "payroll.salaries_paid"
HANDLER_SALARIES_PAID = "payroll.salaries_paid.v1"

SALARY_PAYMENT_ROLES = (ROLE_DATORII_SALARIALE, *TREASURY_ROLES.values())

PAYMENT_PAYLOAD_FIELDS = (
    "payment_id",
    "run_id",
    "year",
    "month",
    "paid_on",
    "treasury_account",
    "lines",
)

PAYMENT_LINE_FIELDS = ("employee_id", "amount")


class SalaryPaymentPostingError(ApiError):
    code = "payroll.payment_posting_malformed"
    status = 422


class SalaryPaymentTreasuryMissingError(ApiError):
    """The document does not say where the money left from (ADR-073 section 5)."""

    code = "payroll.treasury_account_missing"
    status = 422


@dataclass(frozen=True, slots=True)
class SalaryPaymentLineFact:
    employee_id: uuid.UUID
    amount: Decimal

    def as_payload(self) -> dict[str, Any]:
        return {"employee_id": str(self.employee_id), "amount": str(self.amount)}


@dataclass(frozen=True, slots=True)
class SalaryPaymentFact:
    """What the payroll module states about a salary payment -- the event's payload."""

    payment_id: uuid.UUID
    run_id: uuid.UUID
    year: int
    month: int
    paid_on: date
    treasury_account: str
    lines: tuple[SalaryPaymentLineFact, ...]
    description: str

    def as_payload(self) -> dict[str, Any]:
        return {
            "payment_id": str(self.payment_id),
            "run_id": str(self.run_id),
            "year": self.year,
            "month": self.month,
            "paid_on": self.paid_on.isoformat(),
            "treasury_account": self.treasury_account,
            "lines": [line.as_payload() for line in self.lines],
        }


def recognise_salary_payment(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    accounting_date: date,
    functional_currency: str,
    payload: dict[str, Any],
) -> tuple[RoleFormula, ...]:
    """Per person: the salary payable against the treasury account. One formula each.

    Pure, like the accrual's handler. It does not know how much the run left for
    the person -- that is the payroll module's check, made before the fact is
    stated -- and it refuses only what no fact may say: no lines, a line without
    a person, an amount that is not strictly positive, a document that does not
    say where the money left from.
    """
    del tenant_id, company_id

    where = payload.get("treasury_account")
    if where not in TREASURY_ROLES:
        raise SalaryPaymentTreasuryMissingError(
            f"treasury_account is {where!r}; the money left the till or the bank "
            f"account, and which one is stated on the document ({sorted(TREASURY_ROLES)})"
        )
    lines = payload.get("lines")
    if not isinstance(lines, list) or not lines:
        raise SalaryPaymentPostingError("a payment posts its lines; one without any pays nobody")
    document_date = date.fromisoformat(str(payload["paid_on"]))
    description = f"Salariu net achitat {int(payload['year'])}-{int(payload['month']):02d}"

    formulas: list[RoleFormula] = []
    for number, line in enumerate(lines, start=1):
        if not isinstance(line, dict):
            raise SalaryPaymentPostingError(f"line {number} is not an object")
        missing = [field for field in PAYMENT_LINE_FIELDS if field not in line]
        if missing:
            raise SalaryPaymentPostingError(f"line {number} lacks {', '.join(missing)}")
        amount = _decimal(line["amount"], f"line {number} amount")
        if amount <= 0:
            raise SalaryPaymentPostingError(
                f"line {number}: amount is {amount}; a person who receives nothing on this "
                f"payment has no line, not a line of zero"
            )
        employee = _uuid(line["employee_id"], f"line {number} employee_id")
        formulas.append(
            RoleFormula(
                debit_role=ROLE_DATORII_SALARIALE,
                credit_role=TREASURY_ROLES[str(where)],
                amount=amount,
                currency=functional_currency,
                amount_currency=amount,
                exchange_rate=Decimal(1),
                rate_date=accounting_date,
                document_date=document_date,
                dimensions=(DimensionValue(EMPLOYEE_DIMENSION, employee),),
                description=description,
            )
        )
    return tuple(formulas)


HANDLERS[HANDLER_SALARIES_PAID] = recognise_salary_payment

register(
    EventType(
        name=EVENT_SALARIES_PAID,
        payload_fields=PAYMENT_PAYLOAD_FIELDS,
        account_roles=SALARY_PAYMENT_ROLES,
        handlers=(HandlerVersion(implementation_ref=HANDLER_SALARIES_PAID, valid_from=date.min),),
        description=(
            "Salaries paid: the salary payable, per person, against the till or the bank account."
        ),
    )
)


def post_salary_payment(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    functional_currency: str,
    fact: SalaryPaymentFact,
    actor_user_id: uuid.UUID,
    request_id: str,
    capability_snapshot: dict[str, Any],
    occurred_at: datetime | None = None,
) -> PayrollPostingResult:
    """Record the payment as an event and post it -- the same sequence as the run.

    The idempotency key is the document's identity plus the event type (`R19`,
    ADR-073 section 8): a payment is posted once, and the same fact stated again
    returns the first entry. The accounting date is the day the money left.
    No parameter stamps: nothing here was computed on a rate.
    """
    event, created = emit(
        tenant_id=tenant_id,
        company_id=company_id,
        event_type=EVENT_SALARIES_PAID,
        source_module=SOURCE_MODULE,
        source_document_type=SOURCE_DOCUMENT_TYPE_PAYMENT,
        source_document_id=fact.payment_id,
        occurred_at=occurred_at or datetime.now(UTC),
        accounting_date=fact.paid_on,
        idempotency_key=f"{EVENT_SALARIES_PAID}:{fact.payment_id}",
        payload=fact.as_payload(),
        capability_snapshot=capability_snapshot,
        actor_user_id=actor_user_id,
        request_id=request_id,
    )
    if not created:
        posted = entry_id_of_event(event.id)
        if posted is not None or event.status == "posted":
            return PayrollPostingResult(event.id, posted, 0, posted_now=False)

    treatment = selected_treatment(EVENT_SALARIES_PAID, fact.paid_on, capability_snapshot)
    produced = treatment.handler(
        tenant_id=tenant_id,
        company_id=company_id,
        accounting_date=fact.paid_on,
        functional_currency=functional_currency,
        payload=event.payload,
    )
    formulas: Sequence[RoleFormula] = tuple(produced)

    try:
        with transaction.atomic():
            bound = bind_roles(company_id, fact.paid_on, formulas)
            result = post_formulas(
                tenant_id=tenant_id,
                company_id=company_id,
                accounting_date=fact.paid_on,
                functional_currency=functional_currency,
                accounting_event_id=event.id,
                origin=Origin(
                    module=SOURCE_MODULE,
                    document_type=SOURCE_DOCUMENT_TYPE_PAYMENT,
                    document_id=fact.payment_id,
                ),
                rule_ref=treatment.ref,
                description=fact.description,
                request_id=request_id,
                actor_user_id=actor_user_id,
                formulas=bound,
            )
    except (ApiError, NumberingError) as refusal:
        mark_failed(event.id, code=refusal.code, detail={"event_type": EVENT_SALARIES_PAID})
        raise
    mark_posted(event.id)
    return PayrollPostingResult(event.id, result.journal_entry_id, result.formulas, posted_now=True)


# --- the storno pairs ---------------------------------------------------------------
#
# `R14`: a payroll entry that was wrong -- a run approved on the wrong hours, a
# payment posted twice -- is corrected by a reversal, never by an UPDATE (`R10`).
# The reversal service selects the pair by suffix (`<domain>.<action>_reversed`)
# and refuses a type nobody registered, so the pairs are registered here, with
# the mirror handler: a storno derives no accounts and names no roles, it uses
# the ones already posted. What it does NOT do is move the run or the payment
# back to draft: the document's state is the module's, the entry's is the
# ledger's, and the accountant recomputes into a new run after the correction.
for _original in (EVENT_RUN_APPROVED, EVENT_SALARIES_PAID):
    register(
        EventType(
            name=_original + REVERSAL_SUFFIX,
            payload_fields=("reverses_entry_id", "reason"),
            account_roles=(),
            handlers=(
                HandlerVersion(implementation_ref=REVERSAL_HANDLER_REF, valid_from=date.min),
            ),
            description=(
                f"The cancellation of a {_original} entry: the original's lines with "
                f"debit and credit swapped, linked to the source document and to the "
                f"entry it cancels (R14)."
            ),
        )
    )
