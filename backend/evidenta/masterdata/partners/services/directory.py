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
from collections.abc import Iterable, Sequence
from datetime import date
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Q

from evidenta.masterdata.partners.models import Partner, PartnerKind, PartnerVatRegistration
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


class PartnerNameCollisionError(ApiError):
    """A second nameless record for a name that already exists.

    `R20` deduplicates by natural business keys, and for a partner that key is
    the IDNO -- which the unique index already enforces. A record with **no**
    identifier has no key at all, so nothing stops a second one, and the two then
    split one counterparty's balance between them. The split does not announce
    itself: it surfaces later as a reconciliation that will not close.

    Not a database constraint, and the reason is that the rule is not true in
    general: two real firms can carry the same name, and a constraint would refuse
    the second one forever. What is refused here is narrower -- a second record
    when **neither** side has anything to tell them apart -- and the message says
    the way out, which is to give one of them its IDNO.
    """

    code = "partners.name_collision"
    status = 409


class PartnerNotFoundError(ApiError):
    code = "partners.not_found"
    status = 404


class VatValidFromRequiredError(ApiError):
    """A VAT code with no date it started applying on.

    Refused rather than dated to today. Whether a counterparty was registered on
    the day of a document decides how that document is treated, and a start date
    invented at data-entry time would answer that question with the date somebody
    happened to type the card -- silently, and wrongly for every document before
    it.
    """

    code = "partners.vat_valid_from_required"
    status = 422


class VatRegistrationOverlapError(ApiError):
    code = "partners.vat_registration_overlap"
    status = 409


def create_partner(
    *,
    tenant_id: uuid.UUID,
    legal_name: str,
    kind: str = PartnerKind.LEGAL_ENTITY,
    idno: str | None = None,
    idnp: str | None = None,
    vat_code: str | None = None,
    vat_valid_from: date | None = None,
    short_name: str | None = None,
    internal_name: str | None = None,
    default_currency: str | None = None,
    default_payment_terms_days: int | None = None,
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

    code = (vat_code or "").strip()
    if code and vat_valid_from is None:
        raise VatValidFromRequiredError(
            "a VAT code needs the date the registration started. Whether the "
            "counterparty was registered on the day of a document decides how that "
            "document is treated, and there is no safe date to assume."
        )

    # Only when the newcomer has nothing to be told apart by. With an IDNO the
    # unique index is the authority, and two same-named firms are a fact of the
    # register rather than a mistake.
    if idno is None and idnp is None:
        nameless_twin = (
            Partner.objects.filter(
                tenant_id=tenant_id, legal_name__iexact=name, idno__isnull=True, idnp__isnull=True
            )
            .exclude(is_active=False)
            .first()
        )
        if nameless_twin is not None:
            raise PartnerNameCollisionError(
                f"a partner named {name!r} without an IDNO already exists; a second "
                f"nameless record splits one counterparty's balance between two, and "
                f"the split surfaces as a reconciliation that will not close. Give "
                f"one of them its IDNO, or use the record that is already there"
            )

    try:
        with transaction.atomic():
            partner = Partner.objects.create(
                tenant_id=tenant_id,
                legal_name=name,
                short_name=(short_name or "").strip() or None,
                internal_name=(internal_name or "").strip() or None,
                kind=kind,
                idno=idno,
                idnp=idnp,
                default_currency=(default_currency or "").strip().upper() or None,
                default_payment_terms_days=default_payment_terms_days,
                is_customer=is_customer,
                is_supplier=is_supplier,
            )
            if code and vat_valid_from is not None:
                PartnerVatRegistration.objects.create(
                    tenant_id=tenant_id,
                    partner=partner,
                    vat_code=code,
                    valid_from=vat_valid_from,
                )
            return partner
    except IntegrityError as clash:
        # The unique constraint is the authority, not a prior SELECT: two
        # requests arriving together would both find nothing and both insert.
        if "partner_idno_unique" in str(clash):
            raise PartnerDuplicateError(
                f"a partner with IDNO {idno} already exists in this tenant; a second "
                f"record splits the balances between them, and the split surfaces "
                f"as a reconciliation that will not close"
            ) from clash
        if "partner_vat_registration_no_overlap" in str(clash):
            raise VatRegistrationOverlapError(
                "the partner already has a VAT registration covering that period"
            ) from clash
        raise


@transaction.atomic
def register_vat(
    partner_id: uuid.UUID,
    *,
    vat_code: str,
    valid_from: date,
    source: str | None = None,
) -> PartnerVatRegistration:
    """Record that a counterparty is a VAT payer, from a date.

    A new row rather than an edit of the last one. A partner struck off and
    registered again receives a different code, and overwriting would erase the
    code the invoices already issued still carry.
    """
    partner = Partner.objects.filter(id=partner_id).first()
    if partner is None:
        raise PartnerNotFoundError(f"partner {partner_id} is not visible in this context")
    code = (vat_code or "").strip()
    if not code:
        raise PartnerMalformedError("a VAT registration needs the code it was issued under")
    try:
        return PartnerVatRegistration.objects.create(
            tenant_id=partner.tenant_id,
            partner=partner,
            vat_code=code,
            valid_from=valid_from,
            source=source,
        )
    except IntegrityError as clash:
        if "partner_vat_registration_no_overlap" in str(clash):
            raise VatRegistrationOverlapError(
                f"partner {partner_id} already has a VAT registration covering "
                f"{valid_from}; two answers to 'was this a VAT payer then' is no answer"
            ) from clash
        raise


@transaction.atomic
def deregister_vat(partner_id: uuid.UUID, *, last_day: date) -> PartnerVatRegistration:
    """Close the open registration on a day -- struck off, not deleted."""
    registration = (
        PartnerVatRegistration.objects.select_for_update()
        .filter(partner_id=partner_id, valid_to__isnull=True)
        .order_by("-valid_from")
        .first()
    )
    if registration is None:
        raise PartnerNotFoundError(f"partner {partner_id} has no open VAT registration to close")
    if last_day < registration.valid_from:
        raise VatRegistrationOverlapError(
            f"a registration cannot end on {last_day}, before it starts on "
            f"{registration.valid_from}"
        )
    # The column is the half-open upper bound: the first day the registration no
    # longer applies. `last_day` is what a human says.
    registration.valid_to = date.fromordinal(last_day.toordinal() + 1)
    registration.save(update_fields=["valid_to"])
    return registration


def vat_registration_on(partner_id: uuid.UUID, on: date) -> PartnerVatRegistration | None:
    """The registration in force on a date, or None. Half-open ``[from, to)``.

    ``on`` is required and has no default. The question a document asks is "was
    this counterparty a VAT payer on the day of the document", and a resolver
    that could fall back to today would answer a different question -- correctly,
    and about the wrong day (ADR-044).
    """
    return (
        PartnerVatRegistration.objects.filter(partner_id=partner_id, valid_from__lte=on)
        .filter(Q(valid_to__isnull=True) | Q(valid_to__gt=on))
        .first()
    )


def is_vat_registered(partner_id: uuid.UUID, on: date) -> bool:
    return vat_registration_on(partner_id, on) is not None


def partners_of(
    tenant_id: uuid.UUID,
    *,
    query: str | None = None,
    role: str | None = None,
    include_inactive: bool = False,
) -> list[dict[str, Any]]:
    """The directory, searchable by the two things a person has in front of them.

    ``query`` matches the legal name, the short name, the internal name or the
    IDNO -- the internal one included because that is what a Russian-speaking
    accountant typed and therefore what they will search for (ADR-034).
    Case-insensitive
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
            | Q(internal_name__icontains=needle)
            | Q(idno__startswith=needle)
        )

    page = list(rows.order_by("legal_name")[:200])
    return [_row(partner, _open_codes(page)) for partner in page]


def partner_in_context(partner_id: uuid.UUID) -> dict[str, Any]:
    partner = Partner.objects.filter(id=partner_id).first()
    if partner is None:
        raise PartnerNotFoundError(f"partner {partner_id} is not visible in this context")
    return _row(partner, _open_codes([partner]))


#: What a person may correct from the partner's own form.
#:
#: The identity is **not** in it, and that is the same line ADR-083 drew for a
#: company: `idno` and `idnp` are what a document already issued names the
#: counterparty by, and what the unique constraint uses to keep two records from
#: splitting one balance (`R20`). A typo in one is a correction with
#: consequences -- it can move posted history from one partner to another -- so it
#: is an operator act, not a form field.
#:
#: `kind` is out for the same reason once removed: it decides which identifier
#: applies, so changing it would silently orphan the one that is filled.
#:
#: The VAT code is out because it is **not a field**: registration is a dated
#: state (`register_vat` / `deregister_vat`), and overwriting a code would
#: rewrite how documents issued before the change are treated.
EDITABLE = (
    "legal_name",
    "short_name",
    "internal_name",
    "default_currency",
    "default_payment_terms_days",
    "is_customer",
    "is_supplier",
)


def update_partner(partner_id: uuid.UUID, **changes: Any) -> dict[str, Any]:
    """Correct what a partner's form owns. Absent keys are left alone.

    A partial update, deliberately: a form that sent every field would clear
    whatever it did not render, and the first screen to render half the record
    would silently empty the other half.
    """
    partner = Partner.objects.filter(id=partner_id).first()
    if partner is None:
        raise PartnerNotFoundError(f"partner {partner_id} is not visible in this context")

    unknown = set(changes) - set(EDITABLE)
    if unknown:
        # Named, not ignored: a caller that sends `idno` believes it is being
        # applied, and a silent drop is how a wrong IDNO survives a correction.
        raise PartnerMalformedError(
            f"{sorted(unknown)} cannot be changed from the partner form: identity "
            f"and VAT registration are corrected on their own paths"
        )

    if "legal_name" in changes:
        name = (changes["legal_name"] or "").strip()
        if not name:
            raise PartnerMalformedError(
                "a partner needs a legal name: it is what appears on documents and "
                "in registers, and nothing else identifies it there (C39)"
            )
        changes["legal_name"] = name

    for blankable in ("short_name", "internal_name"):
        if blankable in changes:
            changes[blankable] = (changes[blankable] or "").strip() or None

    if "default_currency" in changes:
        changes["default_currency"] = (changes["default_currency"] or "").strip().upper() or None

    # Evaluated on the row as it will be, not on what arrived: a request that
    # only clears `is_customer` still has to leave a partner something can be
    # posted against.
    after_customer = bool(changes.get("is_customer", partner.is_customer))
    after_supplier = bool(changes.get("is_supplier", partner.is_supplier))
    if not (after_customer or after_supplier):
        raise PartnerMalformedError(
            "a partner is a customer, a supplier, or both. Neither is a record "
            "nothing can be posted against, and the database refuses it too"
        )

    for field, value in changes.items():
        setattr(partner, field, value)
    partner.save(update_fields=[*changes, "updated_at"])
    return _row(partner, _open_codes([partner]))


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
    return _row(partner, _open_codes([partner]))


def _open_codes(partners: Iterable[Partner]) -> dict[uuid.UUID, str]:
    """The still-open VAT registration of each partner, in one query.

    "Open" is a fact about the row -- `valid_to IS NULL` -- not a resolution
    against a date, so the directory can show it without answering a question
    nobody asked. A document that needs the status *on a day* calls
    `vat_registration_on`, which takes the day.
    """
    ids = [partner.id for partner in partners]
    rows = PartnerVatRegistration.objects.filter(partner_id__in=ids, valid_to__isnull=True)
    return {row.partner_id: row.vat_code for row in rows.order_by("valid_from")}


def _row(partner: Partner, open_codes: dict[uuid.UUID, str]) -> dict[str, Any]:
    code = open_codes.get(partner.id)
    return {
        "id": str(partner.id),
        "legal_name": partner.legal_name,
        "short_name": partner.short_name,
        "internal_name": partner.internal_name,
        "display_name": partner.internal_name or partner.legal_name,
        "kind": partner.kind,
        "idno": partner.idno,
        "idnp": partner.idnp,
        "vat_code": code,
        "vat_registered": code is not None,
        "default_currency": partner.default_currency,
        "default_payment_terms_days": partner.default_payment_terms_days,
        "is_customer": partner.is_customer,
        "is_supplier": partner.is_supplier,
        "is_active": partner.is_active,
    }


def legal_names_for(partner_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, str]:
    """The legal name of each partner, for the documents and registers that name them.

    **The legal name, never the internal one** (`C39`, ADR-034): the internal name
    exists for lists, search and imports, and a register that printed it would be
    the non-conforming artefact `OD-40` is open about.

    One query for many ids, because the caller is a report: a register asking per
    row is how a page of forty documents becomes forty round trips.

    Missing ids are simply absent from the result rather than raising. A report
    that met a partner it cannot see -- deleted, or in another company's reach --
    prints what it knows and says nothing it does not, which is what an empty cell
    means to the person reading it.
    """
    rows = Partner.objects.filter(id__in=tuple(partner_ids)).values_list("id", "legal_name")
    return {partner_id: str(name) for partner_id, name in rows}
