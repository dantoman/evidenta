"""The fiscal status the event stood on -- ADR-088.

Three assertions, and the middle one is the reason the stamp exists at all: a
status corrected after the fact must not reach backwards into reports already
issued. Without the stamp it would, silently, because the engine would resolve
the status again at read time and get today's answer for January's entry.

The stamp is written by `emit` rather than by its callers, so these tests reach
for `emit` directly: what is under test is that no caller *can* forget it.

Under the application role (`T1`).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

import pytest

from evidenta.accounting.events.models import AccountingEvent
from evidenta.accounting.events.services.emission import emit
from evidenta.platform.rls.context import TenantContext, tenant_context
from evidenta.platform.tenancy.models import CompanyVatRegistration
from evidenta.platform.tenancy.services.tax_status import SNAPSHOT_VERSION, tax_status_at

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

IN_JANUARY = date(2026, 1, 20)
SNAPSHOT: dict[str, Any] = {"version": 1, "on": "2026-01-01", "activated": [], "usable": []}


@pytest.fixture
def stamped(
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> dict[str, Any]:
    tenant = world["tenant_a"]
    company = company_of(tenant, "1002600000918", "Alpha Statut")
    grant_company(tenant, company, world["user_a"], world["user_a"])
    return {
        "tenant": tenant,
        "company": company,
        "user": world["user_a"],
        "context": TenantContext(
            tenant_id=tenant, user_id=world["user_a"], request_id="tax-status"
        ),
    }


def _emit(world: dict[str, Any], *, on: date, key: str) -> AccountingEvent:
    document_id = uuid.uuid4()
    event, _ = emit(
        tenant_id=world["tenant"],
        company_id=world["company"],
        event_type="sales.invoice_issued",
        source_module="sales",
        source_document_type="sales.document",
        source_document_id=document_id,
        occurred_at=datetime.now(UTC),
        accounting_date=on,
        idempotency_key=key,
        payload={
            "document_id": str(document_id),
            "partner_id": str(uuid.uuid4()),
            "total": "100.00",
            "net": "100.00",
            "vat": "0",
            "vat_by_rate": [],
            "currency": "MDL",
            "revenue_kind": "services",
            "partner_resident": True,
            "document_date": str(on),
        },
        capability_snapshot=SNAPSHOT,
        actor_user_id=world["user"],
        request_id="tax-status",
    )
    return event


def _register_vat(world: dict[str, Any], *, valid_from: date) -> None:
    CompanyVatRegistration.objects.create(
        tenant_id=world["tenant"],
        company_id=world["company"],
        vat_code="0301234",
        valid_from=valid_from,
    )


def test_the_stamp_is_the_status_at_the_accounting_date_not_at_write_time(
    stamped: dict[str, Any],
) -> None:
    """The registration exists **now**; the entry is dated before it began.

    This is the case a resolution at read time gets wrong every time, and it is
    ordinary: an invoice from January entered in March, for a company that
    registered in February.
    """
    with tenant_context(stamped["context"]):
        _register_vat(stamped, valid_from=date(2026, 2, 1))
        event = _emit(stamped, on=IN_JANUARY, key="before-registration")

    assert event.tax_status_snapshot is not None
    assert event.tax_status_snapshot["vat"] == {"registered": False}
    assert event.tax_status_snapshot["on"] == "2026-01-20"


def test_a_registration_added_afterwards_does_not_reach_backwards(
    stamped: dict[str, Any],
) -> None:
    """The whole reason for the stamp -- ADR-088 §2.

    Same company, same date, and the status is corrected after the event was
    written. The entry keeps what was true when it was posted; the correction is
    visible as a difference rather than propagating in silence.
    """
    with tenant_context(stamped["context"]):
        event = _emit(stamped, on=IN_JANUARY, key="posted-first")
        stamped_before = event.tax_status_snapshot

        _register_vat(stamped, valid_from=date(2026, 1, 1))

        reread = AccountingEvent.objects.get(id=event.id)
        # What the same question answers *now*, which is the other answer.
        answered_now = tax_status_at(stamped["company"], IN_JANUARY)

    assert stamped_before is not None
    assert stamped_before["vat"]["registered"] is False
    assert reread.tax_status_snapshot == stamped_before
    assert answered_now["vat"]["registered"] is True


def test_no_registration_is_recorded_as_measured_not_as_absent(
    stamped: dict[str, Any],
) -> None:
    """An empty stamp and "not registered" are different facts.

    The first says nobody looked, and a reader six months later cannot tell which
    it was -- so the service answers the second, explicitly, and versions it.
    """
    with tenant_context(stamped["context"]):
        event = _emit(stamped, on=IN_JANUARY, key="never-registered")

    snapshot = event.tax_status_snapshot
    assert snapshot is not None
    assert snapshot["version"] == SNAPSHOT_VERSION
    assert snapshot["vat"] == {"registered": False}


def test_the_stamp_carries_the_registration_that_covers_the_date(
    stamped: dict[str, Any],
) -> None:
    """And it carries the code, because a stamp that said only `true` would send
    the reader back to a table whose rows may have moved since."""
    with tenant_context(stamped["context"]):
        _register_vat(stamped, valid_from=date(2026, 1, 1))
        event = _emit(stamped, on=IN_JANUARY, key="registered")

    snapshot = event.tax_status_snapshot
    assert snapshot is not None
    assert snapshot["vat"]["registered"] is True
    assert snapshot["vat"]["code"] == "0301234"
    assert snapshot["vat"]["valid_from"] == "2026-01-01"
    assert snapshot["vat"]["valid_to"] is None
