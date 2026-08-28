"""Consuming from a range the tax service issued -- `art. 118²` Cod fiscal.

Every function here takes a number *out* of an allocation. None of them invents
one: that is the difference between this module and `platform.numbering`, and it
is why both exist.

**The number is taken at posting, under a lock, inside the document's own
transaction.** Never when a draft is created. A draft that reserved a number and
was then abandoned would burn a number the tax service issued, and the register
would have to explain a gap no document accounts for. The lock is on the
allocation row, so two documents posting at the same instant cannot receive the
same number -- the failure that prevents is two fiscal invoices carrying one
number, which is not something an accountant can repair afterwards.

**A number never comes back.** The cursor only advances. Whatever happens to the
document later -- a reversal, a correction -- the number it carried stays
consumed, because the correction is a document of its own.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime

from django.db import transaction
from django.db.models import F

from evidenta.platform.api.errors import ApiError
from evidenta.platform.strictforms.models import (
    FormNumberState,
    StrictFormAllocation,
    StrictFormNumber,
)

#: The states a blank can reach without a document behind it.
VOID_STATES = frozenset(
    {FormNumberState.CANCELLED, FormNumberState.DAMAGED, FormNumberState.RETURNED}
)


class AllocationMalformedError(ApiError):
    code = "strictforms.allocation_malformed"
    status = 422


class NoAllocationError(ApiError):
    """Nothing to consume from -- a refusal, not an empty result.

    A document that cannot receive a legal number must not post. Producing one
    anyway, from a counter or a sequence or anywhere else, is how a company ends
    up with invoices whose numbers the tax service never issued.
    """

    code = "strictforms.no_allocation"
    status = 409


class AllocationExhaustedError(ApiError):
    """The range ran out. A new one is ordered from the tax service, not computed."""

    code = "strictforms.allocation_exhausted"
    status = 409


@dataclass(frozen=True, slots=True)
class IssuedNumber:
    """What a document received: the series, the number, and which range it left."""

    allocation_id: uuid.UUID
    series: str
    number: int
    formatted: str


def record_allocation(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    form_type_code: str,
    series: str,
    first_number: int,
    last_number: int,
    issued_on: date,
    source_reference: str,
    responsible_user_id: uuid.UUID,
    note: str | None = None,
) -> StrictFormAllocation:
    """Record a range the tax service issued. It is not created here -- it arrived.

    ``source_reference`` is what the order or the electronic receipt says, and it
    is required: a range with no provenance cannot be told apart from one
    somebody typed.
    """
    if first_number > last_number:
        raise AllocationMalformedError(f"range {first_number}-{last_number} ends before it starts")
    if first_number <= 0:
        raise AllocationMalformedError("a form number starts at 1, not at zero or below")
    if not series.strip():
        raise AllocationMalformedError(
            "an allocation needs the series the tax service issued; the entity does "
            "not choose one (art. 118²)"
        )
    if not source_reference.strip():
        raise AllocationMalformedError(
            "an allocation needs the order or receipt it came from: a range with no "
            "provenance cannot be told from one somebody typed"
        )

    return StrictFormAllocation.objects.create(
        tenant_id=tenant_id,
        company_id=company_id,
        form_type_code=form_type_code,
        series=series.strip(),
        first_number=first_number,
        last_number=last_number,
        next_number=first_number,
        issued_on=issued_on,
        source_reference=source_reference.strip(),
        responsible_user_id=responsible_user_id,
        note=note,
    )


def consume_number(
    *,
    company_id: uuid.UUID,
    form_type_code: str,
    document_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    occurred_at: datetime | None = None,
) -> IssuedNumber:
    """Take the next number for a document being posted.

    **Call this inside the posting transaction.** The allocation stays locked for
    the rest of it, so a concurrent posting waits instead of receiving the same
    number; and if the posting fails afterwards, the consumption rolls back with
    it rather than leaving a hole.
    """
    return _take(
        company_id=company_id,
        form_type_code=form_type_code,
        state=FormNumberState.CONSUMED,
        document_id=document_id,
        actor_user_id=actor_user_id,
        occurred_at=occurred_at,
        note=None,
    )


def void_number(
    *,
    company_id: uuid.UUID,
    form_type_code: str,
    state: str,
    actor_user_id: uuid.UUID,
    note: str,
    occurred_at: datetime | None = None,
) -> IssuedNumber:
    """Take the next number *without* a document: spoiled, cancelled or returned.

    A blank that was misprinted, damaged or sent back still has to be accounted
    for. Recording it is what makes the register add up -- issued equals consumed
    plus voided plus remaining -- and that sum is what an inspection reconstructs.
    """
    if state not in VOID_STATES:
        raise AllocationMalformedError(
            f"{state!r} is not a way a blank leaves the range without a document"
        )
    if not note.strip():
        raise AllocationMalformedError(
            "voiding a form needs a reason: it is the only part of the register a "
            "reader cannot reconstruct from the numbers themselves"
        )
    return _take(
        company_id=company_id,
        form_type_code=form_type_code,
        state=state,
        document_id=None,
        actor_user_id=actor_user_id,
        occurred_at=occurred_at,
        note=note.strip(),
    )


@transaction.atomic
def _take(
    *,
    company_id: uuid.UUID,
    form_type_code: str,
    state: str,
    document_id: uuid.UUID | None,
    actor_user_id: uuid.UUID,
    occurred_at: datetime | None,
    note: str | None,
) -> IssuedNumber:
    # Oldest usable range first, deterministically: two ranges open at once is a
    # normal state after a re-order, and consuming from the newer one would leave
    # the older with a tail nobody ever uses.
    allocation = (
        StrictFormAllocation.objects.select_for_update()
        .filter(
            company_id=company_id,
            form_type_code=form_type_code,
            is_active=True,
            next_number__lte=F("last_number"),
        )
        .order_by("issued_on", "first_number")
        .first()
    )
    if allocation is None:
        if StrictFormAllocation.objects.filter(
            company_id=company_id, form_type_code=form_type_code, is_active=True
        ).exists():
            raise AllocationExhaustedError(
                f"every active range for {form_type_code} is used up; a new series is "
                f"ordered from the tax service, not generated here"
            )
        raise NoAllocationError(
            f"company {company_id} has no active range for {form_type_code}. The series "
            f"and the numbers are issued by the tax service (art. 118²); nothing here "
            f"can invent one"
        )

    number = allocation.next_number
    StrictFormNumber.objects.create(
        tenant_id=allocation.tenant_id,
        company_id=allocation.company_id,
        allocation=allocation,
        number=number,
        state=state,
        document_id=document_id,
        occurred_at=occurred_at or datetime.now(UTC),
        recorded_by_user_id=actor_user_id,
        note=note,
    )
    allocation.next_number = number + 1
    allocation.save(update_fields=["next_number", "updated_at"])

    return IssuedNumber(
        allocation_id=allocation.id,
        series=allocation.series,
        number=number,
        formatted=f"{allocation.series} {number}",
    )


def remaining(company_id: uuid.UUID, form_type_code: str) -> int:
    """How many numbers are left across every active range, together.

    No threshold here and no alert. When to warn is a product decision nobody has
    made, and a number invented in this module would quietly become the policy.
    The caller states the threshold it wants to act on.
    """
    return sum(
        max(0, allocation.last_number - allocation.next_number + 1)
        for allocation in StrictFormAllocation.objects.filter(
            company_id=company_id, form_type_code=form_type_code, is_active=True
        )
    )


def state_of(allocation_id: uuid.UUID, number: int) -> str:
    """What happened to one number, including the state that is not a row.

    ``allocated`` is derived -- in range and not yet handed out. Every other state
    was written down when the number left.
    """
    allocation = StrictFormAllocation.objects.filter(id=allocation_id).first()
    if allocation is None:
        raise NoAllocationError(f"allocation {allocation_id} is not visible in this context")
    if not (allocation.first_number <= number <= allocation.last_number):
        raise AllocationMalformedError(
            f"{number} is outside {allocation.first_number}-{allocation.last_number}"
        )
    row = StrictFormNumber.objects.filter(allocation_id=allocation_id, number=number).first()
    return "allocated" if row is None else str(row.state)
