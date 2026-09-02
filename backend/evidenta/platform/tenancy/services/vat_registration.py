"""Registering a company for VAT -- the write path `tax_status_at` reads.

`company_vat_registration` has existed since F0 and was written only by tests
and by hand: the product had a dated status and no door to it, so no company
created through the product could ever be a VAT payer. Step 6 needs one, because
the whole treatment hangs off the answer to *was this company registered on the
day of the document* (ADR-088, ADR-089).

**A registration is a dated fact, never a toggle.** It starts on a day and may
end on one; two registrations cannot cover the same day, because
`tax_status_at` would then have two answers for one question. What is refused
here is exactly that overlap.

**No striking-off here.** Ending a registration is art. 114 para. (2): the final
VAT fiscal period runs from the month of the cancellation to the month the act
entered into force, and that period lives in `accounting/periods`, which
`platform` does not import. Recording the end date and closing the period are
two calls from the client, like creating a company and opening its exercise --
and the second is not built in this step, so a registration created here is
open-ended unless the caller already knows when it ended.

**Guarded by `company.edit`, per company** (ADR-083): whether a company is a VAT
payer is data about the company, and the key that corrects its name is the key
that records its registration.
"""

from __future__ import annotations

import uuid
from datetime import date

from django.db import transaction
from django.db.models import Q

from evidenta.platform.api.errors import ApiError
from evidenta.platform.audit.services.recording import record
from evidenta.platform.rls.context import MissingTenantContextError, current_context
from evidenta.platform.tenancy.models import Company, CompanyVatRegistration
from evidenta.platform.tenancy.services.companies import (
    CompanyNotVisibleError,
    require_permission_on,
)


class VatRegistrationMalformedError(ApiError):
    code = "tenancy.vat_registration_malformed"
    status = 422


class VatRegistrationOverlapError(ApiError):
    """Two registrations over one day would give `tax_status_at` two answers."""

    code = "tenancy.vat_registration_overlap"
    status = 409


def register_for_vat(
    company_id: uuid.UUID,
    *,
    vat_code: str,
    valid_from: date,
    valid_to: date | None = None,
    source: str | None = None,
) -> CompanyVatRegistration:
    """Record that the company is a VAT payer from ``valid_from``.

    ``valid_to`` is the **last day** the registration applies -- inclusive, the
    way `tax_status_at` reads the column -- and is given only when the end is
    already known, as when a past registration is being entered. ``source`` is
    free text for the act or certificate; the number and date of the SFS
    certificate are what an inspector asks for, and a row without them is not
    wrong, only less useful.
    """
    context = current_context()
    if context is None:
        raise MissingTenantContextError("register_for_vat needs a tenant context")

    code = (vat_code or "").strip()
    if not code:
        raise VatRegistrationMalformedError(
            "a VAT registration carries the code the certificate assigned; without it "
            "the registration cannot be printed on an invoice"
        )
    if valid_to is not None and valid_to <= valid_from:
        raise VatRegistrationMalformedError(
            f"a registration cannot end on {valid_to}, on or before the day it starts "
            f"({valid_from})"
        )

    with transaction.atomic():
        # Visibility first, permission second -- the order `update_company` fixes,
        # and for the same reason: a 403 on an invisible company confirms the id
        # exists somewhere (IZ-04).
        company = Company.objects.select_for_update().filter(id=company_id).first()
        if company is None:
            raise CompanyNotVisibleError(f"company {company_id} is not visible in this context")

        require_permission_on(context.user_id, company_id, "company.edit")

        # Overlap over the inclusive interval [valid_from, valid_to]. An open
        # registration reaches forever, so anything starting on or after its
        # first day collides with it.
        clashing = CompanyVatRegistration.objects.filter(company_id=company_id).filter(
            Q(valid_to__isnull=True) | Q(valid_to__gte=valid_from)
        )
        if valid_to is not None:
            clashing = clashing.filter(valid_from__lte=valid_to)
        clash = clashing.order_by("valid_from").first()
        if clash is not None:
            raise VatRegistrationOverlapError(
                f"the company is already registered from {clash.valid_from}"
                f"{'' if clash.valid_to is None else f' to {clash.valid_to}'}; a second "
                f"registration over the same days would give two answers to one question"
            )

        registration = CompanyVatRegistration.objects.create(
            tenant_id=company.tenant_id,
            company_id=company_id,
            vat_code=code,
            valid_from=valid_from,
            valid_to=valid_to,
            source=(source or "").strip() or None,
        )

        record(
            action="company.vat_registered",
            entity_type="company_vat_registration",
            entity_id=registration.id,
            company_id=company_id,
            new_value={
                "vat_code": code,
                "valid_from": str(valid_from),
                "valid_to": None if valid_to is None else str(valid_to),
                "source": registration.source,
            },
        )
        return registration


def vat_registrations_of(company_id: uuid.UUID) -> list[CompanyVatRegistration]:
    """Every registration of the company, oldest first. The policy decides visibility."""
    return list(CompanyVatRegistration.objects.filter(company_id=company_id).order_by("valid_from"))
