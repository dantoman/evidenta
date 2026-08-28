"""Creating a company -- `P-9`, the privileged path of ADR-040.

The application role cannot do this with ordinary statements, and the reason is
in the policy rather than in a service: `company` requires
`rls.has_company_access(id)` on both `USING` and `WITH CHECK`, the access row
requires the company, and the company requires the access row. Measured on the
live policy, not inferred from the specification.

So the insert happens inside `rls.provision_company`, a `SECURITY DEFINER`
function with a narrow signature that carries no SQL and no table names. What it
may do is fixed there: one company, in a tenant the caller already has access to,
with the role the caller already holds from their membership. It cannot create a
user, cannot widen a permission, cannot touch an existing company.

**No fiscal year here.** Opening an exercise is `accounting`, and `platform` does
not import `accounting` (DG). The composition belongs to the caller.
"""

from __future__ import annotations

import uuid
from datetime import date

from django.db import connection, transaction

from evidenta.platform.api.errors import ApiError
from evidenta.platform.audit.services.recording import record
from evidenta.platform.numbering.services.templates import create_general_template
from evidenta.platform.rls.context import MissingTenantContextError, current_context
from evidenta.platform.tenancy.models import Company


class CompanyIdnoTakenError(ApiError):
    """One IDNO identifies one legal entity, and the tenant already has it."""

    code = "tenancy.company_idno_taken"
    status = 409


class CompanyProvisioningRefusedError(ApiError):
    """The privileged path refused: no active membership, or no tenant access."""

    code = "tenancy.company_provisioning_refused"
    status = 403


@transaction.atomic
def provision_company(
    *,
    idno: str,
    legal_name: str,
    functional_currency: str = "MDL",
    accounting_start: date | None = None,
    fiscal_year_start_month: int = 1,
) -> Company:
    """Create one company in the tenant in context, and return it.

    ``accounting_start`` defaults to the first day of the current calendar year,
    which is also what a calendar exercise starts on. It is stored on the company
    rather than derived later: a company whose books start mid-year is ordinary,
    and the date has to survive the year it was entered in.
    """
    context = current_context()
    if context is None:
        raise MissingTenantContextError("provision_company needs a tenant context")

    start = accounting_start or date(date.today().year, 1, 1)

    if Company.objects.filter(idno=idno).exists():
        # Answered before the function so the caller gets the stable code rather
        # than a database error string. The function refuses it too -- this is
        # the message, not the guarantee.
        raise CompanyIdnoTakenError(f"IDNO {idno} already exists in this tenant")

    with connection.cursor() as cursor:
        try:
            cursor.execute(
                # Cast every parameter. psycopg sends them untyped, and with six
                # of them Postgres cannot resolve the overload -- it answered
                # "no function matches the given name and argument types" for a
                # function that was right there. Measured, not guessed.
                "SELECT rls.provision_company("
                "%s::uuid, %s::text, %s::text, %s::text, %s::date, %s::smallint)",
                [
                    str(context.tenant_id),
                    idno,
                    legal_name,
                    functional_currency,
                    start,
                    fiscal_year_start_month,
                ],
            )
            row = cursor.fetchone()
        except Exception as error:
            message = str(error)
            if "IDNO" in message:
                raise CompanyIdnoTakenError(message) from error
            raise CompanyProvisioningRefusedError(message) from error

    company_id = uuid.UUID(str(row[0]))
    company = Company.objects.get(id=company_id)

    # A general numbering template, chosen here rather than invented later.
    # `numbering.resolve_template` refuses a document type with no template and
    # is right to: a number nobody chose would go out on documents that leave the
    # company. Choosing one at creation is the other half of that -- without it a
    # brand-new company cannot post its first journal entry, which is where this
    # was found. The company can change it; what it cannot do is have none.
    # Valid from the day the books start, not from today: a document dated
    # before the series existed could otherwise not be numbered at all.
    create_general_template(context.tenant_id, company_id, valid_from=start)

    # Explicit, from the service (C4). Who created which company, and when, is
    # not something to reconstruct from row timestamps.
    record(
        action="tenancy.company_provisioned",
        entity_type="company",
        entity_id=company.id,
        company_id=company.id,
        new_value={
            "idno": idno,
            "legal_name": legal_name,
            "functional_currency": functional_currency,
            "accounting_start_date": str(start),
        },
    )
    return company
