"""Exemptions -- an application with an effective date, and the history it makes.

**Point 18 is the whole shape.** The regulation approved by HG 697/2014 grants
and cancels exemptions *from the month following* the one the application was
filed or withdrawn in. So this module never writes "the employee has exemption
P"; it records an application, and the application opens or closes a dated
entitlement. "What exemptions did this person have in March" is then a query, and
that is exactly what `R18` asks of every recalculation of a past month.

**No amounts.** What an exemption is worth is a fiscal parameter (`R15`), resolved
by the effective date of the period being calculated. This module says who was
entitled to what, and when.

**No `S`.** There is no ordinary spouse exemption -- art. 34 para (2) grants only
the increased one. The vocabulary is closed in the model and in the database; the
absence is deliberate and is the reason
`income_tax.exemption_spouse_ordinary = 0` is a loaded parameter rather than a
missing one.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from django.db import IntegrityError, transaction

from evidenta.operations.payroll.models import (
    DEPENDENT_CODES,
    Dependent,
    Employee,
    ExemptionApplication,
    ExemptionCode,
    ExemptionEntitlement,
)
from evidenta.platform.api.errors import ApiError
from evidenta.platform.audit.services.recording import record


class ExemptionMalformedError(ApiError):
    code = "payroll.exemption_malformed"
    status = 422


class ExemptionOverlapError(ApiError):
    """The same exemption, for the same dependent, over a period already covered.

    Distinct from `malformed` (`C10`): the request is well formed and the state
    refuses it, which is a different thing for whoever is holding the screen --
    the fix is to look at what is already there, not at what was typed.
    """

    code = "payroll.exemption_overlap"
    status = 409


class ExemptionNotFoundError(ApiError):
    code = "payroll.exemption_not_found"
    status = 404


@dataclass(frozen=True, slots=True)
class GrantRequest:
    """One line of the application: a code, and a dependent when the code needs one."""

    code: str
    dependent_id: uuid.UUID | None = None


def month_after(filed_on: date) -> date:
    """The first day of the month following `filed_on` -- point 18.

    Written here **and** checked by the database. Not redundancy: the CHECK is
    what makes the rule survive a bulk import or a correction written straight
    into the table, and this is what makes the screen able to show the date
    before anybody saves.
    """
    return date(filed_on.year + (filed_on.month // 12), (filed_on.month % 12) + 1, 1)


def add_dependent(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    employee_id: uuid.UUID,
    last_name: str,
    first_name: str,
    idnp: str | None = None,
    identity_document_type: str | None = None,
    identity_document_number: str | None = None,
) -> Dependent:
    """Record a person an exemption can be claimed for.

    Their own identifier is required for the same reason the employee's is: it is
    what makes the legitimate uniqueness constraint possible. Without it, the same
    child entered twice is indistinguishable from two children -- and the
    exemption doubles, quietly.
    """
    if not Employee.objects.filter(id=employee_id, company_id=company_id).exists():
        raise ExemptionMalformedError("no such person in this company")

    surname = (last_name or "").strip()
    given = (first_name or "").strip()
    if not surname or not given:
        raise ExemptionMalformedError("a dependent has both names")

    idnp = (idnp or "").strip() or None
    doc_type = (identity_document_type or "").strip() or None
    doc_number = (identity_document_number or "").strip() or None
    if idnp is None and not (doc_type and doc_number):
        raise ExemptionMalformedError(
            "a dependent needs an identifier of their own: without one there is no "
            "constraint that can tell the same child entered twice from two children"
        )
    if idnp is not None and (doc_type or doc_number):
        raise ExemptionMalformedError("an IDNP or a document, not both")

    try:
        with transaction.atomic():
            dependent = Dependent.objects.create(
                tenant_id=tenant_id,
                company_id=company_id,
                employee_id=employee_id,
                last_name=surname,
                first_name=given,
                idnp=idnp,
                identity_document_type=doc_type,
                identity_document_number=doc_number,
            )
    except IntegrityError as exc:
        raise ExemptionOverlapError(
            "this person is already recorded as a dependent of that employee"
        ) from exc

    record(
        action="payroll.dependent_created",
        entity_type="exemption_dependent",
        entity_id=dependent.id,
        company_id=company_id,
        new_value={"employee": str(employee_id)},
    )
    return dependent


def file_application(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    employee_id: uuid.UUID,
    filed_on: date,
    declared_sole_workplace: bool,
    grants: list[GrantRequest],
    note: str = "",
) -> dict[str, Any]:
    """Record an application and open the entitlements it grants.

    The effective date is **derived** from `filed_on`, never supplied: point 18
    fixes it, and a date the caller could choose is a rule the caller could break.

    `declared_sole_workplace` is the employee's declaration, stored as one. Point
    9 grants exemptions at one place of work only -- a fact across employers that
    no employer can verify and this system cannot see across tenants. What is
    recorded is the evidence the employer acted on, not a check nobody can
    perform.
    """
    if not Employee.objects.filter(id=employee_id, company_id=company_id).exists():
        raise ExemptionMalformedError("no such person in this company")
    if not grants:
        raise ExemptionMalformedError("an application grants at least one exemption")

    effective_from = month_after(filed_on)

    for grant in grants:
        if grant.code not in ExemptionCode.values:
            raise ExemptionMalformedError(
                f"{grant.code!r} is not an exemption code. Art. 34 para (2) grants "
                f"only the increased spouse exemption, so the vocabulary is "
                f"{', '.join(ExemptionCode.values)} -- there is no ordinary 'S'"
            )
        needs_dependent = grant.code in DEPENDENT_CODES
        if needs_dependent and grant.dependent_id is None:
            raise ExemptionMalformedError(
                f"exemption {grant.code} is claimed for a named person, so it needs one"
            )
        if not needs_dependent and grant.dependent_id is not None:
            raise ExemptionMalformedError(
                f"exemption {grant.code} is personal; naming a dependent on it would "
                f"claim the same person twice"
            )
        if (
            grant.dependent_id is not None
            and not Dependent.objects.filter(
                id=grant.dependent_id, employee_id=employee_id
            ).exists()
        ):
            raise ExemptionMalformedError("that dependent does not belong to this person")

    try:
        with transaction.atomic():
            application = ExemptionApplication.objects.create(
                tenant_id=tenant_id,
                company_id=company_id,
                employee_id=employee_id,
                filed_on=filed_on,
                effective_from=effective_from,
                declared_sole_workplace=declared_sole_workplace,
                note=note or "",
            )
            for grant in grants:
                ExemptionEntitlement.objects.create(
                    tenant_id=tenant_id,
                    company_id=company_id,
                    employee_id=employee_id,
                    code=grant.code,
                    dependent_id=grant.dependent_id,
                    valid_from=effective_from,
                    granted_by=application,
                )
    except IntegrityError as exc:
        raise ExemptionOverlapError(
            "one of these exemptions is already in force over that period for this "
            "person. Two claims for the same dependent double the exemption"
        ) from exc

    record(
        action="payroll.exemption_application_filed",
        entity_type="exemption_application",
        entity_id=application.id,
        company_id=company_id,
        new_value={
            "employee": str(employee_id),
            "effective_from": str(effective_from),
            "codes": [grant.code for grant in grants],
        },
    )
    return application_in_context(application.id)


def withdraw(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    employee_id: uuid.UUID,
    filed_on: date,
    entitlement_ids: list[uuid.UUID],
    note: str = "",
) -> dict[str, Any]:
    """Close entitlements from the month after the withdrawal was filed.

    A withdrawal is an application too -- point 18 treats it the same way, and so
    does the row: the entitlement records *which* document closed it. Nothing is
    deleted, and the database does not grant DELETE here at all: the month it was
    granted in would recalculate differently and nothing would say why.
    """
    if not entitlement_ids:
        raise ExemptionMalformedError("a withdrawal names what it withdraws")

    effective_from = month_after(filed_on)
    rows = list(
        ExemptionEntitlement.objects.filter(
            id__in=entitlement_ids, employee_id=employee_id, valid_to__isnull=True
        )
    )
    if len(rows) != len(entitlement_ids):
        raise ExemptionNotFoundError(
            "one of these exemptions is not open for this person in this context"
        )
    for row in rows:
        if effective_from <= row.valid_from:
            raise ExemptionMalformedError(
                f"exemption {row.code} starts on {row.valid_from}; a withdrawal takes "
                f"effect from {effective_from}, which would leave it with no period at "
                f"all rather than a closed one"
            )

    with transaction.atomic():
        application = ExemptionApplication.objects.create(
            tenant_id=tenant_id,
            company_id=company_id,
            employee_id=employee_id,
            filed_on=filed_on,
            effective_from=effective_from,
            declared_sole_workplace=False,
            note=note or "",
        )
        for row in rows:
            row.valid_to = effective_from
            row.withdrawn_by = application
            row.save(update_fields=["valid_to", "withdrawn_by"])

    record(
        action="payroll.exemption_withdrawn",
        entity_type="exemption_application",
        entity_id=application.id,
        company_id=company_id,
        new_value={"employee": str(employee_id), "closed": [str(row.id) for row in rows]},
    )
    return application_in_context(application.id)


def exemptions_in_force_on(employee_id: uuid.UUID, on: date) -> list[dict[str, Any]]:
    """What this person was entitled to on that date. The question point 18 creates.

    Half-open interval: `valid_to` is the first day **not** covered, which is what
    the withdrawal writes -- the month after the request. A closed interval here
    would grant one extra month to everybody who ever withdrew a claim.
    """
    rows = (
        ExemptionEntitlement.objects.filter(employee_id=employee_id, valid_from__lte=on)
        .exclude(valid_to__lte=on)
        .select_related("dependent")
        .order_by("code", "valid_from")
    )
    return [_entitlement(row) for row in rows]


def exemptions_of(employee_id: uuid.UUID) -> list[dict[str, Any]]:
    """The whole history, closed rows included. Nothing here is ever deleted."""
    rows = (
        ExemptionEntitlement.objects.filter(employee_id=employee_id)
        .select_related("dependent")
        .order_by("valid_from", "code")
    )
    return [_entitlement(row) for row in rows]


def dependents_of(employee_id: uuid.UUID) -> list[dict[str, Any]]:
    return [
        {
            "id": str(row.id),
            "last_name": row.last_name,
            "first_name": row.first_name,
            "idnp": row.idnp,
            "identity_document_type": row.identity_document_type,
            "identity_document_number": row.identity_document_number,
        }
        for row in Dependent.objects.filter(employee_id=employee_id).order_by(
            "last_name", "first_name"
        )
    ]


def application_in_context(application_id: uuid.UUID) -> dict[str, Any]:
    application = ExemptionApplication.objects.filter(id=application_id).first()
    if application is None:
        raise ExemptionNotFoundError("no such application in this context")
    return {
        "id": str(application.id),
        "employee_id": str(application.employee_id),
        "filed_on": str(application.filed_on),
        "effective_from": str(application.effective_from),
        "declared_sole_workplace": application.declared_sole_workplace,
        "note": application.note,
        "granted": [_entitlement(row) for row in application.granted.all()],
    }


def _entitlement(row: ExemptionEntitlement) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "code": row.code,
        "dependent_id": str(row.dependent_id) if row.dependent_id else None,
        "dependent_name": (
            f"{row.dependent.last_name} {row.dependent.first_name}" if row.dependent else None
        ),
        "valid_from": str(row.valid_from),
        "valid_to": str(row.valid_to) if row.valid_to else None,
        "granted_by_filed_on": str(row.granted_by.filed_on) if row.granted_by_id else None,
    }
