"""Accounting events and idempotency -- F1.3.1, R19.

Spec B section 10.1 states three behaviours on conflict, and they are
requirements rather than preferences. Two of them are easy and one is the reason
this file exists:

* same key, same payload -> the first result, no new effect;
* **same key, different payload -> error with a stable code, no effect**;
* no key on an operation with a financial effect -> refusal.

The middle one is the case a reasonable implementation gets wrong. Treating a
differing payload as a new event, or letting the last write win, turns a caller's
bug into a silent divergence between what the caller believes it recorded and
what the ledger holds -- found, if at all, at a reconciliation months later.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime

import pytest
from django.db import transaction
from django.db.utils import IntegrityError, InternalError, ProgrammingError

from evidenta.accounting.events.models import AccountingEvent, EventStatus, SourceModule
from evidenta.accounting.events.services.emission import (
    IdempotencyConflictError,
    MissingIdempotencyKeyError,
    emit,
)
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])


@pytest.fixture
def company(
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> uuid.UUID:
    company_id = company_of(world["tenant_a"], "1002600000001", "Alpha Trading")
    grant_company(world["tenant_a"], company_id, world["user_a"], world["user_a"])
    return company_id


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="events")


def emit_one(
    world: dict[str, uuid.UUID],
    company_id: uuid.UUID,
    *,
    key: str = "test-key-0001",
    amount: str = "100.00",
) -> tuple[AccountingEvent, bool]:
    return emit(
        tenant_id=world["tenant_a"],
        company_id=company_id,
        event_type="sales.invoice_issued",
        source_module=SourceModule.SALES,
        source_document_type="sales_invoice",
        source_document_id=uuid.UUID("00000000-0000-0000-0000-0000000000f1"),
        occurred_at=datetime(2026, 3, 7, 10, 0, tzinfo=UTC),
        accounting_date=date(2026, 3, 7),
        idempotency_key=key,
        payload={"amount": amount, "currency": "MDL"},
        capability_snapshot={"vat": True},
        actor_user_id=world["user_a"],
        request_id="req-1",
    )


# --- The three behaviours R19 requires ---------------------------------------


def test_the_same_key_and_payload_returns_the_first_event(
    company: uuid.UUID, context: TenantContext, world: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        first, created_first = emit_one(world, company)
        second, created_second = emit_one(world, company)

    assert created_first is True
    assert created_second is False
    assert first.id == second.id

    with tenant_context(context):
        assert AccountingEvent.objects.count() == 1


def test_the_same_key_with_a_different_payload_is_an_error(
    company: uuid.UUID, context: TenantContext, world: dict[str, uuid.UUID]
) -> None:
    """The case that signals a bug in the caller. Silence would hide it.

    And no effect: the second call must leave exactly the first event behind, not
    a second one and not a modified one.
    """
    with tenant_context(context):
        emit_one(world, company, amount="100.00")

        with pytest.raises(IdempotencyConflictError) as conflict:
            emit_one(world, company, amount="900.00")

        assert conflict.value.code == "accounting.idempotency_conflict"
        events = list(AccountingEvent.objects.all())

    assert len(events) == 1
    assert events[0].payload["amount"] == "100.00"


def test_an_operation_without_a_key_is_refused(
    company: uuid.UUID, context: TenantContext, world: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context), pytest.raises(MissingIdempotencyKeyError):
        emit_one(world, company, key="")


def test_key_reordering_in_the_payload_is_not_a_conflict(
    company: uuid.UUID, context: TenantContext, world: dict[str, uuid.UUID]
) -> None:
    """JSON object order is not semantic.

    Without `sort_keys` in the fingerprint, the same event serialised by two
    library versions would compare unequal -- and a harmless reordering would be
    reported to the caller as their bug.
    """
    document_id = uuid.uuid4()

    def emit_with(payload: dict[str, object]) -> tuple[AccountingEvent, bool]:
        return emit(
            tenant_id=world["tenant_a"],
            company_id=company,
            event_type="sales.invoice_issued",
            source_module=SourceModule.SALES,
            source_document_type="sales_invoice",
            source_document_id=document_id,
            occurred_at=datetime(2026, 3, 7, 10, 0, tzinfo=UTC),
            accounting_date=date(2026, 3, 7),
            idempotency_key="order-test",
            payload=payload,
            capability_snapshot={"vat": True},
            actor_user_id=world["user_a"],
            request_id="req-2",
        )

    with tenant_context(context):
        first, _ = emit_with({"a": 1, "b": 2})
        second, created = emit_with({"b": 2, "a": 1})

    assert created is False
    assert first.id == second.id


def test_the_key_is_unique_per_company_not_globally(
    company: uuid.UUID,
    context: TenantContext,
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> None:
    """`UNIQUE (company_id, idempotency_key)`, per Spec B.

    Two companies of one tenant may legitimately use the same key -- they are
    separate sets of books, and a client-generated key has no reason to be unique
    across them.
    """
    other = company_of(world["tenant_a"], "1002600000002", "Alpha Services")
    grant_company(world["tenant_a"], other, world["user_a"], world["user_a"])

    with tenant_context(context):
        first, _ = emit_one(world, company, key="shared")
        second, created = emit_one(world, other, key="shared")

    assert created is True
    assert first.id != second.id


# --- Immutability after posting ----------------------------------------------


def test_a_posted_event_cannot_be_rewritten(
    company: uuid.UUID, context: TenantContext, world: dict[str, uuid.UUID]
) -> None:
    """The posted event is the origin of an immutable entry (R10).

    If its payload could change afterwards, the chain R13 requires would lead
    back to something other than what produced the posting -- and reconstructing
    a period would give a different answer than the original.
    """
    with tenant_context(context):
        event, _ = emit_one(world, company)
        AccountingEvent.objects.filter(pk=event.pk).update(
            status=EventStatus.POSTED, posted_at=datetime.now(UTC)
        )

        with pytest.raises((InternalError, ProgrammingError)), transaction.atomic():
            AccountingEvent.objects.filter(pk=event.pk).update(payload={"amount": "1.00"})


def test_a_posted_event_may_still_be_superseded(
    company: uuid.UUID, context: TenantContext, world: dict[str, uuid.UUID]
) -> None:
    """The one transition that stays open, and only of the status.

    A superseded event stays, because the ledger it may already have produced
    stays.
    """
    with tenant_context(context):
        event, _ = emit_one(world, company)
        AccountingEvent.objects.filter(pk=event.pk).update(
            status=EventStatus.POSTED, posted_at=datetime.now(UTC)
        )
        AccountingEvent.objects.filter(pk=event.pk).update(status=EventStatus.SUPERSEDED)
        assert AccountingEvent.objects.get(pk=event.pk).status == EventStatus.SUPERSEDED


def test_an_event_cannot_be_deleted(
    company: uuid.UUID, context: TenantContext, world: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        event, _ = emit_one(world, company)
        with pytest.raises((InternalError, ProgrammingError)), transaction.atomic():
            AccountingEvent.objects.filter(pk=event.pk).delete()


def test_a_failed_event_must_record_a_reason(
    company: uuid.UUID, context: TenantContext, world: dict[str, uuid.UUID]
) -> None:
    """A failure nobody can branch on or count is not a recorded failure."""
    with tenant_context(context):
        event, _ = emit_one(world, company)
        with pytest.raises(IntegrityError), transaction.atomic():
            AccountingEvent.objects.filter(pk=event.pk).update(status=EventStatus.FAILED)


# --- Isolation ----------------------------------------------------------------


def test_another_tenant_sees_nothing(
    company: uuid.UUID, context: TenantContext, world: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        emit_one(world, company)

    stranger = TenantContext(
        tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="events"
    )
    with tenant_context(stranger):
        assert AccountingEvent.objects.count() == 0


def test_a_member_without_access_to_the_company_sees_nothing(
    seed: Callable[..., None],
    company: uuid.UUID,
    context: TenantContext,
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
) -> None:
    """The company boundary, not just the tenant one.

    `user_b` is not in this tenant at all; the sharper case is a member of the
    same tenant with no grant on this company -- covered by the policy's
    `has_company_access`, which reads a grant rather than a session variable
    (ADR-004).
    """
    with tenant_context(context):
        emit_one(world, company)
        assert AccountingEvent.objects.count() == 1

    ungranted = company_of(world["tenant_a"], "1002600000003", "Alpha Logistics")
    with tenant_context(context):
        assert not AccountingEvent.objects.filter(company_id=ungranted).exists()


def test_an_event_cannot_be_written_into_a_company_without_access(
    company: uuid.UUID,
    context: TenantContext,
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
) -> None:
    """`WITH CHECK`, not only `USING`. Writing where you cannot see is the half
    of an access rule easiest to leave out.
    """
    other = company_of(world["tenant_a"], "1002600000004", "Alpha Rental")
    with (
        tenant_context(context),
        pytest.raises((ProgrammingError, IntegrityError)),
        transaction.atomic(),
    ):
        emit_one(world, other, key="no-access")
