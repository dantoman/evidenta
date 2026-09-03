"""The printed payslip -- `C22`, `C38`, ADR-095 -- under the application role.

The same four claims as `test_printing.py` makes for the invoice: Romanian
whatever language is active, identical bytes twice, the legal names, the route
answering as a document -- and for another tenant the same 404 every reader of
this project gives (IZ-04). The fixtures are the payroll run's own, so the month,
the rates and the ledger are what `test_payroll_run.py` builds.
"""

from __future__ import annotations

import io
import uuid
from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from django.test import Client
from django.utils import translation
from pypdf import PdfReader

from evidenta.operations.payroll.models import PayrollLine
from evidenta.operations.payroll.services.payslip_pdf import (
    PayslipNotPrintableError,
    payslip_pdf,
    payslip_printable,
)
from evidenta.operations.payroll.services.runs import PayrollRunNotFoundError, approve, create_run
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.isolation.test_coa_api import HOST_A, mfa_key, signed_in  # noqa: F401
from tests.isolation.test_payroll_run import (  # noqa: F401
    a_contract,
    a_month,
    alpha,
    context_of,
    rates,
    rounding_direction,
)

pytestmark = pytest.mark.django_db(databases=["default", "migration", "refdata"])


def text_of(pdf: bytes) -> str:
    assert pdf.startswith(b"%PDF-")
    return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)


def other_tenant(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="print-b")


def a_run(alpha: dict[str, uuid.UUID], rates: Callable[..., None]) -> tuple[Any, uuid.UUID]:  # noqa: F811
    rates(
        "cnas.employer_rate",
        "cnam.employee_rate",
        "income_tax.rate_individual",
        "labour.minimum_wage_monthly",
        "income_tax.exemption_personal",
    )
    contract = a_contract(alpha, idnp="2001111111177", number="CIM-9")
    a_month(alpha, contract)
    run = create_run(
        tenant_id=alpha["tenant"],
        company_id=alpha["company"],
        year=2026,
        month=3,
        accrual_date=date(2026, 3, 31),
    )
    employee = PayrollLine.objects.filter(run=run).values_list("employee_id", flat=True)[0]
    # The written payslip is the approved run's (art. 142 alin. (3)); a draft is
    # refused by name, which its own test below measures.
    approve(run_id=run.id, approver_user_id=alpha["user"])
    return run, employee


def test_the_payslip_is_romanian_and_deterministic(
    alpha: dict[str, uuid.UUID],  # noqa: F811
    rates: Callable[..., None],  # noqa: F811
) -> None:
    with tenant_context(context_of(alpha)):
        run, employee = a_run(alpha, rates)
        with translation.override("ru"):
            under_russian = payslip_pdf(run_id=run.id, employee_id=employee)
        with translation.override("en"):
            under_english = payslip_pdf(run_id=run.id, employee_id=employee)
        romanian = payslip_pdf(run_id=run.id, employee_id=employee)
        printable = payslip_printable(run_id=run.id, employee_id=employee)

    assert romanian == under_russian == under_english
    assert printable.file_name == "fluturas-martie-2026-CIM-9"

    text = text_of(romanian)
    assert "Fluturaș de salariu" in text
    assert "martie 2026" in text and "31.03.2026" in text
    # The employer by its legal name, the employee, the three elements of
    # art. 142 alin. (3): components, deductions with their amount, the net.
    assert "Alpha SRL" in text and "Rusu CIM-9" in text
    assert "Părțile componente ale salariului" in text
    assert "Reținerile efectuate" in text
    assert "Suma totală de primit" in text
    assert "10000,00" in text and "4500,00" in text
    assert "10000.00" not in text


def test_the_payslip_route_serves_pdf_and_another_tenant_gets_nothing(
    alpha: dict[str, uuid.UUID],  # noqa: F811
    rates: Callable[..., None],  # noqa: F811
    world: dict[str, uuid.UUID],
    signed_in: Client,  # noqa: F811
) -> None:
    with tenant_context(context_of(alpha)):
        run, employee = a_run(alpha, rates)

    served = signed_in.get(
        f"/api/v1/payroll/runs/{run.id}/payslips/{employee}/pdf", headers={"host": HOST_A}
    )
    assert served.status_code == 200, served.content
    assert served["Content-Type"] == "application/pdf"
    assert served["Content-Disposition"] == 'inline; filename="fluturas-martie-2026-CIM-9.pdf"'
    assert served.content.startswith(b"%PDF-")

    with tenant_context(other_tenant(world)), pytest.raises(PayrollRunNotFoundError) as refused:
        payslip_printable(run_id=run.id, employee_id=employee)
    assert refused.value.status == 404


def test_a_draft_run_has_no_written_payslip(
    alpha: dict[str, uuid.UUID],  # noqa: F811
    rates: Callable[..., None],  # noqa: F811
) -> None:
    """Until approval the numbers can still move, so nothing is handed out in writing."""
    rates(
        "cnas.employer_rate",
        "cnam.employee_rate",
        "income_tax.rate_individual",
        "labour.minimum_wage_monthly",
        "income_tax.exemption_personal",
    )
    with tenant_context(context_of(alpha)):
        contract = a_contract(alpha, idnp="2001111111178", number="CIM-10")
        a_month(alpha, contract)
        run = create_run(
            tenant_id=alpha["tenant"],
            company_id=alpha["company"],
            year=2026,
            month=3,
            accrual_date=date(2026, 3, 31),
        )
        employee = PayrollLine.objects.filter(run=run).values_list("employee_id", flat=True)[0]
        with pytest.raises(PayslipNotPrintableError) as refused:
            payslip_printable(run_id=run.id, employee_id=employee)
    assert refused.value.code == "payroll.run_not_approved"
