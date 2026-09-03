"""What another module may ask about a company, without touching its table.

`D6`: modules talk through services, not through each other's models. The
posting engine needs one fact -- the currency the books are kept in -- and
`manual.post_manual_entry` already documents why it takes it as a parameter
rather than looking it up: no public service of this module exposed it. This is
that service.

Everything here reads under the policy, so a company this context cannot see is
absent rather than forbidden (IZ-04).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any, Final

from django.db import transaction

from evidenta.platform.api.errors import ApiError
from evidenta.platform.audit.services.recording import record
from evidenta.platform.identity.services.roles import RoleError, require_company_permission
from evidenta.platform.rls.context import MissingTenantContextError, current_context
from evidenta.platform.tenancy.models import Company, CompanyStatus


class CompanyNotVisibleError(ApiError):
    """The company does not exist, or this context cannot reach it."""

    code = "tenancy.company_not_visible"
    status = 404


def functional_currency(company_id: uuid.UUID) -> str:
    """The currency this company keeps its books in."""
    currency = (
        Company.objects.filter(id=company_id).values_list("functional_currency", flat=True).first()
    )
    if currency is None:
        raise CompanyNotVisibleError(f"company {company_id} is not visible in this context")
    return str(currency)


@dataclass(frozen=True, slots=True)
class StatutoryIdentity:
    """What a statutory return's header names the company by.

    Three fields, returned together rather than one at a time, because a return
    freezes them **as a set**: reading the fiscal code now and the CAEM code after
    the next edit would produce a header describing two moments.

    The classifier codes are optional and the type says so. Neither classifier is
    in this repository, so a company card may legitimately carry neither -- and a
    return generated meanwhile records the absence instead of an invented code.
    """

    fiscal_code: str
    cuatm_code: str | None
    caem_code: str | None


def statutory_identity(company_id: uuid.UUID) -> StatutoryIdentity:
    """The header identity of a company, for a return that is about to freeze it."""
    row = Company.objects.filter(id=company_id).values("idno", "cuatm_code", "caem_code").first()
    if row is None:
        raise CompanyNotVisibleError(f"company {company_id} is not visible in this context")
    return StatutoryIdentity(
        fiscal_code=str(row["idno"]),
        cuatm_code=row["cuatm_code"],
        caem_code=row["caem_code"],
    )


@dataclass(frozen=True, slots=True)
class CompanyHeading:
    """What a printed document names the company by -- ADR-095.

    The legal name and the IDNO, and nothing the interface may call the company
    (`C39`): a document carries the name the registry knows.
    """

    legal_name: str
    idno: str


def company_heading(company_id: uuid.UUID) -> CompanyHeading:
    """The company as a printed document names it. Absent and not-visible are
    one answer, like every reader here."""
    row = Company.objects.filter(id=company_id).values("legal_name", "idno").first()
    if row is None:
        raise CompanyNotVisibleError(f"company {company_id} is not visible in this context")
    return CompanyHeading(legal_name=str(row["legal_name"]), idno=str(row["idno"]))


def accounting_start_date(company_id: uuid.UUID) -> date:
    """The day this company's books start.

    Asked for by anything that has to date a company-wide default from the
    beginning rather than from today -- the role bindings, for one: installed on
    the day the chart happens to be created, they would not cover an entry dated
    earlier in the same year.
    """
    start = (
        Company.objects.filter(id=company_id)
        .values_list("accounting_start_date", flat=True)
        .first()
    )
    if start is None:
        raise CompanyNotVisibleError(f"company {company_id} is not visible in this context")
    return start


#: What ``update_company`` accepts, and the list is the rule -- ADR-083 section 3.
#:
#: Free to correct because nothing outside the system stands on them: a misspelt
#: legal name is a misspelt legal name, and a classifier code that arrives later
#: was recorded as absent rather than as wrong.
EDITABLE_FIELDS: Final = (
    "legal_name",
    "short_name",
    "registered_address",
    "cuatm_code",
    "caem_code",
)

#: What it refuses to touch, and **not** because the rule is "never".
#:
#: The rule is "not after the first posted entry": `idno` has left on issued
#: documents, while the currency and the start date have already been used to date
#: and value what is in the ledger. But *has this company got a posted entry* is a
#: fact `accounting` owns, and `platform` may not import `accounting` (CLAUDE.md
#: section 3) -- so the guard has no honest home here, and a service that accepted
#: the field while checking nothing would be worse than one that refuses.
#:
#: Refused entirely until that is decided (`OD-123`). Meanwhile they stay where
#: `tenant.idno` already is: operator commands, under the installation role --
#: the same shape as `OD-108`, one level down.
CONSEQUENTIAL_FIELDS: Final = (
    "idno",
    "functional_currency",
    "fiscal_year_start_month",
    "accounting_start_date",
)


class CompanyFieldNotEditableError(ApiError):
    """A field with consequences outside the system, asked for through the API."""

    code = "tenancy.company_field_not_editable"
    status = 409


class CompanyPermissionDeniedError(ApiError):
    """The caller may reach this company and may not change it.

    Translated from ``RoleError`` rather than raised by it: `identity` speaks in
    uppercase codes internally, the API speaks in dotted ones, and letting the
    first vocabulary out of the module would make an internal name part of the
    public contract (C10).
    """

    code = "tenancy.company_permission_denied"
    status = 403


class CompanyNotActiveError(ApiError):
    """The company is closed, so it is not edited either."""

    code = "tenancy.company_not_active"
    status = 409


def is_open_for_posting(company_id: uuid.UUID) -> bool:
    """Whether this company still accepts postings -- read by the posting gate.

    A fact, not a refusal: the refusal belongs to `assert_postable`, where `R12`
    already lives, and this module has no business raising an accounting error.

    The direction is what makes this legal: `accounting` depends on `platform`,
    never the other way round. It is also why the mirror image -- platform asking
    whether a company has postings -- has no equivalent here (`OD-123`).
    """
    status = Company.objects.filter(id=company_id).values_list("status", flat=True).first()
    if status is None:
        raise CompanyNotVisibleError(f"company {company_id} is not visible in this context")
    return bool(status == CompanyStatus.ACTIVE)


def update_company(company_id: uuid.UUID, **fields: Any) -> Company:
    """Correct a company's descriptive data -- `company.edit`, per company.

    The permission is checked against **this** company (ADR-083 section 2.2): a
    key held on another company of the same tenant opens nothing here.
    """
    context = current_context()
    if context is None:
        raise MissingTenantContextError("update_company needs a tenant context")

    refused = [name for name in fields if name in CONSEQUENTIAL_FIELDS]
    if refused:
        raise CompanyFieldNotEditableError(
            f"{', '.join(sorted(refused))} cannot be changed through the interface: "
            f"the guard that would allow it -- whether this company has a posted entry -- "
            f"is a fact platform cannot read (OD-123)"
        )
    unknown = [name for name in fields if name not in EDITABLE_FIELDS]
    if unknown:
        raise CompanyFieldNotEditableError(f"{', '.join(sorted(unknown))} is not an editable field")

    with transaction.atomic():
        # Visibility first, permission second, and the order is a rule: a 403 on
        # a company this caller cannot see would confirm that the id exists
        # somewhere (IZ-04). Absent, never forbidden.
        company = Company.objects.select_for_update().filter(id=company_id).first()
        if company is None:
            raise CompanyNotVisibleError(f"company {company_id} is not visible in this context")

        require_permission_on(context.user_id, company_id, "company.edit")

        if company.status != CompanyStatus.ACTIVE:
            raise CompanyNotActiveError(f"company {company_id} is {company.status}")

        before = {name: getattr(company, name) for name in fields}
        for name, value in fields.items():
            setattr(company, name, value)
        company.save(update_fields=[*fields, "updated_at"])

        record(
            action="company.updated",
            entity_type="company",
            entity_id=company.id,
            old_value=_audited(before),
            new_value=_audited(fields),
        )
        return company


def close_company(company_id: uuid.UUID, reason: str) -> Company:
    """Stop this company receiving postings -- `company.close`, per company.

    **Nothing in the ledger moves.** Closing is not deletion and cannot be: every
    accounting table points at the company with `PROTECT`, the posted ledger is
    immutable (`R10`), and the retention period is somebody else's obligation.
    What changes is that the engine refuses new postings, through
    `is_open_for_posting` -- and until ADR-083 that status was read by nothing,
    which made it a promise rather than a rule.

    ``reason`` is required and recorded. A company that stopped operating and one
    closed by mistake look identical afterwards, and only the reason tells them
    apart.
    """
    context = current_context()
    if context is None:
        raise MissingTenantContextError("close_company needs a tenant context")
    if not reason.strip():
        raise CompanyNotActiveError("closing a company states a reason")

    with transaction.atomic():
        # Visibility before permission, as in `update_company` and for the same
        # reason.
        company = Company.objects.select_for_update().filter(id=company_id).first()
        if company is None:
            raise CompanyNotVisibleError(f"company {company_id} is not visible in this context")

        require_permission_on(context.user_id, company_id, "company.close")

        if company.status == CompanyStatus.CLOSED:
            return company

        previous = company.status
        company.status = CompanyStatus.CLOSED
        company.save(update_fields=["status", "updated_at"])

        record(
            action="company.closed",
            entity_type="company",
            entity_id=company.id,
            old_value={"status": previous},
            new_value={"status": CompanyStatus.CLOSED, "reason": reason},
        )
        return company


def _audited(fields: dict[str, Any]) -> dict[str, Any]:
    """Audit values as text, because the trail is read, not replayed."""
    return {name: None if value is None else str(value) for name, value in fields.items()}


def require_permission_on(user_id: uuid.UUID, company_id: uuid.UUID, permission_key: str) -> None:
    """The permission check, with its refusal translated and nothing else caught.

    Only ``PERMISSION_DENIED`` becomes a 403. ``PERMISSION_CHECK_NOT_SELF`` is a
    programming mistake -- asking about somebody else's rights -- and flattening
    it into "you may not" would hide the bug behind a plausible answer.
    """
    try:
        require_company_permission(user_id, company_id, permission_key)
    except RoleError as exc:
        if exc.code != "PERMISSION_DENIED":
            raise
        raise CompanyPermissionDeniedError(f"{permission_key} is required on this company") from exc
