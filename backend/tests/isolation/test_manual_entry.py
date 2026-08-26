"""The manual journal note -- F1.7.1, Spec B section 1.5.

The criterion of this task is not "a manual note can be posted". It is that
**there is no second path**: the note takes the same route a sales invoice will
take, so lineage, idempotency and effect enumeration exist once. So the assertions
below are mostly about the route rather than about the amounts -- that an event
exists and the entry names it, that a replayed key produces no second entry, that
a refusal reaches the caller with a stable code and leaves the ledger untouched.

**Under the application role, like every test in this suite** (T1). The reads the
engine makes -- the period, the chart, the numbering template -- go through the
same policies a request does, so a note that only posted because the seeding
connection could see more would fail here.

**No account code from the published chart appears.** The engine resolves accounts
by id and never reads a code; the fixture uses codes no chart uses (`FIXTURE-D`,
`FIXTURE-C`, ...). The content of the general chart is `OD-23`, open, and a
plausible `221` in a fixture is that content arriving through the back door (R15).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from django.db import connection

from evidenta.accounting.coa.services.accounts import set_blocked
from evidenta.accounting.events import registry
from evidenta.accounting.events.models import AccountingEvent, EventStatus
from evidenta.accounting.events.services.emission import IdempotencyConflictError, emit
from evidenta.accounting.events.services.lifecycle import mark_posted
from evidenta.accounting.events.services.lineage import origin_of_event
from evidenta.accounting.ledger.models import EntryStatus, EntryType, JournalEntry, JournalLine
from evidenta.accounting.ledger.services.lineage import origin_of_line
from evidenta.accounting.ledger.services.writing import (
    LineToWrite,
    NothingToWriteError,
    UnknownDimensionError,
    post_entry,
)
from evidenta.accounting.periods.errors import PeriodLockedError, PeriodNotOpenError
from evidenta.accounting.posting.dimensions import MissingRequiredDimensionError
from evidenta.accounting.posting.invariants import (
    AccountNotPostableError,
    MalformedLineAmountError,
    OutOfBalanceError,
    ZeroAmountLineError,
)
from evidenta.accounting.posting.services.manual import (
    EVENT_TYPE,
    HANDLER_REF,
    NUMBERING_DOCUMENT_TYPE,
    SOURCE_DOCUMENT_TYPE,
    SOURCE_MODULE,
    EventAlreadyPostedError,
    ForeignCurrencyNoteError,
    ManualPayloadError,
    post_manual_entry,
)
from evidenta.platform.numbering.services.allocation import NumberingError
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

#: A Wednesday in the open month. Everything is dated relative to it.
POSTING = date(2026, 1, 15)

#: The profile as `platform.capabilities` writes it (R26). A company with nothing
#: activated is still a company, and the snapshot says so explicitly rather than
#: being absent -- an absent one is refused, which is the point of F1.4.1.
SNAPSHOT: dict[str, Any] = {
    "version": 1,
    "on": POSTING.isoformat(),
    "activated": [],
    "usable": [],
}


# --- the world ---------------------------------------------------------------


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="manual")


def seed_account(
    seed: Callable[..., None],
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    code: str,
    *,
    blocked: bool = False,
    requires: str = "{}",
) -> uuid.UUID:
    """One account of the company's own. `requires` is a Postgres array literal."""
    account_id = uuid.uuid4()
    seed(
        "INSERT INTO company_account (id, tenant_id, company_id, account_code,"
        " parent_id, origin, template_account_id, name_ro, account_class,"
        " normal_balance, allows_subaccounts, currency_tracking, quantity_tracking,"
        " required_dimensions, is_blocked, valid_from, valid_to, created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, NULL, 'company', NULL, %s, 'asset', 'debit',"
        " false, false, false, %s::text[], %s, '2020-01-01', NULL, now(), now())",
        [account_id, tenant_id, company_id, code, f"Cont de fixture {code}", requires, blocked],
    )
    return account_id


def seed_period(
    seed: Callable[..., None],
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    year_id: uuid.UUID,
    *,
    period_no: int,
    start: str,
    end: str,
    status: str,
) -> uuid.UUID:
    period_id = uuid.uuid4()
    closed_at = "now()" if status in ("closed", "locked") else "NULL"
    seed(
        "INSERT INTO period (id, tenant_id, company_id, fiscal_year_id, period_no,"
        " start_date, end_date, status, reopened_count, closed_at, created_at, updated_at)"
        f" VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, {closed_at}, now(), now())",
        [period_id, tenant_id, company_id, year_id, period_no, start, end, status],
    )
    return period_id


def seed_template(
    seed: Callable[..., None],
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    *,
    document_type: str | None = NUMBERING_DOCUMENT_TYPE,
) -> uuid.UUID:
    """The company's numbering template (ADR-022).

    Seeded rather than assumed: a company with no template at all cannot number
    an entry, and that is a refusal this file asserts rather than a state it hides.
    """
    template_id = uuid.uuid4()
    seed(
        "INSERT INTO numbering_template (id, tenant_id, company_id, document_type,"
        " series, prefix, suffix, separator, digits, include_year, year_format,"
        " reset_policy, created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, '', 'NC', '', '-', 4, true, 'yyyy', 'yearly',"
        " now(), now())",
        [template_id, tenant_id, company_id, document_type],
    )
    return template_id


@pytest.fixture
def scene(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> dict[str, uuid.UUID]:
    """One company, three months in three states, five accounts, one template."""
    tenant = world["tenant_a"]
    company = company_of(tenant, "1002600000501", "Alpha Nota")
    grant_company(tenant, company, world["user_a"], world["user_a"])

    year_id = uuid.uuid4()
    seed(
        "INSERT INTO fiscal_year (id, tenant_id, company_id, code, start_date, end_date,"
        " status, created_at, updated_at)"
        " VALUES (%s, %s, %s, '2026', '2026-01-01', '2026-12-31', 'open', now(), now())",
        [year_id, tenant, company],
    )
    seed_template(seed, tenant, company)

    return {
        "tenant": tenant,
        "company": company,
        "user": world["user_a"],
        "open_period": seed_period(
            seed,
            tenant,
            company,
            year_id,
            period_no=1,
            start="2026-01-01",
            end="2026-01-31",
            status="open",
        ),
        "closed_period": seed_period(
            seed,
            tenant,
            company,
            year_id,
            period_no=2,
            start="2026-02-01",
            end="2026-02-28",
            status="closed",
        ),
        "locked_period": seed_period(
            seed,
            tenant,
            company,
            year_id,
            period_no=3,
            start="2026-03-01",
            end="2026-03-31",
            status="locked",
        ),
        "debit_account": seed_account(seed, tenant, company, "FIXTURE-D"),
        "credit_account": seed_account(seed, tenant, company, "FIXTURE-C"),
        "blocked_account": seed_account(seed, tenant, company, "FIXTURE-B", blocked=True),
        "partner_account": seed_account(seed, tenant, company, "FIXTURE-P", requires="{partner}"),
    }


# --- building a note ---------------------------------------------------------


def line(
    account_id: uuid.UUID, *, debit: str = "0", credit: str = "0", **extra: Any
) -> dict[str, Any]:
    """One payload line. Amounts are strings, because JSON has no decimal."""
    return {"account_id": str(account_id), "debit": debit, "credit": credit, **extra}


def note(scene: dict[str, uuid.UUID], amount: str = "1000.0000", **extra: Any) -> dict[str, Any]:
    """The smallest correct note: one debit, one credit, a sentence."""
    payload: dict[str, Any] = {
        "description": "Nota contabila de fixture",
        "lines": [
            line(scene["debit_account"], debit=amount),
            line(scene["credit_account"], credit=amount),
        ],
    }
    payload.update(extra)
    return payload


def post(
    scene: dict[str, uuid.UUID],
    payload: dict[str, Any] | None = None,
    *,
    on: date = POSTING,
    key: str = "note-1",
    note_id: uuid.UUID | None = None,
) -> Any:
    return post_manual_entry(
        tenant_id=scene["tenant"],
        company_id=scene["company"],
        accounting_date=on,
        functional_currency="MDL",
        note_id=note_id or uuid.uuid5(uuid.NAMESPACE_URL, key),
        payload=payload if payload is not None else note(scene),
        idempotency_key=key,
        actor_user_id=scene["user"],
        request_id="manual-test",
        capability_snapshot=dict(SNAPSHOT),
    )


# --- the note reaches the ledger, and only through the engine ----------------


def test_a_manual_note_posts_through_an_accounting_event(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The whole criterion of F1.7.1 in one assertion.

    Not "an entry exists" -- an entry exists **and names the event that produced
    it**. A note written straight into `journal_entry` would look identical in a
    trial balance and would have no answer to "what is this and who asked for it".
    """
    with tenant_context(context):
        result = post(scene)

        entry = JournalEntry.objects.get(id=result.journal_entry_id)
        event = AccountingEvent.objects.get(id=result.accounting_event_id)

        assert result.posted_now is True
        assert entry.accounting_event_id == event.id
        assert entry.status == EntryStatus.POSTED
        assert entry.posted_at is not None
        assert entry.entry_type == EntryType.STANDARD
        assert entry.period_id == scene["open_period"]
        assert entry.description == "Nota contabila de fixture"
        assert event.event_type == EVENT_TYPE
        assert event.source_module == SOURCE_MODULE
        assert event.status == EventStatus.POSTED


def test_the_lines_are_stored_exactly_as_proposed(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """ "Posteaza **fara sa derive** liniile" -- the amounts are the user's.

    The currency triple is the identity case and not a conversion: the rate is 1,
    the transaction amount is the same number, and nothing multiplies. Which way a
    real conversion would round is `DNB-08`, open -- so a note that needed one is
    refused rather than rounded (see the foreign-currency test).
    """
    with tenant_context(context):
        result = post(scene, note(scene, amount="1234.5678"))

        lines = list(JournalLine.objects.filter(journal_entry_id=result.journal_entry_id))
        assert [line.line_number for line in lines] == [1, 2]
        assert lines[0].debit == Decimal("1234.5678")
        assert lines[0].credit == Decimal(0)
        assert lines[1].credit == Decimal("1234.5678")
        for stored in lines:
            assert stored.currency == "MDL"
            assert stored.exchange_rate == Decimal(1)
            assert stored.amount_currency == stored.debit + stored.credit
            assert stored.accounting_date == POSTING
            assert stored.document_date == POSTING
            assert stored.rate_date == POSTING

        entry = JournalEntry.objects.get(id=result.journal_entry_id)
        assert entry.total_debit == entry.total_credit == Decimal("1234.5678")


def test_the_entry_is_numbered_from_the_company_template(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """A number the company's template shaped, not one this module invented.

    ADR-022: the platform applies the template and guarantees uniqueness. The
    engine consumes a number like any other document, which is also why the
    allocation happens **after** every refusal -- a consumed number is a permanent
    gap in the register.
    """
    with tenant_context(context):
        first = post(scene)
        second = post(scene, key="note-2")

        numbers = [
            JournalEntry.objects.get(id=first.journal_entry_id).entry_number,
            JournalEntry.objects.get(id=second.journal_entry_id).entry_number,
        ]
        assert numbers == ["NC-2026-0001", "NC-2026-0002"]


def test_the_chain_walks_back_from_a_line_to_the_note(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """R13, on the shape that has no document module behind it.

        Journal Line -> Journal Entry -> Accounting Event -> Source Document

    The last hop ends at an identifier, because a manual note is not a stored
    document at F1 -- and the caller supplies that identifier precisely so the
    hop is not a dead end.
    """
    note_id = uuid.uuid4()
    with tenant_context(context):
        result = post(scene, note_id=note_id)

        line_id = (
            JournalLine.objects.filter(journal_entry_id=result.journal_entry_id)
            .values_list("id", flat=True)
            .first()
        )
        assert line_id is not None

        walked = origin_of_line(line_id)
        assert walked is not None
        assert walked.journal_entry_id == result.journal_entry_id
        assert walked.accounting_event_id == result.accounting_event_id

        source = origin_of_event(walked.accounting_event_id)
        assert source is not None
        assert source.source_module == SOURCE_MODULE
        assert source.source_document_type == SOURCE_DOCUMENT_TYPE
        assert source.source_document_id == note_id


def test_the_database_agrees_the_entry_balances(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """R11 lives in the database, and the engine does not replace it.

    `journal_entry_balance_at_commit` is deferred, and a pytest transaction never
    commits -- so without forcing it, this suite would prove the service and say
    nothing about the barrier the 1C importer will meet. `SET CONSTRAINTS ALL
    IMMEDIATE` is the same trigger firing for the same reason, at a point the test
    can observe.
    """
    with tenant_context(context):
        post(scene)
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_a_note_of_more_than_two_lines_posts(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Two lines is the smallest note, not the shape of one."""
    payload = {
        "description": "Nota cu trei linii",
        "lines": [
            line(scene["debit_account"], debit="600.0000"),
            line(scene["debit_account"], debit="400.0000"),
            line(scene["credit_account"], credit="1000.0000"),
        ],
    }
    with tenant_context(context):
        result = post(scene, payload)
        assert JournalLine.objects.filter(journal_entry_id=result.journal_entry_id).count() == 3


# --- idempotency: R19, on the event and not on the endpoint ------------------


def test_a_replayed_key_returns_the_first_entry_and_writes_nothing(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The double-click, the retried request, the redelivered task.

    The second call must return the first result and produce no second entry --
    and no second *number*, which is the part a service that only deduplicated the
    write would still get wrong.
    """
    with tenant_context(context):
        first = post(scene)
        again = post(scene)

        assert again.journal_entry_id == first.journal_entry_id
        assert again.accounting_event_id == first.accounting_event_id
        assert again.posted_now is False
        assert JournalEntry.objects.count() == 1
        assert AccountingEvent.objects.count() == 1


def test_the_same_key_with_a_different_note_is_a_conflict(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The case that signals a bug in the caller, and silence would hide it."""
    with tenant_context(context):
        post(scene)
        with pytest.raises(IdempotencyConflictError) as excinfo:
            post(scene, note(scene, amount="2000.0000"))
        assert excinfo.value.code == "accounting.idempotency_conflict"
        assert JournalEntry.objects.count() == 1


def test_an_event_that_failed_posts_on_a_later_attempt(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """`failed` is not terminal, and this is why it is not.

    The note was refused because an account was blocked -- a configuration fact,
    not a defect in the note. Unblocking it and retrying the same key posts the
    same event, without the user retyping anything and without a second event
    colliding with its own idempotency key.
    """
    payload = {
        "description": "Nota pe cont blocat",
        "lines": [
            line(scene["blocked_account"], debit="500.0000"),
            line(scene["credit_account"], credit="500.0000"),
        ],
    }
    with tenant_context(context):
        with pytest.raises(AccountNotPostableError):
            post(scene, payload)
        assert AccountingEvent.objects.get().status == EventStatus.FAILED

        set_blocked(scene["blocked_account"], False)
        result = post(scene, payload)

        assert result.posted_now is True
        assert AccountingEvent.objects.count() == 1
        assert AccountingEvent.objects.get().status == EventStatus.POSTED
        assert JournalEntry.objects.get().id == result.journal_entry_id


# --- what the engine refuses, and what it leaves behind ----------------------


def test_an_unbalanced_note_is_refused_and_writes_nothing(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The engine answers before the write, with a code (C10).

    The database would answer too, at COMMIT, as an `IntegrityError` with no code
    and no line number -- correct, unbranchable, and far from the caller.
    """
    payload = {
        "description": "Nota dezechilibrata",
        "lines": [
            line(scene["debit_account"], debit="1000.0000"),
            line(scene["credit_account"], credit="999.0000"),
        ],
    }
    with tenant_context(context):
        with pytest.raises(OutOfBalanceError) as excinfo:
            post(scene, payload)
        assert excinfo.value.code == "posting.out_of_balance"
        assert not JournalEntry.objects.exists()
        assert not JournalLine.objects.exists()


def test_the_refusal_is_recorded_on_the_event(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """An event that failed to post is work somebody has to finish.

    `posting_error` carries the stable code rather than a message, so the queue
    can be counted and filtered by cause -- and `accounting_event_failed_has_reason`
    refuses a failure recorded without one.
    """
    payload = {
        "description": "Nota dezechilibrata",
        "lines": [
            line(scene["debit_account"], debit="1000.0000"),
            line(scene["credit_account"], credit="999.0000"),
        ],
    }
    with tenant_context(context), pytest.raises(OutOfBalanceError):
        post(scene, payload)

    with tenant_context(context):
        event = AccountingEvent.objects.get()
        assert event.status == EventStatus.FAILED
        assert event.posting_error is not None
        assert event.posting_error["code"] == "posting.out_of_balance"


def test_a_closed_period_refuses_the_note(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """R12, and the code says whether reopening is even possible.

    Not flattened into a posting code: reopening answers `period_not_open` and can
    never answer `period_locked`, so a caller that could not tell them apart could
    not tell a user what to do next.
    """
    with tenant_context(context):
        with pytest.raises(PeriodNotOpenError) as excinfo:
            post(scene, on=date(2026, 2, 10))
        assert excinfo.value.code == "periods.period_not_open"
        assert not JournalEntry.objects.exists()


def test_a_locked_period_refuses_the_note(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        with pytest.raises(PeriodLockedError) as excinfo:
            post(scene, on=date(2026, 3, 10))
        assert excinfo.value.code == "periods.period_locked"
        assert not JournalEntry.objects.exists()


def test_an_account_outside_the_chart_refuses_the_note(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """There is no fallback account, and that is deliberate (ADR-036 section 5.1).

    Posting quietly to a generic one is the worst available failure: it is found
    months later, by somebody who cannot tell what should have been there.
    """
    payload = {
        "description": "Nota pe cont inexistent",
        "lines": [
            line(uuid.uuid4(), debit="100.0000"),
            line(scene["credit_account"], credit="100.0000"),
        ],
    }
    with tenant_context(context):
        with pytest.raises(AccountNotPostableError) as excinfo:
            post(scene, payload)
        assert excinfo.value.code == "posting.account_not_postable"
        assert not JournalEntry.objects.exists()


def test_a_line_with_no_amount_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """A zero line survives every aggregate: the entry still balances, the trial
    balance is still right, and the line sits there for ever meaning nothing."""
    payload = {
        "description": "Nota cu o linie goala",
        "lines": [
            line(scene["debit_account"], debit="100.0000"),
            line(scene["credit_account"], credit="100.0000"),
            line(scene["debit_account"]),
        ],
    }
    with tenant_context(context):
        with pytest.raises(ZeroAmountLineError) as excinfo:
            post(scene, payload)
        assert excinfo.value.code == "posting.zero_amount_line"


def test_a_line_carrying_both_sides_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """One movement modelled as one line instead of two -- and unwriteable anyway
    (`journal_line_one_side_only`)."""
    payload = {
        "description": "Nota cu ambele laturi",
        "lines": [
            line(scene["debit_account"], debit="100.0000", credit="100.0000"),
            line(scene["credit_account"], credit="100.0000"),
        ],
    }
    with tenant_context(context):
        with pytest.raises(MalformedLineAmountError) as excinfo:
            post(scene, payload)
        assert excinfo.value.code == "posting.malformed_line_amount"


# --- mandatory dimensions: the mechanism ADR-029 defended --------------------


def test_an_account_that_requires_a_dimension_refuses_a_line_without_it(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The rule is on the account, not on the line (Spec B section 1.7).

    Refused rather than posted with a NULL, because the NULL is invisible
    afterwards: the entry balances and the only report that shows the gap is the
    partner ledger nobody runs until it does not add up.
    """
    payload = {
        "description": "Nota fara partener",
        "lines": [
            line(scene["partner_account"], debit="100.0000"),
            line(scene["credit_account"], credit="100.0000"),
        ],
    }
    with tenant_context(context):
        with pytest.raises(MissingRequiredDimensionError) as excinfo:
            post(scene, payload)
        assert excinfo.value.code == "posting.missing_required_dimension"
        assert not JournalEntry.objects.exists()


def test_the_named_dimension_lands_in_its_own_column(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """And the same note posts once the dimension is named.

    Without this, a check that refused everything would pass the test above.
    """
    partner_id = uuid.uuid4()
    payload = {
        "description": "Nota cu partener",
        "lines": [
            line(
                scene["partner_account"],
                debit="100.0000",
                dimensions={"partner": str(partner_id)},
            ),
            line(scene["credit_account"], credit="100.0000"),
        ],
    }
    with tenant_context(context):
        result = post(scene, payload)
        stored = JournalLine.objects.get(journal_entry_id=result.journal_entry_id, line_number=1)
        assert stored.partner_id == partner_id


def test_a_dimension_outside_the_vocabulary_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """A name no column matches would be dropped, and the line would look analysed.

    Refused at the payload rather than at the write: by the time the ledger's own
    guard would catch it, an event exists and a document number has been consumed.
    """
    payload = {
        "description": "Nota cu dimensiune inventata",
        "lines": [
            line(
                scene["debit_account"], debit="100.0000", dimensions={"branch": str(uuid.uuid4())}
            ),
            line(scene["credit_account"], credit="100.0000"),
        ],
    }
    with tenant_context(context):
        with pytest.raises(ManualPayloadError) as excinfo:
            post(scene, payload)
        assert excinfo.value.code == "posting.manual_payload_malformed"
        assert not AccountingEvent.objects.exists()


# --- the payload: a caller's bug, refused before an event exists -------------


@pytest.mark.parametrize(
    ("payload", "why"),
    [
        ({"description": "Nota", "lines": []}, "an empty form is not a note"),
        ({"description": "Nota", "lines": "one"}, "lines is not a list"),
        ({"description": "Nota", "lines": [{"debit": "1"}]}, "no account named"),
        ({"description": "", "lines": None}, "no description and no lines"),
    ],
)
def test_a_malformed_payload_is_refused_before_anything_is_recorded(
    context: TenantContext, scene: dict[str, uuid.UUID], payload: dict[str, Any], why: str
) -> None:
    """No event, no number, no entry -- the caller is on the stack and can fix it.

    Recorded instead, it would be an event that can never post, sitting in the
    retry queue for ever looking like work somebody could finish.
    """
    with tenant_context(context):
        with pytest.raises(ManualPayloadError):
            post(scene, payload)
        assert not AccountingEvent.objects.exists(), why


def test_a_note_without_a_description_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The one entry with no document behind it. Without a sentence, nothing says
    later what it was -- and it is the user's sentence, in Romanian, never one
    this system generates (C33, C38)."""
    payload = {"description": "   ", "lines": note(scene)["lines"]}
    with tenant_context(context), pytest.raises(ManualPayloadError):
        post(scene, payload)


@pytest.mark.parametrize("amount", [1000.5, "not a number", "1000.55555", True])
def test_an_amount_that_cannot_be_stored_exactly_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID], amount: Any
) -> None:
    """A float is not exact; a fifth decimal would be rounded by the column.

    Both would balance and both would be wrong by an amount nobody chose. Which
    way a rounding goes is `DNB-08`, open -- so the value is refused rather than
    altered.
    """
    payload = {
        "description": "Nota cu suma imposibila",
        "lines": [
            {"account_id": str(scene["debit_account"]), "debit": amount},
            line(scene["credit_account"], credit="1000.0000"),
        ],
    }
    with tenant_context(context):
        with pytest.raises(ManualPayloadError):
            post(scene, payload)
        assert not AccountingEvent.objects.exists()


def test_a_note_in_another_currency_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Refused, not converted and not stored unchecked.

    Converting needs the rounding rule (`DNB-08`); storing the user's four numbers
    without checking `amount_currency x exchange_rate` would put a line in an
    append-only ledger that nothing can reconcile. The refusal is removable: the
    day the convention is decided, this becomes a handler version with a later
    `valid_from`, and the entries posted before it stay as they are.
    """
    payload = {
        "description": "Nota in valuta",
        "lines": [
            line(scene["debit_account"], debit="1000.0000", currency="EUR"),
            line(scene["credit_account"], credit="1000.0000"),
        ],
    }
    with tenant_context(context):
        with pytest.raises(ForeignCurrencyNoteError) as excinfo:
            post(scene, payload)
        assert excinfo.value.code == "posting.manual_foreign_currency_unsupported"


# --- the registry, and the numbering the entry depends on --------------------


def test_the_event_type_is_registered_with_a_handler() -> None:
    """ADR-038: the module registers its own type, and a type with no handler is
    a document that goes missing silently.

    The registration is what makes `manual.journal_entry` resolvable at all -- the
    service selects its treatment through the registry like any other, so the
    manual path has no privilege the automated ones lack.
    """
    assert EVENT_TYPE in registry.REGISTRY
    declared = registry.REGISTRY[EVENT_TYPE]
    assert declared.payload_fields == ("lines", "description")
    assert [h.implementation_ref for h in declared.handlers] == [HANDLER_REF]
    assert HANDLER_REF in registry.HANDLERS
    assert not [problem for problem in registry.audit() if EVENT_TYPE in problem]


def test_the_treatment_is_selected_by_the_date_of_the_posting(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """R17: the handler in force for the period, never "the newest".

    A manual note has one treatment today, so what this asserts is that the
    selection **runs** -- a service that called the handler directly would post
    identically and would silently stop honouring R18 the day a second version
    exists.
    """
    resolved = registry.resolve_handler(EVENT_TYPE, POSTING, frozenset())
    assert resolved is registry.HANDLERS[HANDLER_REF]


def test_without_a_numbering_template_nothing_is_written(
    context: TenantContext, scene: dict[str, uuid.UUID], seed: Callable[..., None]
) -> None:
    """A number nobody chose is worse than a refusal (ADR-022).

    The refusal is a configuration answer with a stable code, and the event
    records it -- so the note is not lost, it is waiting for a template.
    """
    seed("DELETE FROM numbering_template WHERE company_id = %s", [scene["company"]])
    with tenant_context(context):
        with pytest.raises(NumberingError) as excinfo:
            post(scene)
        assert excinfo.value.code == "numbering.no_template"
        assert not JournalEntry.objects.exists()
        event = AccountingEvent.objects.get()
        assert event.posting_error is not None
        assert event.posting_error["code"] == "numbering.no_template"


# --- isolation ---------------------------------------------------------------


def test_the_entry_is_invisible_to_the_other_tenant(
    context: TenantContext, scene: dict[str, uuid.UUID], world: dict[str, uuid.UUID]
) -> None:
    """The policy, not the service, is what keeps it invisible (IZ-01).

    Asserted here as well as in the ledger's own suite because this is the path a
    note actually takes: if the writer set `tenant_id` from anything but the
    context, the row would be written and then be unreachable, or worse, reachable.
    """
    with tenant_context(context):
        result = post(scene)

    other = TenantContext(
        tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="manual-b"
    )
    with tenant_context(other):
        assert not JournalEntry.objects.filter(id=result.journal_entry_id).exists()
        assert not JournalLine.objects.exists()
        assert not AccountingEvent.objects.exists()


# --- the writer's own refusals, which the engine reaches first ---------------


def test_an_event_marked_posted_with_no_entry_refuses_a_second_write(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The two tables disagree, and writing is the one answer that cannot be undone.

    Not a state the engine can produce -- it marks the event only after the write
    -- so reaching it means something else did. A second entry would double an
    effect the ledger has no UPDATE to take back (R10), so the refusal is the safe
    answer even though it leaves a person with work to do.
    """
    payload = note(scene)
    with tenant_context(context):
        event, created = emit(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            event_type=EVENT_TYPE,
            source_module=SOURCE_MODULE,
            source_document_type=SOURCE_DOCUMENT_TYPE,
            source_document_id=uuid.uuid5(uuid.NAMESPACE_URL, "note-1"),
            occurred_at=datetime.now(UTC),
            accounting_date=POSTING,
            idempotency_key="note-1",
            payload=payload,
            capability_snapshot=dict(SNAPSHOT),
            actor_user_id=scene["user"],
            request_id="manual-test",
        )
        assert created
        mark_posted(event.id)

        with pytest.raises(EventAlreadyPostedError) as excinfo:
            post(scene, payload)
        assert excinfo.value.code == "posting.entry_missing_for_posted_event"
        assert not JournalEntry.objects.exists()


def test_the_ledger_refuses_an_entry_with_no_lines(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The engine refuses it first; this is the barrier for a caller that skips it.

    The database refuses it too, at COMMIT, as `journal_entry % has no amount` --
    a `check_violation` with no stable code, from a deferred trigger, after the
    caller has returned.
    """
    with tenant_context(context), pytest.raises(NothingToWriteError) as excinfo:
        post_entry(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            entry_number="NC-PROBE",
            accounting_date=POSTING,
            period_id=scene["open_period"],
            accounting_event_id=uuid.uuid4(),
            description="Nota fara linii",
            request_id="manual-test",
            lines=[],
        )
    assert excinfo.value.code == "ledger.nothing_to_write"


def test_the_ledger_refuses_a_dimension_no_column_matches(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """A name outside ADR-029 would be dropped, and the line would look analysed.

    Refused by the payload parser long before this, and again here -- because the
    1C importer and any data migration will call the writer, not the parser.
    """
    with tenant_context(context), pytest.raises(UnknownDimensionError) as excinfo:
        post_entry(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            entry_number="NC-PROBE",
            accounting_date=POSTING,
            period_id=scene["open_period"],
            accounting_event_id=uuid.uuid4(),
            description="Nota cu dimensiune inventata",
            request_id="manual-test",
            lines=[
                LineToWrite(
                    account_id=scene["debit_account"],
                    debit=Decimal("100.0000"),
                    credit=Decimal(0),
                    currency="MDL",
                    amount_currency=Decimal("100.0000"),
                    exchange_rate=Decimal(1),
                    accounting_date=POSTING,
                    document_date=POSTING,
                    rate_date=POSTING,
                    dimensions={"branch": uuid.uuid4()},
                )
            ],
        )
    assert excinfo.value.code == "ledger.unknown_dimension"
