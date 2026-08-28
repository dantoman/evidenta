"""Storno: the document that undoes another one.

A type of its own, with a mandatory link to the original and positions copied
with the sign inverted. The link is mandatory in the schema -- `reversal_document`
exists precisely so it can be `NOT NULL` -- rather than in this function, because
a storno with nothing to point at is not a storno and a service is not where that
is kept true.

**No accounting effect.** Nothing here posts, produces a journal entry or names an
account. `R14` asks a reversing *entry* for two links, and this builds the
documentary half of that shape so the accounting half can be added later without
moving anything.

**The date has no default, on purpose.** Which period a correction belongs in is
[ADR-007](../../../../../docs/decisions/007-reversal-period.md), open. A default
chosen here -- today, or the original's own date -- would close that decision from
the layer least entitled to close it, and it would do so invisibly. The caller
says which date, or there is no storno.
"""

from __future__ import annotations

import uuid
from datetime import date

from django.db import transaction

from evidenta.platform.documents.errors import (
    AlreadyReversedError,
    ReversalReasonRequiredError,
    SourceNotValidatedError,
)
from evidenta.platform.documents.models import (
    Document,
    DocumentState,
    ReversalDocument,
)
from evidenta.platform.documents.registry import DocumentTypeSpec, register
from evidenta.platform.documents.services.history import record_event
from evidenta.platform.documents.services.lifecycle import get_document, open_draft
from evidenta.platform.documents.services.lines import copy_lines
from evidenta.platform.tenancy.services.companies import functional_currency

#: Registered by the core rather than by a business module: a storno of a sale
#: and a storno of a purchase are the same document with the same rules, and two
#: types would be two places to keep that true.
REVERSAL_TYPE = "documents.reversal"

#: The states a document has to be in before anything can undo it. A draft is
#: deleted, not reversed -- there is nothing to undo.
REVERSIBLE_STATES = frozenset(
    {DocumentState.CONFIRMED, DocumentState.POSTED, DocumentState.COMPLETED}
)


def register_reversal_type() -> DocumentTypeSpec:
    """Put the storno in the vocabulary. Called from the app's `ready()`."""
    return register(
        DocumentTypeSpec(
            code=REVERSAL_TYPE,
            owner="documents",
            # It takes the counterparty of the document it undoes, whatever that
            # was -- including none, for a document that had none.
            requires_partner=False,
            carries_lines=True,
            requires_lines=True,
        )
    )


@transaction.atomic
def create_reversal(
    original_id: uuid.UUID,
    *,
    reason: str,
    document_date: date,
    accounting_date: date | None = None,
) -> Document:
    """Build the storno of ``original`` as a draft, and return it.

    A draft, not a validated document: the number is allocated at validation like
    every other document's, so a storno that is started and abandoned burns
    nothing. That is the same rule the original followed, and having one rule is
    the point.

    The exchange rate **is** carried over, unlike in a conversion: a storno has
    to reverse the exact amounts the original carried, and a different rate would
    leave a residue in the functional currency that nothing accounts for.

    The positions are copied with quantity and the four monetary amounts negated.
    The unit price, the rate and the discount percentage are **not** negated:
    they describe how the position was priced, and a storno undoes the amount,
    not the price list.
    """
    original = get_document(original_id)
    if original.state not in REVERSIBLE_STATES:
        raise SourceNotValidatedError(
            f"document {original.id} is {original.state}; a draft is deleted, not "
            f"reversed, and a cancelled document has already been undone"
        )
    if not reason.strip():
        raise ReversalReasonRequiredError(
            "a storno needs a reason: a correction nobody can explain is a "
            "correction nobody can defend"
        )
    if ReversalDocument.objects.filter(reversed_document=original).exists():
        raise AlreadyReversedError(
            f"document {original.id} has already been reversed; a second storno would undo it twice"
        )

    storno = open_draft(
        company_id=original.company_id,
        document_type=REVERSAL_TYPE,
        document_date=document_date,
        accounting_date=accounting_date,
        partner_id=original.partner_id,
        currency=original.currency,
        exchange_rate=(
            original.exchange_rate
            if original.currency != functional_currency(original.company_id)
            else None
        ),
        notes=reason.strip(),
    )
    copy_lines(original, storno, invert_signs=True)

    ReversalDocument.objects.create(
        document=storno,
        tenant_id=storno.tenant_id,
        company_id=storno.company_id,
        reversed_document=original,
        reason=reason.strip(),
    )

    record_event(
        storno,
        event_type="document.reverses",
        detail={
            "reverses_document_id": str(original.id),
            "reverses_number": original.formatted_number or original.external_number,
            "reason": reason.strip(),
        },
    )
    # And the other direction, on the original: "what happened to this document"
    # has to include being undone, read from the document itself.
    record_event(
        original,
        event_type="document.reversed_by",
        detail={"reversed_by_document_id": str(storno.id), "reason": reason.strip()},
    )
    return storno
