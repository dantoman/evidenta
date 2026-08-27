"""Storno through the engine -- `R10`, `R14`, ADR-006, ADR-038 section 7.2.

The ledger has been able to mirror a posted entry since F1.2 and nothing called
it: the correction `R10` *requires* was the one correction the product could not
make. These tests are about the route as much as the amounts -- that the type is
the original's pair rather than a name invented here, that the correction points
at both the document and the entry it cancels, and that a second storno is
refused rather than accepted twice.

**Under the application role, like every test in this suite** (`T1`).

No account code from the published chart appears: the chart's content is `OD-23`,
open, and a plausible `221` in a fixture is that content arriving sideways.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from evidenta.accounting.events.models import AccountingEvent
from evidenta.accounting.ledger.errors import AlreadyReversedError
from evidenta.accounting.ledger.models import EntryType, JournalEntry, JournalLine
from evidenta.accounting.periods.errors import PeriodNotOpenError
from evidenta.accounting.posting.services.reversal import (
    EVENT_TYPE,
    ReversalPayloadError,
    post_reversal,
)
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.isolation import test_manual_entry as note_suite
from tests.isolation.test_manual_entry import POSTING, SNAPSHOT, post

#: The world the note suite builds -- one company, three months in three states,
#: five accounts, a numbering template. Bound to the module rather than imported
#: by name: a `from ... import scene` is shadowed by every test parameter called
#: `scene`, which is a lint error in twenty-five places and a real redefinition in
#: none of them.
context = note_suite.context
scene = note_suite.scene

pytestmark = pytest.mark.django_db(databases=["default", "migration"])


def reverse(
    scene: dict[str, uuid.UUID],
    entry_id: uuid.UUID,
    *,
    on: date = POSTING,
    key: str = "storno-1",
    reason: str = "Cont gresit pe linia a doua",
) -> Any:
    return post_reversal(
        tenant_id=scene["tenant"],
        company_id=scene["company"],
        entry_id=entry_id,
        accounting_date=on,
        reason=reason,
        idempotency_key=key,
        actor_user_id=scene["user"],
        request_id="storno-test",
        capability_snapshot=dict(SNAPSHOT),
    )


# --- the mirror --------------------------------------------------------------


def test_the_reversal_swaps_the_sides_it_does_not_negate_them(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Spec B section 9.2, and the reason it matters is turnover.

    A negative line would make the month's debit turnover go *down* by the
    correction instead of up, and a trial balance would stop showing activity
    that actually happened. The constraint makes it unwriteable anyway; this says
    the engine never tries.
    """
    with tenant_context(context):
        original = post(scene)
        result = reverse(scene, original.journal_entry_id)

        source = list(
            JournalLine.objects.filter(journal_entry_id=original.journal_entry_id)
            .order_by("line_number")
            .values_list("account_id", "debit", "credit")
        )
        mirror = list(
            JournalLine.objects.filter(journal_entry_id=result.journal_entry_id)
            .order_by("line_number")
            .values_list("account_id", "debit", "credit")
        )

    assert [(a, c, d) for a, d, c in source] == mirror
    assert all(debit >= 0 and credit >= 0 for _, debit, credit in mirror)


def test_the_reversal_carries_both_links(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """`R14`. Without the second, a drill-down shows two entries with opposite
    amounts and nothing saying one cancels the other."""
    with tenant_context(context):
        original = post(scene)
        result = reverse(scene, original.journal_entry_id)

        entry = JournalEntry.objects.get(id=result.journal_entry_id)

    assert entry.entry_type == EntryType.REVERSAL
    assert entry.reverses_entry_id == original.journal_entry_id
    assert entry.accounting_event_id == result.accounting_event_id
    assert entry.accounting_event_id != original.accounting_event_id


def test_the_event_type_is_the_originals_pair(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """ADR-038 section 7.2: the pair, derived rather than named here.

    Asserted because the derivation is what makes this service work for the sales
    invoice and the payroll run without a second storno path -- and a hardcoded
    name would pass every other test in this file.
    """
    with tenant_context(context):
        original = post(scene)
        result = reverse(scene, original.journal_entry_id)

        reversal_event = AccountingEvent.objects.get(id=result.accounting_event_id)
        original_event = AccountingEvent.objects.get(id=original.accounting_event_id)

    assert reversal_event.event_type == original_event.event_type + "_reversed"
    assert reversal_event.event_type == EVENT_TYPE


def test_the_correction_points_at_the_same_document(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """A correction says something further about the document already there.

    It does not invent one, so `R13`'s chain reads the same from either entry.
    """
    with tenant_context(context):
        original = post(scene)
        result = reverse(scene, original.journal_entry_id)

        reversal_event = AccountingEvent.objects.get(id=result.accounting_event_id)
        original_event = AccountingEvent.objects.get(id=original.accounting_event_id)

    assert reversal_event.source_document_id == original_event.source_document_id
    assert reversal_event.source_document_type == original_event.source_document_type
    assert reversal_event.source_module == original_event.source_module


def test_the_reversal_takes_a_number_from_the_same_series(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """One kind of document, one register. Two series would be two things to read."""
    with tenant_context(context):
        original = post(scene)
        result = reverse(scene, original.journal_entry_id)

        numbers = list(
            JournalEntry.objects.filter(
                id__in=[original.journal_entry_id, result.journal_entry_id]
            ).values_list("entry_number", flat=True)
        )

    assert len(set(numbers)) == 2
    assert all(number.startswith("NC-") for number in numbers)


# --- refusals ----------------------------------------------------------------


def test_a_second_storno_is_refused(context: TenantContext, scene: dict[str, uuid.UUID]) -> None:
    """Its result is a ledger that cancels the entry twice, which nothing undoes."""
    with tenant_context(context):
        original = post(scene)
        reverse(scene, original.journal_entry_id)

        with pytest.raises(AlreadyReversedError) as excinfo:
            reverse(scene, original.journal_entry_id, key="storno-2")

    assert excinfo.value.code == "ledger.entry_already_reversed"


def test_a_storno_without_a_reason_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The one part of a storno a reader cannot reconstruct from the ledger."""
    with tenant_context(context):
        original = post(scene)

        with pytest.raises(ReversalPayloadError) as excinfo:
            reverse(scene, original.journal_entry_id, reason="   ")

    assert excinfo.value.code == "posting.reversal_payload_invalid"


def test_an_entry_that_is_not_visible_cannot_be_reversed(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The refusal is the engine's, with a code, before anything is emitted."""
    with tenant_context(context):
        with pytest.raises(Exception) as excinfo:
            reverse(scene, uuid.uuid4())

        assert AccountingEvent.objects.filter(event_type=EVENT_TYPE).count() == 0

    assert getattr(excinfo.value, "code", "") in {
        "posting.reversal_origin_missing",
        "ledger.entry_not_found",
    }


def test_a_storno_into_a_closed_period_is_refused_by_the_engine(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """`R12`, with a stable code rather than a trigger message.

    The database refuses it either way. What this asserts is that the caller
    learns why in a form an interface can act on.
    """
    with tenant_context(context):
        original = post(scene)

        # February is closed in the fixture; the correction is aimed at it
        # deliberately, because that is the case an accountant meets.
        with pytest.raises(PeriodNotOpenError):
            reverse(scene, original.journal_entry_id, on=date(2026, 2, 15))


# --- idempotency -------------------------------------------------------------


def test_the_same_key_twice_produces_one_reversal(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """`R19`, on the accounting event rather than on the endpoint.

    A retried storno that wrote a second one would cancel the entry twice, and
    the second cancellation is itself unreversible.
    """
    with tenant_context(context):
        original = post(scene)
        first = reverse(scene, original.journal_entry_id)
        second = reverse(scene, original.journal_entry_id)

        written = JournalEntry.objects.filter(reverses_entry_id=original.journal_entry_id).count()

    assert first.posted_now is True
    assert second.posted_now is False
    assert first.journal_entry_id == second.journal_entry_id
    assert written == 1


def test_the_reversal_leaves_the_original_untouched(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Correction is a reversal, not an erasure -- and the original still says so."""
    with tenant_context(context):
        original = post(scene)
        before = list(
            JournalLine.objects.filter(journal_entry_id=original.journal_entry_id)
            .order_by("line_number")
            .values_list("account_id", "debit", "credit")
        )
        reverse(scene, original.journal_entry_id)

        after = list(
            JournalLine.objects.filter(journal_entry_id=original.journal_entry_id)
            .order_by("line_number")
            .values_list("account_id", "debit", "credit")
        )
        entry = JournalEntry.objects.get(id=original.journal_entry_id)

    assert before == after
    assert entry.status == "posted"
    assert entry.entry_type == EntryType.STANDARD


def test_the_pair_sums_to_nothing(context: TenantContext, scene: dict[str, uuid.UUID]) -> None:
    """The point of the whole exercise, stated as arithmetic.

    Per account, the original and its reversal cancel: debit minus credit across
    both entries is zero for every account touched. A trial balance built over
    the pair shows the activity and no residue.
    """
    with tenant_context(context):
        original = post(scene)
        result = reverse(scene, original.journal_entry_id)

        rows = JournalLine.objects.filter(
            journal_entry_id__in=[original.journal_entry_id, result.journal_entry_id]
        ).values_list("account_id", "debit", "credit")

        net: dict[uuid.UUID, Decimal] = {}
        for account_id, debit, credit in rows:
            net[account_id] = net.get(account_id, Decimal(0)) + debit - credit

    assert net and all(amount == Decimal(0) for amount in net.values())
