"""The people a company employs -- recording one, and finding one again.

**At the level of the company, not the tenant** (ADR-065 section 4). The legal
employer is the company: it withholds, it files, it answers for it. A person
working at two companies of the same tenant is two rows here, deliberately --
they have two work relationships, two withholdings and two declarations, and the
exemption is granted at one place of work only.

**Searching exists for the same reason it exists in the partner directory.** A
screen that asks a person for an `employee_id` is a screen nobody can fill in
correctly. What somebody has in front of them is a name and an IDNP.

**Reads are audited, writes too** (`F2.B1`). Not by a signal (`C4`): explicit
calls, visible in the code that performs the action.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Q

from evidenta.operations.payroll.models import Employee, TaxResidency
from evidenta.platform.api.errors import ApiError
from evidenta.platform.audit.services.recording import record

#: Thirteen digits, like the IDNO the company endpoint enforces. Written here
#: rather than imported so `operations` does not reach into another module's
#: serializers for a regular expression (`D6`).
IDNP = re.compile(r"^\d{13}$")


class EmployeeMalformedError(ApiError):
    code = "payroll.employee_malformed"
    status = 422


class EmployeeDuplicateError(ApiError):
    """Two rows for one person inside a company.

    Refused rather than merged: by the time anybody notices, the withholdings
    have already split between them, and merging is a decision with declaration
    consequences that no automatic path should take.
    """

    code = "payroll.employee_duplicate"
    status = 409


class EmployeeNotFoundError(ApiError):
    code = "payroll.employee_not_found"
    status = 404


def create_employee(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    last_name: str,
    first_name: str,
    tax_residency: str,
    idnp: str | None = None,
    identity_document_type: str | None = None,
    identity_document_number: str | None = None,
    social_insurance_code: str | None = None,
) -> Employee:
    """Record a person. Exactly one identity, and it is not negotiable.

    The row for which the IDNP exception is made is precisely the row that would
    otherwise carry no natural key -- so the alternative identity is required
    rather than optional, and the database refuses the pair anyway.
    """
    surname = (last_name or "").strip()
    given = (first_name or "").strip()
    if not surname or not given:
        raise EmployeeMalformedError(
            "a person needs both names as they appear in the identity document: "
            "the nominal declaration carries them that way (IRM19 col. 2)"
        )
    if tax_residency not in TaxResidency.values:
        raise EmployeeMalformedError(
            f"{tax_residency!r} is not a tax residency. Residency decides the shape "
            f"of the withholding, so it is stated rather than defaulted"
        )

    idnp = (idnp or "").strip() or None
    doc_type = (identity_document_type or "").strip() or None
    doc_number = (identity_document_number or "").strip() or None

    if idnp is not None:
        if doc_type or doc_number:
            raise EmployeeMalformedError(
                "a person is identified by IDNP or by an identity document, not by "
                "both: two natural keys on one row is two ways to enter them twice"
            )
        if not IDNP.match(idnp):
            raise EmployeeMalformedError("an IDNP is thirteen digits")
    elif not (doc_type and doc_number):
        raise EmployeeMalformedError(
            "a person without an IDNP needs the type and number of an identity "
            "document. Without one of the two there is no natural key at all, and "
            "the same person is entered again at the next hiring"
        )

    try:
        with transaction.atomic():
            employee = Employee.objects.create(
                tenant_id=tenant_id,
                company_id=company_id,
                last_name=surname,
                first_name=given,
                tax_residency=tax_residency,
                idnp=idnp,
                identity_document_type=doc_type,
                identity_document_number=doc_number,
                social_insurance_code=(social_insurance_code or "").strip() or None,
            )
    except IntegrityError as exc:
        raise EmployeeDuplicateError("this company already has a record for that person") from exc

    record(
        action="payroll.employee_created",
        entity_type="employee",
        entity_id=employee.id,
        company_id=company_id,
        new_value={"last_name": surname, "first_name": given},
    )
    return employee


def employees_of(
    company_id: uuid.UUID, *, query: str | None = None, limit: int = 200
) -> list[dict[str, Any]]:
    """The people of one company, newest names first by surname.

    `query` matches what a person has in front of them: a name, or an IDNP.
    """
    rows = Employee.objects.filter(company_id=company_id)
    if query:
        needle = query.strip()
        if needle:
            rows = rows.filter(
                Q(last_name__icontains=needle)
                | Q(first_name__icontains=needle)
                | Q(idnp__startswith=needle)
            )
    rows = rows.order_by("last_name", "first_name")[:limit]
    return [_as_dict(row) for row in rows]


def employee_in_context(employee_id: uuid.UUID) -> dict[str, Any]:
    employee = Employee.objects.filter(id=employee_id).first()
    if employee is None:
        raise EmployeeNotFoundError("no such person in this context")

    record(
        action="payroll.employee_read",
        entity_type="employee",
        entity_id=employee.id,
        company_id=employee.company_id,
    )
    return _as_dict(employee)


def _as_dict(employee: Employee) -> dict[str, Any]:
    return {
        "id": str(employee.id),
        # The company, because the caller frequently has only the person's id --
        # the exemption routes hang off the person, and every write below them
        # still has to name the company the employer is.
        "company_id": str(employee.company_id),
        "last_name": employee.last_name,
        "first_name": employee.first_name,
        "idnp": employee.idnp,
        "identity_document_type": employee.identity_document_type,
        "identity_document_number": employee.identity_document_number,
        "tax_residency": employee.tax_residency,
        "social_insurance_code": employee.social_insurance_code,
    }
