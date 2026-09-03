"""The payslip -- a legal document, generated on the server, in Romanian.

**Its labels are here and not in the interface resource files, and that is the
rule rather than an oversight.** `C32` puts interface strings in resource files
so that adding Russian costs a translation; `C33` and `C38` say the opposite
thing about a document: accounting is kept in Romanian (Law 287/2017 art. 7 para
(1)), and no interface translation ever reaches a register, a statement or a
generated document. A payslip is the second kind, so its text is fixed here and
is not translatable -- if it were in the resource file, the day a second language
is added it would quietly follow the reader's choice.

**The formatting comes from the document module** (`platform/documents/formatting`),
which uses fixed `ro-MD` conventions and never consults the active language.
Measured before that module existed: `django.utils.formats` renders a date
according to whoever activated a language last on the thread, and a reused Celery
worker carries that activation into the next task. `decimal_ro` and `date_ro`
cannot move, and the test for this module proves it by rendering a payslip with
another language active.

**The PDF is next door.** `C22` says printed documents are produced by a
server-side pipeline with an imposed format; since ADR-095 that pipeline exists
(`platform/documents/printing`) and `payslip_pdf.py` feeds it **this** dict, so
the JSON the screen shows, the text and the PDF come from one set of values
(`C20`). A screen showing these fields is displaying data; the PDF is the
document.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from evidenta.operations.payroll.models import LineNature, PayrollLine, PayrollRun
from evidenta.operations.payroll.services.exemptions import exemptions_in_force_on
from evidenta.operations.payroll.services.runs import GROSS, PayrollRunNotFoundError
from evidenta.platform.audit.services.recording import record
from evidenta.platform.documents.formatting import date_ro, decimal_ro

#: The document's own words. Fixed, in Romanian, and deliberately not in the
#: interface resource files -- see the module docstring.
TITLE = "Fluturaș de salariu"
LABELS = {
    "salary.gross": "Salariu brut calculat",
    "cas.employer": "Contribuții de asigurări sociale (angajator)",
    "cnam.employee": "Primă de asigurare obligatorie de asistență medicală (reținută)",
    "income_tax.withheld": "Impozit pe venit reținut",
}

MONTHS = (
    "ianuarie",
    "februarie",
    "martie",
    "aprilie",
    "mai",
    "iunie",
    "iulie",
    "august",
    "septembrie",
    "octombrie",
    "noiembrie",
    "decembrie",
)

EXEMPTION_LABELS = {
    "P": "Scutire personală",
    "M": "Scutire personală majoră",
    "Sm": "Scutire majorată pentru soț/soție",
    "N": "Scutire pentru persoană întreținută",
    "H": "Scutire pentru persoană întreținută cu dizabilitate",
}


def payslip(*, run_id: uuid.UUID, employee_id: uuid.UUID) -> dict[str, Any]:
    """One person's payslip for one run.

    Amounts are rendered Romanian-style **and** carried as raw strings. The
    rendered form is what a person reads; the raw form is what a caller checks
    against the register, and keeping both means the screen never has to reformat
    -- which is how the two stop agreeing.
    """
    run = PayrollRun.objects.filter(id=run_id).first()
    if run is None:
        raise PayrollRunNotFoundError("no such payroll run in this context")

    lines = list(
        PayrollLine.objects.filter(run=run, employee_id=employee_id)
        .select_related("employee", "contract")
        .order_by("component_key")
    )
    if not lines:
        raise PayrollRunNotFoundError("this person has no lines in that run")

    employee = lines[0].employee
    contract = lines[0].contract

    # A payslip carries the person's IDNP and the whole salary detail; like every
    # other read of personal data in this module (`F2.B1`, `employee_in_context`)
    # it leaves a trace of who read whose, in JSON, text or PDF alike.
    record(
        action="payroll.payslip_read",
        entity_type="employee",
        entity_id=employee.id,
        company_id=run.company_id,
        new_value={"run_id": str(run.id)},
    )

    gross = Decimal(0)
    withheld = Decimal(0)
    charges = Decimal(0)
    rows: list[dict[str, Any]] = []
    complete = True

    for line in lines:
        if line.amount is None:
            complete = False
        elif line.component_key == GROSS:
            gross = line.amount
        elif line.nature == LineNature.EMPLOYEE_WITHHOLDING:
            withheld += line.amount
        elif line.nature == LineNature.EMPLOYER_CHARGE:
            charges += line.amount

        rows.append(
            {
                "component_key": line.component_key,
                "label": LABELS.get(line.component_key, line.component_key),
                "nature": line.nature,
                "amount": str(line.amount) if line.amount is not None else None,
                "amount_ro": decimal_ro(line.amount) if line.amount is not None else None,
                "basis_ro": decimal_ro(line.basis) if line.basis is not None else None,
                "rate": str(line.rate) if line.rate is not None else None,
                "unresolved_reason": line.unresolved_reason,
            }
        )

    exemptions = [
        {
            "code": entitlement["code"],
            "label": EXEMPTION_LABELS.get(entitlement["code"], entitlement["code"]),
            "dependent_name": entitlement["dependent_name"],
        }
        for entitlement in exemptions_in_force_on(employee_id, lines[0].work_period_end)
    ]

    return {
        "title": TITLE,
        "period": f"{MONTHS[run.month - 1]} {run.year}",
        "accrual_date_ro": date_ro(run.accrual_date),
        "employee_name": f"{employee.last_name} {employee.first_name}",
        "idnp": employee.idnp,
        "position_title": contract.position_title,
        "contract_number": contract.contract_number,
        "components": rows,
        "exemptions": exemptions,
        "gross_ro": decimal_ro(gross),
        "withheld_ro": decimal_ro(withheld),
        "employer_charges_ro": decimal_ro(charges),
        # The net is derived, never stored: it is what remains on the payroll
        # liability after the withholdings (ADR-065 section 8.5).
        "net_ro": decimal_ro(gross - withheld) if complete else None,
        "complete": complete,
    }


def render_text(slip: dict[str, Any]) -> str:
    """The payslip as plain text, in Romanian, at fixed `ro-MD` conventions.

    Kept beside the PDF (`payslip_pdf.py`), not replaced by it: a payslip handed
    over as text is a real thing an accountant sends, and it is produced from the
    same values the register shows, from the same source (`C20`).
    """
    out = [
        slip["title"],
        f"Perioada: {slip['period']}",
        f"Data calculului: {slip['accrual_date_ro']}",
        "",
        f"Angajat: {slip['employee_name']}",
        f"IDNP: {slip['idnp'] or '-'}",
        f"Funcția: {slip['position_title']}",
        f"Contract: {slip['contract_number']}",
        "",
    ]
    for row in slip["components"]:
        if row["amount_ro"] is not None:
            out.append(f"{row['label']}: {row['amount_ro']} MDL")
        else:
            out.append(f"{row['label']}: nu s-a putut calcula — {row['unresolved_reason']}")
    out.append("")
    if slip["exemptions"]:
        out.append("Scutiri aplicate:")
        for exemption in slip["exemptions"]:
            name = exemption["dependent_name"]
            out.append(f"  {exemption['label']}" + (f" — {name}" if name else ""))
        out.append("")
    out.append(f"Total reținut: {slip['withheld_ro']} MDL")
    out.append(
        f"Salariu net: {slip['net_ro']} MDL"
        if slip["net_ro"] is not None
        else "Salariu net: nu se poate stabili cât timp există sume necalculate"
    )
    return "\n".join(out)
