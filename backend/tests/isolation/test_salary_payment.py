"""Paying the salaries of an approved run reaches the ledger -- `C12`, with accounts and amounts.

ADR-065 section 8, second half, through treasury (ADR-073 section 5): what the
accrual left on the salary payable per person leaves through the till or the
bank account, one formula per person, the person on the debit line. Rates are
the nonsense of `test_payroll_run.py`; what is under test is the chain.

Seven claims:

1. **Paying everyone clears 5311 per person** and credits the treasury account by
   the total; `employee_id` is on the 5311 line and not on the treasury line.
2. **Posting twice posts once** (`R19`): the second call returns the first entry.
3. **A run that is not in the books refuses the payment by name.**
4. **An amount above what the run left is refused by name**, on the draft and
   again at posting -- a draft opened before another payment posted is checked
   against what is posted *now*, and stays a draft.
5. **Two partial payments add up to the net**, and a third has nobody to pay.
6. **The bank's list** carries name, IDNP, IBAN and the amount in the Romanian
   form, one row per person owed.
7. **Another tenant sees nothing** of the payment (IZ).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from evidenta.accounting.events.models import AccountingEvent
from evidenta.accounting.ledger.models import JournalEntry, JournalLine
from evidenta.operations.payroll.models import SalaryPayment, SalaryPaymentLine
from evidenta.operations.payroll.services.payments import (
    PayrollRunNotPostedError,
    SalaryOverpaymentError,
    SalaryPaymentEmptyError,
    SalaryPaymentNotFoundError,
    bank_list_csv,
    create_payment,
    payment_in_context,
    payments_of_run,
    post_payment,
    update_payment,
)
from evidenta.operations.payroll.services.people import set_bank_iban
from evidenta.operations.payroll.services.runs import approve, run_in_context
from evidenta.platform.documents.formatting import decimal_ro
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.isolation.test_line_rounding import source  # noqa: F401 -- payroll_world needs it
from tests.isolation.test_payroll_posting import _run, payroll_world  # noqa: F401

pytestmark = pytest.mark.django_db(databases=["default", "migration", "refdata"])

IBAN = "MD24AG000225100013104168"
PAID_ON = date(2026, 3, 31)


def _posted_run(world: dict[str, Any]) -> tuple[Any, uuid.UUID, Decimal]:
    """An approved, posted March: the run, the one person on it, and their net."""
    run, _contract = _run(world)
    approve(run_id=run.id, approver_user_id=world["user"])
    register = run_in_context(run.id)
    assert register["posting"]["status"] == "posted"
    employee_id = uuid.UUID(register["lines"][0]["employee_id"])
    return run, employee_id, Decimal(register["totals"]["net"])


def _payment_lines(payment_id: uuid.UUID) -> tuple[Any, list[Any]]:
    event = AccountingEvent.objects.get(
        source_document_type="payroll.payment", source_document_id=payment_id
    )
    assert event.status == "posted"
    entry = JournalEntry.objects.get(accounting_event_id=event.id)
    lines = JournalLine.objects.filter(journal_entry_id=entry.id).order_by("line_number")
    return entry, list(lines)


def _balance_5311(world: dict[str, Any], employee_id: uuid.UUID) -> Decimal:
    rows = JournalLine.objects.filter(
        company_id=world["company"],
        account_id=world["accounts"]["5311"],
        employee_id=employee_id,
    )
    return sum((row.credit - row.debit for row in rows), Decimal(0))


def test_paying_everyone_clears_the_salary_payable_per_person(
    payroll_world: dict[str, Any],  # noqa: F811
) -> None:
    world = payroll_world
    with tenant_context(world["context"]):
        run, employee_id, net = _posted_run(world)
        assert net > 0
        assert _balance_5311(world, employee_id) == net

        payment = create_payment(run_id=run.id, paid_on=PAID_ON, treasury_account="bank")
        body = post_payment(payment_id=payment.id, actor_user_id=world["user"])
        assert body["status"] == "posted"
        assert body["posting"]["status"] == "posted"
        assert body["totals"]["amount"] == str(net)

        _entry, lines = _payment_lines(payment.id)
        assert _balance_5311(world, employee_id) == 0

    codes = world["codes"]
    debits = {(codes[line.account_id], line.debit) for line in lines if line.debit > 0}
    credits = {(codes[line.account_id], line.credit) for line in lines if line.credit > 0}
    assert debits == {("5311", net)}
    assert credits == {("2421", net)}
    for line in lines:
        if codes[line.account_id] == "5311":
            assert line.employee_id == employee_id
        else:
            # The bank account is the company's, not the person's.
            assert line.employee_id is None


def test_paying_in_cash_credits_the_till(payroll_world: dict[str, Any]) -> None:  # noqa: F811
    world = payroll_world
    with tenant_context(world["context"]):
        run, _employee_id, net = _posted_run(world)
        payment = create_payment(run_id=run.id, paid_on=PAID_ON, treasury_account="cash")
        post_payment(payment_id=payment.id, actor_user_id=world["user"])
        _entry, lines = _payment_lines(payment.id)
    codes = world["codes"]
    assert {(codes[line.account_id], line.credit) for line in lines if line.credit > 0} == {
        ("2411", net)
    }


def test_posting_twice_posts_once(payroll_world: dict[str, Any]) -> None:  # noqa: F811
    world = payroll_world
    with tenant_context(world["context"]):
        run, _employee_id, _net = _posted_run(world)
        payment = create_payment(run_id=run.id, paid_on=PAID_ON, treasury_account="bank")
        first = post_payment(payment_id=payment.id, actor_user_id=world["user"])
        again = post_payment(payment_id=payment.id, actor_user_id=world["user"])
        entry, _lines = _payment_lines(payment.id)
        events = AccountingEvent.objects.filter(source_document_id=payment.id).count()
        entries = JournalEntry.objects.filter(
            accounting_event_id=uuid.UUID(first["posting"]["accounting_event_id"])
        ).count()
    assert again["posting"]["accounting_event_id"] == first["posting"]["accounting_event_id"]
    assert events == 1
    assert entries == 1
    assert entry.accounting_event_id == uuid.UUID(first["posting"]["accounting_event_id"])


def test_a_run_that_is_not_in_the_books_refuses_the_payment_by_name(
    payroll_world: dict[str, Any],  # noqa: F811
) -> None:
    world = payroll_world
    with tenant_context(world["context"]):
        run, _contract = _run(world)  # a draft: computed, not approved, not posted
        with pytest.raises(PayrollRunNotPostedError) as refused:
            create_payment(run_id=run.id, paid_on=PAID_ON, treasury_account="bank")
        assert refused.value.code == "payroll.run_not_posted"
        assert not SalaryPayment.objects.filter(run_id=run.id).exists()


def test_more_than_the_run_left_is_refused_on_the_draft_and_again_at_posting(
    payroll_world: dict[str, Any],  # noqa: F811
) -> None:
    world = payroll_world
    with tenant_context(world["context"]):
        run, employee_id, net = _posted_run(world)
        first = create_payment(run_id=run.id, paid_on=PAID_ON, treasury_account="bank")
        with pytest.raises(SalaryOverpaymentError) as refused:
            update_payment(
                payment_id=first.id,
                lines=[{"employee_id": employee_id, "amount": net + Decimal("0.01")}],
            )
        assert refused.value.code == "payroll.overpayment"
        # The draft is untouched by the refusal.
        assert payment_in_context(first.id)["lines"][0]["amount"] == str(net)

        # A second draft opened while the first was still a draft: both carry the
        # full net. Once the first posts, the second is too large -- and is told so
        # at posting, not silently posted into a receivable.
        second = create_payment(run_id=run.id, paid_on=PAID_ON, treasury_account="cash")
        post_payment(payment_id=first.id, actor_user_id=world["user"])
        with pytest.raises(SalaryOverpaymentError):
            post_payment(payment_id=second.id, actor_user_id=world["user"])
        assert payment_in_context(second.id)["status"] == "draft"
        assert not AccountingEvent.objects.filter(source_document_id=second.id).exists()
        assert _balance_5311(world, employee_id) == 0


def test_two_partial_payments_add_up_to_the_net_and_a_third_has_nobody_to_pay(
    payroll_world: dict[str, Any],  # noqa: F811
) -> None:
    world = payroll_world
    with tenant_context(world["context"]):
        run, employee_id, net = _posted_run(world)
        half = (net / 2).quantize(Decimal("0.01"))

        first = create_payment(run_id=run.id, paid_on=date(2026, 3, 15), treasury_account="cash")
        update_payment(payment_id=first.id, lines=[{"employee_id": employee_id, "amount": half}])
        post_payment(payment_id=first.id, actor_user_id=world["user"])
        assert _balance_5311(world, employee_id) == net - half

        second = create_payment(run_id=run.id, paid_on=PAID_ON, treasury_account="bank")
        body = payment_in_context(second.id)
        assert body["lines"][0]["already_paid"] == str(half)
        assert body["lines"][0]["amount"] == str(net - half)
        post_payment(payment_id=second.id, actor_user_id=world["user"])
        assert _balance_5311(world, employee_id) == 0

        with pytest.raises(SalaryPaymentEmptyError):
            create_payment(run_id=run.id, paid_on=PAID_ON, treasury_account="bank")
        assert [row["status"] for row in payments_of_run(run.id)] == ["posted", "posted"]


def test_the_bank_list_carries_name_idnp_iban_and_the_amount_in_romanian_form(
    payroll_world: dict[str, Any],  # noqa: F811
) -> None:
    world = payroll_world
    with tenant_context(world["context"]):
        run, employee_id, net = _posted_run(world)
        set_bank_iban(employee_id=employee_id, bank_iban="md24 ag00 0225 1000 1310 4168")
        filename, body = bank_list_csv(run.id)
    assert filename == "lista-de-plata-2026-03.csv"
    text = body.decode("utf-8-sig")
    rows = text.split("\r\n")
    assert rows[0] == "Nr.;Nume și prenume;IDNP;IBAN;Suma"
    assert rows[1] == f"1;Rusu CIM-P1;2001111111150;{IBAN};{decimal_ro(net)}"
    assert rows[2] == ""
    # The decimal comma, not the point: the file is a Romanian document (C38).
    assert "," in decimal_ro(net) and "." not in decimal_ro(net)


def test_another_tenant_sees_nothing_of_the_payment(
    payroll_world: dict[str, Any],  # noqa: F811
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> None:
    alpha = payroll_world
    with tenant_context(alpha["context"]):
        run, _employee_id, _net = _posted_run(alpha)
        payment = create_payment(run_id=run.id, paid_on=PAID_ON, treasury_account="bank")
        post_payment(payment_id=payment.id, actor_user_id=alpha["user"])

    beta_company = company_of(world["tenant_b"], "1000000000042", "Beta SRL")
    grant_company(world["tenant_b"], beta_company, world["user_b"], world["user_b"])
    intruder = TenantContext(
        tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="intruder"
    )
    with tenant_context(intruder):
        assert payments_of_run(run.id) == []
        assert SalaryPayment.objects.count() == 0
        assert SalaryPaymentLine.objects.count() == 0
        with pytest.raises(SalaryPaymentNotFoundError):
            payment_in_context(payment.id)
        with pytest.raises(Exception):  # noqa: B017 -- the run itself is invisible
            bank_list_csv(run.id)
