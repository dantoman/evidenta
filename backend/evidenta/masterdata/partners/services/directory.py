"""The partner directory -- creating one, and finding one again.

A partner is tenant-level, not company-level: the same legal entity is the same
entity for every company of a firm, and a per-company copy is how a holding ends
up with two records for one supplier whose balances no longer reconcile. The
per-company relationship -- which accounts this company posts it to -- lives on
``CompanyPartner`` and is not exposed here yet; nothing at F1 reads it, and a
surface nobody calls is a surface that drifts from what it claims.

**Searching is the reason this module exists at all.** A screen that asks a
person for a `partner_id` is a screen nobody can fill in correctly. So the search
matches the two things a person actually has in front of them: the name on the
document, and the IDNO on it.

`legal_name` is what documents and registers carry (`C39`, ADR-034). ``short_name``
exists for the interface and never reaches a printed document.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from django.db import IntegrityError
from django.db.models import Q

from evidenta.masterdata.partners.models import Partner, PartnerKind
from evidenta.platform.api.errors import ApiError

#: Moldovan IDNO: thirteen digits. The same shape the company endpoint enforces;
#: written here rather than imported so `masterdata` does not reach into
#: `platform.tenancy`'s serializers for a regular expression (`D6`).
IDNO = re.compile(r"^\d{13}$")

#: IDNP, the personal number, is also thirteen digits. Distinguishing them is not
#: this module's job: the *kind* says which column the number belongs in, and a
#: person entering an IDNO under `individual` is a data question, not a format one.
IDNP = re.compile(r"^\d{13}$")


class PartnerMalformedError(ApiError):
    code = "partners.malformed"
    status = 422


class PartnerDuplicateError(ApiError):
    """Two records for one IDNO inside a tenant.

    Refused rather than merged: the balances have already split between them by
    the time anybody notices, and a merge is a decision with accounting
    consequences that no automatic path should take.
    """

    code = "partners.idno_taken"
    status = 409


class PartnerNotFoundError(ApiError):
    code = "partners.not_found"
    status = 404


def create_partner(
    *,
    tenant_id: uuid.UUID,
    legal_name: str,
    kind: str = PartnerKind.LEGAL_ENTITY,
    idno: str | None = None,
    idnp: str | None = None,
    vat_code: str | None = None,
    short_name: str | None = None,
    is_customer: bool = False,
    is_supplier: bool = False,
) -> Partner:
    """Record a partner. At least one role, and a legal name that is not blank.

    Both roles on one record when the counterparty is both, which it frequently
    is. Two records would disagree about the address the first time one of them
    is corrected.
    """
    name = (legal_name or "").strip()
    if not name:
        raise PartnerMalformedError(
            "a partner needs a legal name: it is what appears on documents and in "
            "registers, and nothing else identifies it there (C39)"
        )
    if not (is_customer or is_supplier):
        raise PartnerMalformedError(
            "a partner is a customer, a supplier, or both. Neither is a record "
            "nothing can be posted against, and the database refuses it too"
        )
    if kind not in PartnerKind.values:
        raise PartnerMalformedError(f"{kind!r} is not a partner kind")

    if idno is not None and not IDNO.match(idno):
        raise PartnerMalformedError(f"{idno!r} is not an IDNO: thirteen digits, no spaces")
    if idnp is not None and not IDNP.match(idnp):
        raise PartnerMalformedError(f"{idnp!r} is not an IDNP: thirteen digits, no spaces")

    try:
        return Partner.objects.create(
            tenant_id=tenant_id,
            legal_name=name,
            short_name=(short_name or "").strip() or None,
            kind=kind,
            idno=idno,
            idnp=idnp,
            vat_code=(vat_code or "").strip() or None,
            is_customer=is_customer,
            is_supplier=is_supplier,
        )
    except IntegrityError as clash:
        # The unique constraint is the authority, not a prior SELECT: two
        # requests arriving together would both find nothing and both insert.
        if "partner_idno_unique" in str(clash):
            raise PartnerDuplicateError(
                f"a partner with IDNO {idno} already exists in this tenant; a second "
                f"record splits the balances between them, and the split surfaces "
                f"as a reconciliation that will not close"
            ) from clash
        raise


def partners_of(
    tenant_id: uuid.UUID,
    *,
    query: str | None = None,
    role: str | None = None,
    include_inactive: bool = False,
) -> list[dict[str, Any]]:
    """The directory, searchable by the two things a person has in front of them.

    ``query`` matches the legal name, the short name or the IDNO. Case-insensitive
    on the names and exact-prefix on the number, because a person copying an IDNO
    off an invoice copies it from the start.

    ``role`` is ``customer`` or ``supplier``. A partner that is both appears under
    either, which is the point of one record with two flags.
    """
    rows = Partner.objects.filter(tenant_id=tenant_id)
    if not include_inactive:
        rows = rows.filter(is_active=True)
    if role == "customer":
        rows = rows.filter(is_customer=True)
    elif role == "supplier":
        rows = rows.filter(is_supplier=True)
    elif role is not None:
        raise PartnerMalformedError(f"{role!r} is not a role: customer or supplier")

    if query:
        needle = query.strip()
        rows = rows.filter(
            Q(legal_name__icontains=needle)
            | Q(short_name__icontains=needle)
            | Q(idno__startswith=needle)
        )

    return [_row(partner) for partner in rows.order_by("legal_name")[:200]]


def partner_in_context(partner_id: uuid.UUID) -> dict[str, Any]:
    partner = Partner.objects.filter(id=partner_id).first()
    if partner is None:
        raise PartnerNotFoundError(f"partner {partner_id} is not visible in this context")
    return _row(partner)


def set_partner_active(partner_id: uuid.UUID, *, active: bool) -> dict[str, Any]:
    """Retire a partner, or bring one back. Never delete.

    Entries posted against it still name it, and a deleted partner would leave
    them pointing at nothing -- the same reason a retired operation template
    stays readable.
    """
    partner = Partner.objects.filter(id=partner_id).first()
    if partner is None:
        raise PartnerNotFoundError(f"partner {partner_id} is not visible in this context")
    partner.is_active = active
    partner.save(update_fields=["is_active", "updated_at"])
    return _row(partner)


def _row(partner: Partner) -> dict[str, Any]:
    return {
        "id": str(partner.id),
        "legal_name": partner.legal_name,
        "short_name": partner.short_name,
        "kind": partner.kind,
        "idno": partner.idno,
        "idnp": partner.idnp,
        "vat_code": partner.vat_code,
        "is_customer": partner.is_customer,
        "is_supplier": partner.is_supplier,
        "is_active": partner.is_active,
    }
