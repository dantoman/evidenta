"""Opening a treasury document -- ADR-073 §5.

Two functions rather than one with a flag, because the two are different acts to
the person doing them: money arrived, money left. What they share -- the amount,
where it moved, whose account it clears -- is the argument list.

No conversion, no lines: a receipt has an amount, and what it settles is
settlement's business (`F2.A3`).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction

from evidenta.operations.treasury.models import Direction, TreasuryAccount, TreasuryDocument
from evidenta.operations.treasury.types import PAYMENT, RECEIPT
from evidenta.platform.api.errors import ApiError
from evidenta.platform.documents.services.lifecycle import open_draft


class TreasuryAccountInvalidError(ApiError):
    """Where the money moved is asked for, and the vocabulary is closed."""

    code = "treasury.account_invalid"
    status = 422


class TreasuryAmountInvalidError(ApiError):
    """A movement of zero or less is not a movement.

    The direction is the document's type, never the sign: a negative receipt and
    a payment would be the same row written two ways, and every report would have
    to know which convention it was reading.
    """

    code = "treasury.amount_invalid"
    status = 422


def _checked(treasury_account: str, amount: Decimal) -> tuple[str, Decimal]:
    if treasury_account not in TreasuryAccount.values:
        raise TreasuryAccountInvalidError(
            f"treasury_account is {treasury_account!r}; it selects the treasury "
            f"role, so it is chosen from {sorted(TreasuryAccount.values)}"
        )
    if amount <= 0:
        raise TreasuryAmountInvalidError(f"amount is {amount}; money moves in a positive amount")
    return treasury_account, amount


def _open(
    *,
    document_type: str,
    direction: str,
    company_id: uuid.UUID,
    partner_id: uuid.UUID,
    document_date: date,
    amount: Decimal,
    treasury_account: str,
    partner_resident: bool,
    accounting_date: date | None,
    currency: str | None,
    notes: str | None,
) -> uuid.UUID:
    where, checked = _checked(treasury_account, amount)
    document = open_draft(
        company_id=company_id,
        document_type=document_type,
        document_date=document_date,
        accounting_date=accounting_date,
        partner_id=partner_id,
        currency=currency,
        notes=notes,
    )
    TreasuryDocument.objects.create(
        document=document,
        tenant_id=document.tenant_id,
        company_id=document.company_id,
        direction=direction,
        treasury_account=where,
        amount=checked,
        partner_resident=partner_resident,
    )
    return document.id


@transaction.atomic
def open_receipt(
    *,
    company_id: uuid.UUID,
    partner_id: uuid.UUID,
    document_date: date,
    amount: Decimal,
    treasury_account: str,
    partner_resident: bool,
    accounting_date: date | None = None,
    currency: str | None = None,
    notes: str | None = None,
) -> uuid.UUID:
    """Money in."""
    return _open(
        document_type=RECEIPT,
        direction=Direction.RECEIPT,
        company_id=company_id,
        partner_id=partner_id,
        document_date=document_date,
        amount=amount,
        treasury_account=treasury_account,
        partner_resident=partner_resident,
        accounting_date=accounting_date,
        currency=currency,
        notes=notes,
    )


@transaction.atomic
def open_payment(
    *,
    company_id: uuid.UUID,
    partner_id: uuid.UUID,
    document_date: date,
    amount: Decimal,
    treasury_account: str,
    partner_resident: bool,
    accounting_date: date | None = None,
    currency: str | None = None,
    notes: str | None = None,
) -> uuid.UUID:
    """Money out."""
    return _open(
        document_type=PAYMENT,
        direction=Direction.PAYMENT,
        company_id=company_id,
        partner_id=partner_id,
        document_date=document_date,
        amount=amount,
        treasury_account=treasury_account,
        partner_resident=partner_resident,
        accounting_date=accounting_date,
        currency=currency,
        notes=notes,
    )


@dataclass(frozen=True, slots=True)
class MovementView:
    """What another module may know about a movement without reading its table."""

    amount: Decimal
    direction: str
    partner_resident: bool


class MovementNotFoundError(ApiError):
    code = "treasury.movement_not_found"
    status = 404


def movement_of(document_id: uuid.UUID) -> MovementView:
    """The three facts settlement needs: how much moved, which way, whose account."""
    row = (
        TreasuryDocument.objects.filter(document_id=document_id)
        .values("amount", "direction", "partner_resident")
        .first()
    )
    if row is None:
        raise MovementNotFoundError(f"document {document_id} is not a treasury movement")
    return MovementView(
        amount=row["amount"],
        direction=str(row["direction"]),
        partner_resident=bool(row["partner_resident"]),
    )
