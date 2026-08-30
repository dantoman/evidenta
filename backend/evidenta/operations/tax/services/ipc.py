"""Generating the monthly return -- and never regenerating what was filed.

**One entity, three sections** (art. 5 para (1) of Law 489/1999): the nominal
record and the contribution calculation are parts of the return.

**Versions, not overwrites** (art. 188 of the Fiscal Code). `generate` produces
version 1; `correct` produces the next version and points it at the one it
replaces. Neither ever touches a submitted return, and the database refuses it
too.

**Frozen at generation.** Every code, every identity and every amount is copied
onto the row. Regenerating March in September has to produce what was filed in
April, not what September's rules would produce -- and a declaration that looked
its numbers up at read time could not promise that.

**The source is an approved payroll run**, read through payroll's public service
(`D4` forbids the other direction; `D6` forbids reaching into its models). A draft
run can still hold lines with no amount, and a return built from one would carry a
hole indistinguishable from a zero.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from django.db import transaction

from evidenta.operations.payroll.services.insured import InsuredCharge, insured_charges
from evidenta.operations.tax.models import (
    DeclarationStatus,
    IpcDeclaration,
    IpcNominalLine,
    IpcTotalLine,
)
from evidenta.platform.api.errors import ApiError
from evidenta.platform.audit.services.recording import record
from evidenta.platform.tenancy.services.companies import statutory_identity

#: Art. 5 para (1) letter a) of Law 489/1999, and art. 92 para (1)-(2) of the
#: Fiscal Code for the withheld tax: the 25th of the month following the one
#: reported. A constant rather than a parameter, because it is the deadline in
#: the act rather than a rate -- and it is **stored** on each return, so a future
#: change does not restate what an old one was due by.
DEADLINE_DAY = 25


class IpcError(ApiError):
    code = "tax.ipc_malformed"
    status = 422


class IpcExistsError(ApiError):
    code = "tax.ipc_exists"
    status = 409


class IpcNotFoundError(ApiError):
    code = "tax.ipc_not_found"
    status = 404


class IpcEmptyError(ApiError):
    """Nothing to declare, and it is refused rather than filed empty.

    A return generated from a month with no approved run is not an empty return;
    it is a return generated too early. Filing one would say "nobody was insured
    in March", which is a claim, not an absence.
    """

    code = "tax.ipc_nothing_to_declare"
    status = 409


class IpcSubmittedError(ApiError):
    code = "tax.ipc_submitted"
    status = 409


def due_date(year: int, month: int) -> date:
    """The 25th of the following month, including across a year boundary."""
    return date(year + (month // 12), (month % 12) + 1, DEADLINE_DAY)


def generate(
    *, tenant_id: uuid.UUID, company_id: uuid.UUID, year: int, month: int
) -> dict[str, Any]:
    """The primary return for a period. Refused if one already exists.

    A second primary return is not a correction: art. 188 gives corrections their
    own form, and two version-1 returns for one month would leave the question of
    which was filed unanswerable.
    """
    if IpcDeclaration.objects.filter(
        company_id=company_id, year=year, month=month, version_number=1
    ).exists():
        raise IpcExistsError(
            f"{year}-{month:02d} already has a primary return. A change is a "
            f"corrected return (art. 188), not a second primary one"
        )
    return _write(
        tenant_id=tenant_id,
        company_id=company_id,
        year=year,
        month=month,
        version_number=1,
        corrects=None,
    )


def correct(*, declaration_id: uuid.UUID) -> dict[str, Any]:
    """A corrected return -- the next version, pointing at what it replaces.

    Generated from today's state of the period, which is the point: what a
    correction says is what is true now, while the version it corrects keeps
    saying what was filed then. Both stay readable, in a chain.
    """
    previous = _latest_of(declaration_id)
    return _write(
        tenant_id=previous.tenant_id,
        company_id=previous.company_id,
        year=previous.year,
        month=previous.month,
        version_number=previous.version_number + 1,
        corrects=previous,
    )


def submit(*, declaration_id: uuid.UUID, submitted_on: date) -> dict[str, Any]:
    """Record that it was filed. After this the rows are frozen in the database.

    The date is given rather than taken from the clock: the return may be filed
    through the tax service's own channel and recorded here afterwards, and a
    date invented at recording time would answer "when was this filed" with "when
    was this typed".
    """
    declaration = IpcDeclaration.objects.filter(id=declaration_id).first()
    if declaration is None:
        raise IpcNotFoundError("no such return in this context")
    if declaration.status == DeclarationStatus.SUBMITTED:
        raise IpcSubmittedError(
            f"the return was already recorded as filed on {declaration.submitted_on}"
        )

    declaration.status = DeclarationStatus.SUBMITTED
    declaration.submitted_on = submitted_on
    declaration.save(update_fields=["status", "submitted_on"])

    record(
        action="tax.ipc_submitted",
        entity_type="ipc_declaration",
        entity_id=declaration.id,
        company_id=declaration.company_id,
        new_value={"submitted_on": str(submitted_on)},
    )
    return declaration_in_context(declaration.id)


def _latest_of(declaration_id: uuid.UUID) -> IpcDeclaration:
    declaration = IpcDeclaration.objects.filter(id=declaration_id).first()
    if declaration is None:
        raise IpcNotFoundError("no such return in this context")

    latest = (
        IpcDeclaration.objects.filter(
            company_id=declaration.company_id,
            year=declaration.year,
            month=declaration.month,
        )
        .order_by("-version_number")
        .first()
    )
    assert latest is not None
    if latest.id != declaration.id:
        raise IpcError(
            f"version {declaration.version_number} is not the latest for "
            f"{declaration.year}-{declaration.month:02d}; corrections chain from the "
            f"last one, so that the chain has one end rather than two"
        )
    return latest


def _write(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    year: int,
    month: int,
    version_number: int,
    corrects: IpcDeclaration | None,
) -> dict[str, Any]:
    identity = statutory_identity(company_id)
    charges = insured_charges(company_id=company_id, year=year, month=month)
    if not charges:
        raise IpcEmptyError(
            f"{year}-{month:02d} has no approved payroll with a social contribution. "
            f"A return generated now would state that nobody was insured, which is a "
            f"claim rather than an absence"
        )

    with transaction.atomic():
        declaration = IpcDeclaration.objects.create(
            tenant_id=tenant_id,
            company_id=company_id,
            year=year,
            month=month,
            version_number=version_number,
            corrects=corrects,
            # Frozen from the company as it is now. A CAEM code corrected next
            # year does not rewrite a return filed this one.
            fiscal_code=identity.fiscal_code,
            cuatm_code=identity.cuatm_code,
            caem_code=identity.caem_code,
            due_on=due_date(year, month),
        )
        _write_nominal(declaration, charges)
        _write_totals(declaration, charges)

    record(
        action="tax.ipc_generated",
        entity_type="ipc_declaration",
        entity_id=declaration.id,
        company_id=company_id,
        new_value={"year": year, "month": month, "version": version_number},
    )
    return declaration_in_context(declaration.id)


def _write_nominal(declaration: IpcDeclaration, charges: list[InsuredCharge]) -> None:
    IpcNominalLine.objects.bulk_create(
        [
            IpcNominalLine(
                tenant_id=declaration.tenant_id,
                company_id=declaration.company_id,
                declaration=declaration,
                line_number=position,
                person_id=charge.person_id,
                last_name=charge.last_name,
                first_name=charge.first_name,
                idnp=charge.idnp,
                personal_insurance_code=charge.personal_insurance_code,
                work_period_start=charge.work_period_start,
                work_period_end=charge.work_period_end,
                # Annex 3's classifier is not obtained; nothing is written rather
                # than a guessed numeric code.
                insured_category_code=None,
                tariff_rate=charge.tariff_rate,
                insured_income=charge.insured_income,
                contribution=charge.contribution,
            )
            for position, charge in enumerate(charges, start=1)
        ]
    )


def _write_totals(declaration: IpcDeclaration, charges: list[InsuredCharge]) -> None:
    """Sum by the two dimensions the adopted form groups on, on one row.

    Table 1 groups by income source code and the second part of table 2 by tariff
    row; carrying both on the row means either grouping is a read rather than a
    second stored truth.
    """
    buckets: dict[tuple[str, str], IpcTotalLine] = {}
    for charge in charges:
        key = (charge.income_source_code, charge.cas_tariff_code)
        row = buckets.get(key)
        if row is None:
            row = IpcTotalLine(
                tenant_id=declaration.tenant_id,
                company_id=declaration.company_id,
                declaration=declaration,
                income_source_code=charge.income_source_code,
                cas_tariff_code=charge.cas_tariff_code,
                income_paid=0,
                income_tax_withheld=0,
                health_insurance_withheld=0,
                social_contribution=0,
            )
            buckets[key] = row
        row.income_paid += charge.income_paid
        row.income_tax_withheld += charge.income_tax_withheld
        row.health_insurance_withheld += charge.health_insurance_withheld
        row.social_contribution += charge.contribution

    IpcTotalLine.objects.bulk_create(list(buckets.values()))


def declarations_of(company_id: uuid.UUID) -> list[dict[str, Any]]:
    return [
        {
            "id": str(row.id),
            "year": row.year,
            "month": row.month,
            "version_number": row.version_number,
            "corrects_id": str(row.corrects_id) if row.corrects_id else None,
            "status": row.status,
            "due_on": str(row.due_on),
            "submitted_on": str(row.submitted_on) if row.submitted_on else None,
        }
        for row in IpcDeclaration.objects.filter(company_id=company_id).order_by(
            "-year", "-month", "-version_number"
        )
    ]


def declaration_in_context(declaration_id: uuid.UUID) -> dict[str, Any]:
    """The whole return, as it was written. Nothing on this path recomputes."""
    declaration = IpcDeclaration.objects.filter(id=declaration_id).first()
    if declaration is None:
        raise IpcNotFoundError("no such return in this context")

    return {
        "id": str(declaration.id),
        "year": declaration.year,
        "month": declaration.month,
        "version_number": declaration.version_number,
        "corrects_id": str(declaration.corrects_id) if declaration.corrects_id else None,
        "status": declaration.status,
        "due_on": str(declaration.due_on),
        "submitted_on": str(declaration.submitted_on) if declaration.submitted_on else None,
        "header": {
            "fiscal_code": declaration.fiscal_code,
            "cuatm_code": declaration.cuatm_code,
            "caem_code": declaration.caem_code,
        },
        "totals": [
            {
                "income_source_code": row.income_source_code,
                "cas_tariff_code": row.cas_tariff_code,
                "income_paid": str(row.income_paid),
                "income_tax_withheld": str(row.income_tax_withheld),
                "health_insurance_withheld": str(row.health_insurance_withheld),
                "social_contribution": str(row.social_contribution),
            }
            for row in declaration.totals.order_by("income_source_code", "cas_tariff_code")
        ],
        "nominal": [
            {
                "line_number": row.line_number,
                "person_id": str(row.person_id),
                "name": f"{row.last_name} {row.first_name}",
                "idnp": row.idnp,
                "personal_insurance_code": row.personal_insurance_code,
                "work_period_start": str(row.work_period_start),
                "work_period_end": str(row.work_period_end),
                "insured_category_code": row.insured_category_code,
                "tariff_rate": str(row.tariff_rate) if row.tariff_rate is not None else None,
                "insured_income": str(row.insured_income),
                "contribution": str(row.contribution),
            }
            for row in declaration.nominal.order_by("line_number")
        ],
    }
