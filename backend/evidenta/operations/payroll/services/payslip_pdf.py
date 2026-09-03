"""The payslip as a printed document -- `C22`, ADR-095.

**What the law prescribes, and what it does not.** Codul muncii (Legea nr.
154/2003) art. 142 alin. (3), read in `F2.X2 (h)`
(`docs/_input/cercetare/f2-x2-concedii-indemnizatii-fluturas.md` §5): at every
payment the employer informs the employee **in writing** of three things -- the
component parts of the salary for the period, the amount **and the grounds** of
each deduction, and the total sum to be received. It prescribes no form, no
name, no medium and no signature, and at 30.08.2026 no act of the MF, SFS or
Government approves one. So the three headings below are the law's; the layout,
the title and the informative block of employer contributions are the platform's
convention, and say so here rather than pretend otherwise.

**The grounds of a deduction** are printed as the deduction's own name and the
rate applied; the article that founds each one is not written on the document,
because it is not in the payslip's data and the rule of this project is not to
write a legal reference from memory (`CLAUDE.md` §4).

**From the same values as the screen** (`C20`): `payslip()` produces the dict
the register's screen shows and the text rendering hands out; this module reads
that dict and adds nothing. The amounts arrive already formatted by the document
formatter; the rates arrive raw and are formatted by the pipeline.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from evidenta.operations.payroll.models import LineNature, PayrollRun, PayrollRunStatus
from evidenta.operations.payroll.services.payslip import payslip
from evidenta.operations.payroll.services.runs import PayrollRunNotFoundError
from evidenta.platform.api.errors import ApiError
from evidenta.platform.documents.printing import (
    Column,
    Field,
    Fields,
    PrintableDocument,
    Section,
    Table,
    Text,
    Totals,
    file_name_of,
    render,
)
from evidenta.platform.tenancy.services.companies import CompanyHeading, company_heading

#: The document's own words -- fixed, Romanian, not interface strings (`C33`).
#: The three headings are art. 142 alin. (3)'s three elements.
COMPONENTS = "Părțile componente ale salariului"
DEDUCTIONS = "Reținerile efectuate — mărimea și temeiul"
NET = "Suma totală de primit"
EMPLOYER_CHARGES = "Contribuțiile angajatorului (informativ; nu se rețin din salariu)"
NOT_COMPUTED = "nu s-a putut calcula"
NET_UNKNOWN = "nu se poate stabili cât timp există sume necalculate"
ABSENT = "—"

COLUMNS = (
    Column("Componenta", weight=6),
    Column("Baza de calcul, lei", "right", 3),
    Column("Cota, %", "right", 2, None),
    Column("Suma, lei", "right", 3),
)


class PayslipNotPrintableError(ApiError):
    """The written payslip of art. 142 alin. (3) is the approved run's, not a draft's.

    A draft recomputes; a document already handed to the person would stop
    matching the run before it is posted. The screen keeps the preview; the PDF
    waits for the approval that freezes the numbers.
    """

    code = "payroll.run_not_approved"
    status = 409


def payslip_printable(*, run_id: uuid.UUID, employee_id: uuid.UUID) -> PrintableDocument:
    run = PayrollRun.objects.filter(id=run_id).first()
    if run is None:
        raise PayrollRunNotFoundError("no such payroll run in this context")
    if run.status != PayrollRunStatus.APPROVED:
        raise PayslipNotPrintableError(
            f"run {run.year}-{run.month:02d} is {run.status}; the payslip is printed from an "
            f"approved run, whose numbers no longer move"
        )
    slip = payslip(run_id=run_id, employee_id=employee_id)
    return payslip_document(slip, company_heading(run.company_id))


def payslip_pdf(*, run_id: uuid.UUID, employee_id: uuid.UUID) -> bytes:
    return render(payslip_printable(run_id=run_id, employee_id=employee_id))


def payslip_document(slip: dict[str, Any], employer: CompanyHeading) -> PrintableDocument:
    """The value the pipeline prints, from the dict the screen shows."""
    by_nature: dict[str, list[tuple[Any, ...]]] = {nature: [] for nature in LineNature.values}
    for row in slip["components"]:
        by_nature[row["nature"]].append(_row(row))

    sections: list[Section] = [
        Fields(
            None,
            (
                Field("Angajator", employer.legal_name),
                Field("IDNO", employer.idno),
                Field("Perioada", slip["period"]),
                Field("Data calculului", slip["accrual_date_ro"]),
            ),
        ),
        Fields(
            "Salariat",
            (
                Field("Numele și prenumele", slip["employee_name"]),
                Field("IDNP", slip["idnp"] or ABSENT),
                Field("Funcția", slip["position_title"]),
                Field("Contractul", slip["contract_number"]),
            ),
        ),
        Text(COMPONENTS, "heading"),
        Table(COLUMNS, tuple(by_nature[LineNature.SALARY_ACCRUAL])),
        Text(DEDUCTIONS, "heading"),
        Table(COLUMNS, tuple(by_nature[LineNature.EMPLOYEE_WITHHOLDING])),
    ]
    if slip["exemptions"]:
        applied = "; ".join(
            exemption["label"]
            + (f" — {exemption['dependent_name']}" if exemption["dependent_name"] else "")
            for exemption in slip["exemptions"]
        )
        sections.append(Text(f"Scutiri aplicate: {applied}", "note"))
    sections.append(
        Totals(
            (
                Field("Salariu brut", slip["gross_ro"]),
                Field("Total rețineri", slip["withheld_ro"]),
                Field(NET, slip["net_ro"] if slip["net_ro"] is not None else NET_UNKNOWN),
            )
        )
    )
    if by_nature[LineNature.EMPLOYER_CHARGE]:
        sections.append(Text(EMPLOYER_CHARGES, "heading"))
        sections.append(Table(COLUMNS, tuple(by_nature[LineNature.EMPLOYER_CHARGE])))

    period = slip["period"]
    return PrintableDocument(
        title=slip["title"],
        subtitle=f"{period} · {employer.legal_name}",
        sections=tuple(sections),
        file_name=file_name_of("fluturas", period, slip["contract_number"]),
    )


def _row(row: dict[str, Any]) -> tuple[Any, ...]:
    if row["amount_ro"] is None:
        return (f"{row['label']} — {NOT_COMPUTED}: {row['unresolved_reason']}", "", "", ABSENT)
    rate = Decimal(row["rate"]) if row["rate"] is not None else None
    return (row["label"], row["basis_ro"] or "", rate, row["amount_ro"])
