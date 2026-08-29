"""The document lifecycle: ciornă -> validat -> anulat.

Three moves and one refusal, and the refusal is the load-bearing part.

**A draft is free.** It is edited, its positions are replaced, it is deleted
without trace beyond the audit line that says so. Nothing has happened yet.

**Validation allocates the number and freezes the document.** From that instant
the row is immutable except for the columns the lifecycle itself writes, and that
is enforced by a trigger rather than by this module: a bulk import, a data
migration and a psql session all bypass every service ever written, and those are
exactly the paths on which a validated document gets quietly edited.

**Cancellation is allowed only before the accounting effect exists**, and it
carries a reason. A cancelled document keeps its number: the gap is permanent and
is the point, because a register with reassigned numbers is not a register.

``posted`` is declared in the state machine and unreachable from here. Adding the
transition means adding a function beside `validate`, not reshaping anything
below it -- which is why the number, the freeze and the history are already
where posting will find them.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from django.db import transaction

from evidenta.platform.audit.services.recording import record
from evidenta.platform.documents.errors import (
    CancelAfterPostingError,
    CancellationReasonRequiredError,
    CurrencyMismatchError,
    DocumentNotEditableError,
    DocumentNotFoundError,
    ExchangeRateRequiredError,
    ExternalNumberNotAllowedError,
    InvalidTransitionError,
    NoLinesError,
    PartnerRequiredError,
    RateTermUnknownError,
)
from evidenta.platform.documents.models import (
    DOCUMENT_TRANSITIONS,
    EDITABLE_STATES,
    Document,
    DocumentState,
    RateTerm,
)
from evidenta.platform.documents.registry import DocumentTypeSpec, spec_for
from evidenta.platform.documents.services.history import record_event, require_context
from evidenta.platform.numbering.regimes import NumberingRegime
from evidenta.platform.numbering.services.allocation import allocate, resolve_template
from evidenta.platform.tenancy.services.companies import functional_currency


def assert_transition(current: str, target: str) -> None:
    """Refuse a move the machine does not contain.

    Absent pairs are refused rather than defaulted, so adding a move is an edit
    to `DOCUMENT_TRANSITIONS` -- visible, reviewable -- instead of a condition
    slipped into a branch.
    """
    if (current, target) not in DOCUMENT_TRANSITIONS:
        raise InvalidTransitionError(
            f"a document cannot move from {current} to {target}; the allowed moves "
            f"are declared in DOCUMENT_TRANSITIONS"
        )


def get_document(document_id: uuid.UUID) -> Document:
    """The document, read under the policy.

    A document of another tenant is *absent*, not forbidden (IZ-04): a 403 would
    confirm that the identifier exists.
    """
    document = Document.objects.filter(id=document_id).first()
    if document is None:
        raise DocumentNotFoundError(f"document {document_id} is not visible in this context")
    return document


@transaction.atomic
def open_draft(
    *,
    company_id: uuid.UUID,
    document_type: str,
    document_date: date,
    accounting_date: date | None = None,
    partner_id: uuid.UUID | None = None,
    currency: str | None = None,
    exchange_rate: Decimal | None = None,
    external_number: str | None = None,
    source_document_id: uuid.UUID | None = None,
    notes: str | None = None,
    rate_term: str = RateTerm.PAYMENT_DATE,
) -> Document:
    """Start a document. Nothing is committed to by opening one.

    ``accounting_date`` defaults to the document's own date, which is what the
    two dates are for an ordinary document entered on the day it happened. It is
    a **default, not an identity**: the column exists precisely so a delivery on
    the 28th recorded on the 5th can say both, and any caller that knows better
    passes its own.

    ``exchange_rate`` is required when the currency is not the company's own and
    is refused when it is -- an amount already in the functional currency
    converts at exactly 1 (Spec B section 1.3). **No rate is looked up here.**
    Art. 97 alin. (6) names a date that is neither the document's nor the
    posting's, and which date that is remains open (ADR-039, `DN-04`); picking
    one would close the decision from the least entitled layer.
    """
    context = require_context()
    spec = spec_for(document_type)

    own_currency = functional_currency(company_id)
    currency = currency or own_currency
    rate = _resolve_rate(currency, own_currency, exchange_rate)
    if rate_term not in RateTerm.values:
        raise RateTermUnknownError(
            f"rate_term {rate_term!r} is not one of {list(RateTerm.values)}: pct. 19 names "
            f"three terms and no fourth"
        )

    # The regime is a property of the series in force on the document's date, and
    # it is copied rather than looked up later: a series can be superseded, and
    # what a document *was* numbered under has to stay legible afterwards.
    regime = resolve_template(company_id, document_type, document_date).regime
    if regime == NumberingRegime.OWN and external_number is not None:
        raise ExternalNumberNotAllowedError(
            f"the series in force for {document_type!r} on {document_date} numbers "
            f"documents itself; a document cannot also carry an identifier issued "
            f"elsewhere"
        )

    document = Document.objects.create(
        tenant_id=context.tenant_id,
        company_id=company_id,
        document_type=spec.code,
        document_date=document_date,
        accounting_date=accounting_date or document_date,
        partner_id=partner_id,
        currency=currency,
        exchange_rate=rate,
        numbering_regime=regime,
        external_number=external_number,
        source_document_id=source_document_id,
        state=DocumentState.DRAFT,
        created_by_id=context.user_id,
        notes=notes,
        rate_term=rate_term,
    )

    record_event(
        document,
        event_type="document.drafted",
        to_state=DocumentState.DRAFT,
        detail={"document_type": spec.code, "regime": regime},
    )
    return document


@transaction.atomic
def update_draft(document_id: uuid.UUID, **fields: object) -> Document:
    """Change a draft. Anything past draft is refused here and by the trigger."""
    document = get_document(document_id)
    if document.state not in EDITABLE_STATES:
        raise DocumentNotEditableError(
            f"document {document.id} is {document.state}; a validated document is "
            f"frozen and a correction is a reversal"
        )
    allowed = {
        "document_date",
        "accounting_date",
        "partner_id",
        "currency",
        "exchange_rate",
        "external_number",
        "notes",
    }
    unknown = set(fields) - allowed
    if unknown:
        raise DocumentNotEditableError(
            f"{sorted(unknown)} are not fields of a draft that this service edits; "
            f"state, number and the lifecycle timestamps belong to the transitions"
        )
    for name, value in fields.items():
        setattr(document, name, value)
    document.save(update_fields=[*fields, "updated_at"])
    return document


@transaction.atomic
def validate(document_id: uuid.UUID) -> Document:
    """*Validat*: allocate the number, freeze the document, write the history.

    Everything the type declares is checked here rather than at creation, because
    a draft is allowed to be incomplete -- that is what a draft is.

    The number is taken **inside this transaction**, under the counter's row
    lock, and never at creation: a draft that reserved a number and was abandoned
    would burn one, and the register would carry a gap no document accounts for.

    Takes the identifier rather than the row, like every public service here: a
    module that had to hold a `Document` to validate one would have to import the
    document core's models, which is `D6`.
    """
    context = require_context()
    document = get_document(document_id)
    assert_transition(document.state, DocumentState.CONFIRMED)
    spec = spec_for(document.document_type)
    _assert_complete(document, spec)

    fields = ["state", "confirmed_by", "confirmed_at", "updated_at"]
    if document.numbering_regime == NumberingRegime.OWN:
        allocated = allocate(
            document.tenant_id,
            document.company_id,
            document.document_type,
            document.document_date,
        )
        document.series = allocated.series
        document.number = allocated.number
        document.formatted_number = allocated.formatted
        document.fiscal_year = allocated.fiscal_year
        fields += ["series", "number", "formatted_number", "fiscal_year"]

    document.state = DocumentState.CONFIRMED
    document.confirmed_by_id = context.user_id
    document.confirmed_at = datetime.now(UTC)
    document.save(update_fields=fields)

    record_event(
        document,
        event_type="document.validated",
        from_state=DocumentState.DRAFT,
        to_state=DocumentState.CONFIRMED,
        detail={"number": document.formatted_number, "external_number": document.external_number},
    )
    record(
        action="documents.validated",
        entity_type="document",
        entity_id=document.id,
        company_id=document.company_id,
        new_value={
            "document_type": document.document_type,
            "number": document.formatted_number,
            "external_number": document.external_number,
            "document_date": document.document_date.isoformat(),
        },
    )
    return document


@transaction.atomic
def cancel(document_id: uuid.UUID, *, reason: str) -> Document:
    """*Anulat*: allowed only before the accounting effect exists, with a reason.

    The number is **not** released. A cancelled document keeps it and the gap is
    permanent -- which is the property that makes the register answerable, and
    the reason a cancellation is a state rather than a deletion.
    """
    context = require_context()
    document = get_document(document_id)
    if document.state in {DocumentState.POSTED, DocumentState.COMPLETED}:
        raise CancelAfterPostingError(
            f"document {document.id} is {document.state}; after the accounting "
            f"effect exists the correction is a reversal and a re-entry (R10), "
            f"not a cancellation"
        )
    assert_transition(document.state, DocumentState.CANCELLED)
    if not reason.strip():
        raise CancellationReasonRequiredError(
            "a cancellation needs a reason: the register has to account for what "
            "was voided, not fall silent about it"
        )

    previous = document.state
    document.state = DocumentState.CANCELLED
    document.cancelled_by_id = context.user_id
    document.cancelled_at = datetime.now(UTC)
    document.cancellation_reason = reason.strip()
    document.save(
        update_fields=[
            "state",
            "cancelled_by",
            "cancelled_at",
            "cancellation_reason",
            "updated_at",
        ]
    )

    record_event(
        document,
        event_type="document.cancelled",
        from_state=previous,
        to_state=DocumentState.CANCELLED,
        detail={"reason": document.cancellation_reason},
    )
    record(
        action="documents.cancelled",
        entity_type="document",
        entity_id=document.id,
        company_id=document.company_id,
        old_value={"state": previous, "number": document.formatted_number},
        new_value={"state": DocumentState.CANCELLED, "reason": document.cancellation_reason},
    )
    return document


@transaction.atomic
def delete_draft(document_id: uuid.UUID) -> None:
    """Throw a draft away. Only a draft, and the audit line survives it.

    A draft holds no number and made no commitment, so there is nothing to
    account for afterwards -- which is exactly why anything past draft is
    cancelled instead.
    """
    document = get_document(document_id)
    if document.state not in EDITABLE_STATES:
        raise DocumentNotEditableError(
            f"document {document.id} is {document.state} and is not deleted; it is "
            f"cancelled, with a reason"
        )
    record(
        action="documents.draft_deleted",
        entity_type="document",
        entity_id=document.id,
        company_id=document.company_id,
        old_value={
            "document_type": document.document_type,
            "document_date": document.document_date.isoformat(),
        },
    )
    document.delete()


def _assert_complete(document: Document, spec: DocumentTypeSpec) -> None:
    if spec.requires_partner and document.partner_id is None:
        raise PartnerRequiredError(
            f"a {document.document_type} names a counterparty; validating without "
            f"one produces a document nobody can be shown to have received"
        )
    if spec.carries_lines and spec.requires_lines and not document.lines.exists():
        raise NoLinesError(f"a {document.document_type} with no positions has no content")


def _resolve_rate(currency: str, own_currency: str, supplied: Decimal | None) -> Decimal:
    if currency == own_currency:
        if supplied is not None and supplied != Decimal(1):
            raise CurrencyMismatchError(
                f"an amount already in {own_currency} converts at exactly 1, not {supplied}"
            )
        return Decimal(1)
    if supplied is None:
        raise ExchangeRateRequiredError(
            f"a document in {currency} needs an exchange rate. None is looked up "
            f"here: art. 97 alin. (6) names a date that is neither the document's "
            f"nor the posting's, and which date that is remains open (ADR-039)."
        )
    if not isinstance(supplied, Decimal):
        raise TypeError("exchange_rate must be Decimal, never float")
    if supplied <= 0:
        raise CurrencyMismatchError("a zero or negative rate erases or inverts the amount")
    return supplied
