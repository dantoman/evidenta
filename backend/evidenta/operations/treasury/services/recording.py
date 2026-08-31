"""Recording a movement: validate it, then post it -- ADR-073 §5.

The same two steps as the two invoice families, and the same reason: validation
freezes the document and allocates its number, posting is the accounting effect
and goes through the engine (`R9`).

**The amount comes from this table, not from `totals_of`.** These documents carry
no lines, so the document core has nothing to sum -- which is why the column
exists and why reading it here is not a shortcut past the line layer.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.db import transaction

from evidenta.accounting.posting.services.commercial import (
    TreasuryFact,
    TreasuryPostingResult,
    post_treasury_movement,
)
from evidenta.operations.treasury.models import Direction, TreasuryDocument
from evidenta.platform.api.errors import ApiError
from evidenta.platform.documents.services.lifecycle import (
    get_document,
    mark_posted,
    validate,
)
from evidenta.platform.tenancy.services.companies import functional_currency


class MovementNotRecordableError(ApiError):
    code = "treasury.not_recordable"
    status = 409


def record_and_post(
    *,
    document_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    request_id: str,
    capability_snapshot: dict[str, Any],
) -> TreasuryPostingResult:
    """Validate the movement if it is still a draft, then post it."""
    document = get_document(document_id)
    movement = TreasuryDocument.objects.filter(document_id=document_id).first()
    if movement is None:
        raise MovementNotRecordableError(f"document {document_id} is not a treasury movement")

    if document.state == "draft":
        with transaction.atomic():
            document = validate(document_id)

    if document.state not in ("confirmed", "posted"):
        raise MovementNotRecordableError(
            f"a movement is posted from `confirmed`; this one is {document.state!r}"
        )

    if document.partner_id is None:
        raise MovementNotRecordableError(
            "a movement has a counterparty; the receivable it reduces belongs to somebody"
        )

    inbound = movement.direction == Direction.RECEIPT
    result = post_treasury_movement(
        tenant_id=document.tenant_id,
        company_id=document.company_id,
        functional_currency=functional_currency(document.company_id),
        direction=str(movement.direction),
        fact=TreasuryFact(
            document_id=document_id,
            partner_id=document.partner_id,
            accounting_date=document.accounting_date,
            document_date=document.document_date,
            amount=movement.amount,
            currency=document.currency,
            treasury_account=str(movement.treasury_account),
            partner_resident=movement.partner_resident,
            # Romanian, and in the register (`C33`).
            description=(
                f"{'Încasare' if inbound else 'Plată'} {document.formatted_number or ''}".strip()
            ),
        ),
        actor_user_id=actor_user_id,
        request_id=request_id,
        capability_snapshot=capability_snapshot,
    )

    mark_posted(document_id)
    return result
