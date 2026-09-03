"""Paying the net -- the second half of ADR-065 section 8, through treasury.

**What the run left on the salary payable is what this pays.** The accrual put
the gross on 5311 per person and moved the withholdings off it; what remains is
the net, and it is not stored anywhere (section 8.5) -- it is derived here from
the run's lines exactly as the register derives it, so the payment and the
payslip cannot disagree about what a person is owed.

**A line may be less than the net, never more.** Reduced or removed while the
document is a draft: an advance already handed over, a person paid later. Above
what the run left for that person -- counting what earlier payments of the same
run already posted -- the payment is refused by name (`payroll.overpayment`),
because a debit on 5311 past its balance is a receivable from the employee that
nobody decided on. The check is the payroll module's, made on its own tables
before the fact is stated; the engine's handler is pure and does not know the
net.

**Only a run that reached the ledger can be paid** (`payroll.run_not_posted`).
Paying a run whose accrual was never posted would credit the till against a
liability that does not exist in the books.

**The bank's list is a file, built here from the same rows** (`C20`): name,
IDNP, IBAN, amount, one row per person with something to receive. The bank's
own format is an adaptor (`OD-27`); the generic CSV is the reversible default.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Sum

from evidenta.accounting.events.services.lineage import events_of_document
from evidenta.accounting.posting.services.payroll import (
    SOURCE_DOCUMENT_TYPE,
    SOURCE_DOCUMENT_TYPE_PAYMENT,
    SalaryPaymentFact,
    SalaryPaymentLineFact,
    post_salary_payment,
)
from evidenta.operations.payroll.models import (
    LineNature,
    PayrollRun,
    PayrollRunStatus,
    SalaryPayment,
    SalaryPaymentLine,
    SalaryPaymentStatus,
    SalaryTreasuryAccount,
)
from evidenta.operations.payroll.services.runs import GROSS, PayrollRunNotFoundError
from evidenta.platform.api.errors import ApiError
from evidenta.platform.audit.services.recording import record
from evidenta.platform.capabilities.services.profile import active_profile
from evidenta.platform.documents.services.csv import csv_document
from evidenta.platform.tenancy.services.companies import functional_currency


class PayrollRunNotPostedError(ApiError):
    """The run's accrual is not in the books, so there is nothing on 5311 to pay."""

    code = "payroll.run_not_posted"
    status = 409


class SalaryOverpaymentError(ApiError):
    """A line above what the run left for that person, after earlier payments."""

    code = "payroll.overpayment"
    status = 422


class SalaryPaymentNotFoundError(ApiError):
    code = "payroll.payment_not_found"
    status = 404


class SalaryPaymentNotDraftError(ApiError):
    code = "payroll.payment_not_draft"
    status = 409


class SalaryPaymentMalformedError(ApiError):
    code = "payroll.payment_malformed"
    status = 422


class SalaryPaymentEmptyError(ApiError):
    """Nobody left to pay, or a document with no lines asked to post."""

    code = "payroll.payment_empty"
    status = 409


#: The bank list's headings -- accounting text, Romanian, fixed here (`C33`).
BANK_LIST_HEADINGS = ("Nr.", "Nume și prenume", "IDNP", "IBAN", "Suma")


@dataclass(frozen=True, slots=True)
class Payee:
    """One person on the run: what the run left them, and what was already paid."""

    employee_id: uuid.UUID
    name: str
    idnp: str | None
    bank_iban: str | None
    net: Decimal
    paid: Decimal

    @property
    def remaining(self) -> Decimal:
        return self.net - self.paid


def _run(run_id: uuid.UUID) -> PayrollRun:
    run = PayrollRun.objects.filter(id=run_id).first()
    if run is None:
        raise PayrollRunNotFoundError("no such payroll run in this context")
    return run


def _payment(payment_id: uuid.UUID) -> SalaryPayment:
    payment = SalaryPayment.objects.filter(id=payment_id).select_related("run").first()
    if payment is None:
        raise SalaryPaymentNotFoundError("no such salary payment in this context")
    return payment


def _run_is_posted(run: PayrollRun) -> bool:
    events = events_of_document(SOURCE_DOCUMENT_TYPE, run.id)
    return bool(events) and events[-1].status == "posted"


def _require_posted(run: PayrollRun) -> None:
    if run.status != PayrollRunStatus.APPROVED or not _run_is_posted(run):
        raise PayrollRunNotPostedError(
            f"{run.year}-{run.month:02d} is {run.status} and its accrual is not in the "
            f"books; a payment settles what the accrual put on the salary payable, so "
            f"the run is approved and posted first"
        )


def _checked_account(treasury_account: str) -> str:
    if treasury_account not in SalaryTreasuryAccount.values:
        raise SalaryPaymentMalformedError(
            f"treasury_account is {treasury_account!r}; it selects the treasury role, "
            f"so it is chosen from {sorted(SalaryTreasuryAccount.values)}"
        )
    return treasury_account


def payees_of(run: PayrollRun) -> dict[uuid.UUID, Payee]:
    """Every person on the run with the net the run left them and what is already paid.

    The net is derived, not read: gross less the employee's withholdings, the
    same arithmetic as the register (`run_in_context`) and the ledger (section
    8.5). `paid` counts only **posted** payments -- a draft pays nobody yet.
    """
    nets: dict[uuid.UUID, dict[str, Any]] = {}
    for line in run.lines.select_related("employee").order_by(
        "employee__last_name", "employee__first_name"
    ):
        if line.amount is None:
            continue
        block = nets.setdefault(
            line.employee_id,
            {
                "name": f"{line.employee.last_name} {line.employee.first_name}",
                "idnp": line.employee.idnp,
                "bank_iban": line.employee.bank_iban,
                "net": Decimal(0),
            },
        )
        if line.component_key == GROSS:
            block["net"] += line.amount
        elif line.nature == LineNature.EMPLOYEE_WITHHOLDING:
            block["net"] -= line.amount

    paid = {
        row["employee_id"]: row["total"]
        for row in SalaryPaymentLine.objects.filter(
            payment__run_id=run.id, payment__status=SalaryPaymentStatus.POSTED
        )
        .values("employee_id")
        .annotate(total=Sum("amount"))
    }
    return {
        employee_id: Payee(
            employee_id=employee_id,
            name=block["name"],
            idnp=block["idnp"],
            bank_iban=block["bank_iban"],
            net=block["net"],
            paid=paid.get(employee_id) or Decimal(0),
        )
        for employee_id, block in nets.items()
    }


def _checked_lines(
    run: PayrollRun, lines: Sequence[dict[str, Any]]
) -> list[tuple[uuid.UUID, Decimal]]:
    """The lines a draft may hold: people of this run, each once, within what is left."""
    payees = payees_of(run)
    seen: set[uuid.UUID] = set()
    checked: list[tuple[uuid.UUID, Decimal]] = []
    for number, line in enumerate(lines, start=1):
        try:
            employee_id = uuid.UUID(str(line["employee_id"]))
            amount = Decimal(str(line["amount"]))
        except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
            raise SalaryPaymentMalformedError(
                f"line {number} is not a person and an amount"
            ) from exc
        if employee_id in seen:
            raise SalaryPaymentMalformedError(
                f"line {number}: the same person twice on one payment; a second amount "
                f"for the same person is a second document"
            )
        seen.add(employee_id)
        payee = payees.get(employee_id)
        if payee is None:
            raise SalaryPaymentMalformedError(
                f"line {number}: {employee_id} is not on run {run.year}-{run.month:02d}"
            )
        if amount <= 0:
            raise SalaryPaymentMalformedError(
                f"line {number}: {payee.name} would receive {amount}; a person who receives "
                f"nothing is removed from the payment, not paid zero"
            )
        if amount > payee.remaining:
            raise SalaryOverpaymentError(
                f"{payee.name}: {amount} exceeds the {payee.remaining} the run left "
                f"(net {payee.net}, already paid {payee.paid}). A debit on the salary "
                f"payable past its balance is a receivable from the employee, which "
                f"nobody decided on"
            )
        checked.append((employee_id, amount))
    return checked


def create_payment(*, run_id: uuid.UUID, paid_on: date, treasury_account: str) -> SalaryPayment:
    """Open a draft over everyone the run still owes, each at what is left.

    Refused for a run that is not in the books; refused when nobody is owed
    anything -- a payment of nothing is not a document.
    """
    run = _run(run_id)
    _require_posted(run)
    where = _checked_account(treasury_account)
    due = [payee for payee in payees_of(run).values() if payee.remaining > 0]
    if not due:
        raise SalaryPaymentEmptyError(
            f"everyone on {run.year}-{run.month:02d} has been paid in full; there is "
            f"nothing left to pay"
        )

    with transaction.atomic():
        payment = SalaryPayment.objects.create(
            tenant_id=run.tenant_id,
            company_id=run.company_id,
            run=run,
            paid_on=paid_on,
            treasury_account=where,
        )
        SalaryPaymentLine.objects.bulk_create(
            [
                SalaryPaymentLine(
                    tenant_id=run.tenant_id,
                    company_id=run.company_id,
                    payment=payment,
                    employee_id=payee.employee_id,
                    amount=payee.remaining,
                )
                for payee in due
            ]
        )

    record(
        action="payroll.payment_created",
        entity_type="salary_payment",
        entity_id=payment.id,
        company_id=run.company_id,
        new_value={
            "run_id": str(run.id),
            "paid_on": str(paid_on),
            "treasury_account": where,
            "lines": len(due),
        },
    )
    return payment


def update_payment(
    *,
    payment_id: uuid.UUID,
    paid_on: date | None = None,
    treasury_account: str | None = None,
    lines: Sequence[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Change the date, the account, or the lines -- while draft, and replacing.

    Lines are replaced rather than patched, for the reason the run's recompute
    gives: a merge would leave a line behind for a person the caller meant to
    remove, indistinguishable from a real one.
    """
    payment = _payment(payment_id)
    if payment.status != SalaryPaymentStatus.DRAFT:
        raise SalaryPaymentNotDraftError(
            f"the payment of {payment.paid_on} is {payment.status}; what was posted is "
            f"what was paid"
        )
    checked = _checked_lines(payment.run, lines) if lines is not None else None

    with transaction.atomic():
        fields: list[str] = []
        if paid_on is not None:
            payment.paid_on = paid_on
            fields.append("paid_on")
        if treasury_account is not None:
            payment.treasury_account = _checked_account(treasury_account)
            fields.append("treasury_account")
        if fields:
            payment.save(update_fields=[*fields, "updated_at"])
        if checked is not None:
            payment.lines.all().delete()
            SalaryPaymentLine.objects.bulk_create(
                [
                    SalaryPaymentLine(
                        tenant_id=payment.tenant_id,
                        company_id=payment.company_id,
                        payment=payment,
                        employee_id=employee_id,
                        amount=amount,
                    )
                    for employee_id, amount in checked
                ]
            )

    record(
        action="payroll.payment_updated",
        entity_type="salary_payment",
        entity_id=payment.id,
        company_id=payment.company_id,
        new_value={
            "paid_on": str(payment.paid_on),
            "treasury_account": payment.treasury_account,
            "lines": len(checked) if checked is not None else None,
        },
    )
    return payment_in_context(payment.id)


def _fact_of(payment: SalaryPayment) -> SalaryPaymentFact:
    run = payment.run
    return SalaryPaymentFact(
        payment_id=payment.id,
        run_id=run.id,
        year=run.year,
        month=run.month,
        paid_on=payment.paid_on,
        treasury_account=payment.treasury_account,
        lines=tuple(
            SalaryPaymentLineFact(employee_id=line.employee_id, amount=line.amount)
            for line in payment.lines.order_by("employee_id")
        ),
        # Romanian, and in the register (`C33`).
        description=f"Plata salariilor {run.year}-{run.month:02d}",
    )


def post_payment(
    *, payment_id: uuid.UUID, actor_user_id: uuid.UUID, request_id: str = "payroll"
) -> dict[str, Any]:
    """Freeze the document and post it, in one transaction.

    The overpayment check is made again here, against what is posted **now**:
    a draft opened before another payment of the same run was posted may have
    become too large in the meantime. A refusal by the engine -- an unbound
    role, a closed month -- rolls the freeze back with it. Posting a document
    already posted states the same fact again and gets the first entry back
    (`R19`), never a second one.
    """
    payment = _payment(payment_id)
    run = payment.run
    if payment.status == SalaryPaymentStatus.POSTED:
        post_salary_payment(
            tenant_id=payment.tenant_id,
            company_id=payment.company_id,
            functional_currency=functional_currency(payment.company_id),
            fact=_fact_of(payment),
            actor_user_id=actor_user_id,
            request_id=request_id,
            capability_snapshot=active_profile(payment.company_id, payment.paid_on).as_snapshot(),
        )
        return payment_in_context(payment.id)

    _require_posted(run)
    lines = [
        {"employee_id": line.employee_id, "amount": line.amount} for line in payment.lines.all()
    ]
    if not lines:
        raise SalaryPaymentEmptyError("a payment with no lines pays nobody; it is not posted")

    with transaction.atomic():
        # The overpayment check reads "already paid" for the run; two drafts of
        # the same run posted at once would each read the same total and both
        # pass. Locking the run serialises the posters, so the second reads the
        # first's posted lines and is refused (the schema reviewer's finding).
        run = PayrollRun.objects.select_for_update(of=("self",)).get(id=run.id)
        _checked_lines(run, lines)
        payment.status = SalaryPaymentStatus.POSTED
        payment.posted_by_user_id = actor_user_id
        payment.posted_at = datetime.now(UTC)
        payment.save(update_fields=["status", "posted_by_user_id", "posted_at", "updated_at"])

        record(
            action="payroll.payment_posted",
            entity_type="salary_payment",
            entity_id=payment.id,
            company_id=payment.company_id,
            new_value={"run_id": str(run.id), "paid_on": str(payment.paid_on)},
        )
        post_salary_payment(
            tenant_id=payment.tenant_id,
            company_id=payment.company_id,
            functional_currency=functional_currency(payment.company_id),
            fact=_fact_of(payment),
            actor_user_id=actor_user_id,
            request_id=request_id,
            capability_snapshot=active_profile(payment.company_id, payment.paid_on).as_snapshot(),
        )
    return payment_in_context(payment.id)


def _posting_of(payment: SalaryPayment) -> dict[str, Any] | None:
    events = events_of_document(SOURCE_DOCUMENT_TYPE_PAYMENT, payment.id)
    if not events:
        return None
    last = events[-1]
    return {
        "accounting_event_id": str(last.id),
        "status": last.status,
        "posted_at": last.posted_at.isoformat() if last.posted_at else None,
    }


def _summary(payment: SalaryPayment, total: Decimal, count: int) -> dict[str, Any]:
    return {
        "id": str(payment.id),
        "run_id": str(payment.run_id),
        "paid_on": str(payment.paid_on),
        "treasury_account": payment.treasury_account,
        "status": payment.status,
        "posted_at": payment.posted_at.isoformat() if payment.posted_at else None,
        "total": str(total),
        "lines_count": count,
        "posting": _posting_of(payment),
    }


def payments_of_run(run_id: uuid.UUID) -> list[dict[str, Any]]:
    """The payments of one run, newest first, **totalled on the server** (`C19`)."""
    rows = (
        SalaryPayment.objects.filter(run_id=run_id)
        .annotate(total=Sum("lines__amount"))
        .order_by("-paid_on", "-created_at")
    )
    return [
        _summary(
            payment,
            payment.total or Decimal(0),  # type: ignore[attr-defined]
            payment.lines.count(),
        )
        for payment in rows
    ]


def payment_in_context(payment_id: uuid.UUID) -> dict[str, Any]:
    """The document with its lines, each beside what the run left the person."""
    payment = _payment(payment_id)
    record(
        action="payroll.payment_read",
        entity_type="salary_payment",
        entity_id=payment.id,
        company_id=payment.company_id,
    )
    payees = payees_of(payment.run)
    lines = []
    total = Decimal(0)
    for line in payment.lines.select_related("employee").order_by(
        "employee__last_name", "employee__first_name"
    ):
        payee = payees.get(line.employee_id)
        total += line.amount
        lines.append(
            {
                "employee_id": str(line.employee_id),
                "employee_name": f"{line.employee.last_name} {line.employee.first_name}",
                "idnp": line.employee.idnp,
                "bank_iban": line.employee.bank_iban,
                "net": str(payee.net) if payee else None,
                "already_paid": str(payee.paid) if payee else None,
                "amount": str(line.amount),
            }
        )
    body = _summary(payment, total, len(lines))
    body.update(
        {
            "year": payment.run.year,
            "month": payment.run.month,
            "lines": lines,
            "totals": {"amount": str(total)},
        }
    )
    return body


def bank_list_csv(run_id: uuid.UUID, *, payment_id: uuid.UUID | None = None) -> tuple[str, bytes]:
    """The bank's payment list: name, IDNP, IBAN, amount -- one row per person owed.

    Without a payment: what the run left each person (the net), which is the
    list an accountant hands to the bank for the month. With one: exactly that
    document's lines, so the file and the entry cannot disagree (`C20`). Rows with
    nothing to receive are absent, not zero.
    """
    run = _run(run_id)
    payees = payees_of(run)
    if payment_id is None:
        amounts = {payee.employee_id: payee.net for payee in payees.values()}
    else:
        payment = _payment(payment_id)
        if payment.run_id != run.id:
            raise SalaryPaymentNotFoundError("that payment is not of this run")
        amounts = {line.employee_id: line.amount for line in payment.lines.all()}

    rows: list[Sequence[object]] = []
    for payee in sorted(payees.values(), key=lambda p: p.name):
        amount = amounts.get(payee.employee_id)
        if amount is None or amount <= 0:
            continue
        rows.append((len(rows) + 1, payee.name, payee.idnp, payee.bank_iban, amount))
    filename = f"lista-de-plata-{run.year}-{run.month:02d}.csv"
    # IDNP and IBAN leave the system in this file: the read is audited like every
    # other read of personal data in this module (`F2.B1`), with the run as the
    # entity and the document, if one was named, in the value.
    record(
        action="payroll.bank_list_exported",
        entity_type="payroll_run",
        entity_id=run.id,
        company_id=run.company_id,
        new_value={"payment_id": str(payment_id) if payment_id else None, "rows": len(rows)},
    )
    return filename, csv_document(BANK_LIST_HEADINGS, rows)
