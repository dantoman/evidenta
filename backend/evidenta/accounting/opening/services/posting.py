"""Opening balances enter the ledger as a posting -- ADR-039 section 11.

    "Intra ca postare intr-o perioada de deschidere, prin `event_type` propriu
     (`opening.balance.posted`)."

So there is no bulk writer, no "seed the ledger" path and no privileged INSERT.
A validated batch takes the same seven steps a sales invoice will take -- the
treatment is selected from the registry by effective date and capability profile
(R17, R26), an accounting event is recorded under an idempotency key (R19), the
six invariants are checked (F1.4.3), the account's mandatory dimensions are
checked, a number is allocated from the company's own template (ADR-022), the
ledger writes, and the event is marked posted. The batch is the source document
of the R13 chain, and it is a real row, which is more than the manual note can
say.

**The entry Spec B section 8.3 describes, and why the technical account earns
its lines.** One ``JournalEntry`` with ``entry_type = 'opening'`` and
``accounting_date = as_of_date``. Every balance is posted **against a technical
opening account**, which therefore ends the entry with a zero balance -- the test
that the import is complete.

That mirroring is what makes the entry readable rather than merely balanced. The
GL set already balances, checked before anything is written, so an entry made of
the balances alone would balance too. What it would not have is *correspondence*:
Cartea Mare shows each account against the account it moved against, and an
opening entry that paired an unrelated debtor with an unrelated creditor would
fill that column with nonsense for every account a company owns. The technical
account is the one honest answer to "against what".

**The analytical sets post; their GL rows do not.** An account detailed by
partners, items or assets contributes one line per detail row, carrying the
dimension the synthetic figure cannot. Its GL row is the control total that
``batches.check_contents`` compared them against, and posting both would double
every receivable in the company.

**The payroll set does not post at all** (`OD-04`). Year-to-date income and
contribution amounts are not balances; they are the base an IPC calculation
continues from when payroll is activated mid-year. They ride with the batch,
frozen and auditable, and the module that reads them does not exist yet. Nothing
here interprets ``code``.

**No account code appears in this module** (R15, `OD-22`/`OD-23`). Accounts,
including the technical one, are named by id, and the chart is asked whether that
id may receive a posting on ``as_of_date``.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from django.db import transaction

from evidenta.accounting.coa.services.accounts import postable_accounts
from evidenta.accounting.coa.services.chart import chart_version_of
from evidenta.accounting.events.registry import (
    HANDLERS,
    EventType,
    HandlerVersion,
    register,
)
from evidenta.accounting.events.services.emission import emit
from evidenta.accounting.events.services.lifecycle import mark_failed, mark_posted
from evidenta.accounting.ledger.services.lineage import event_id_of_entry, reversal_of_entry
from evidenta.accounting.ledger.services.writing import (
    LineToWrite,
    entry_id_of_event,
    post_entry,
)
from evidenta.accounting.opening.errors import (
    BatchAlreadyPostedError,
    EntryMissingForPostedEventError,
    OpeningAlreadyPostedError,
    OpeningBalanceError,
    StartPeriodFixedError,
)
from evidenta.accounting.opening.models import BatchStatus, OpeningBalanceBatch
from evidenta.accounting.opening.services.batches import (
    ZERO,
    BatchContents,
    assert_transition,
    batch_in_context,
    check_contents,
    load_contents,
    posting_dimensions,
    summary,
)
from evidenta.accounting.posting.dimensions import assert_dimensions_present
from evidenta.accounting.posting.invariants import (
    Origin,
    ProposedLine,
    ProposedPosting,
    verify,
)
from evidenta.accounting.posting.resolution import selected_treatment
from evidenta.accounting.posting.services.reversal import (
    HANDLER_REF as REVERSAL_HANDLER_REF,
)
from evidenta.accounting.posting.services.reversal import (
    REVERSAL_SUFFIX,
)
from evidenta.platform.api.errors import ApiError
from evidenta.platform.numbering.services.allocation import NumberingError, allocate

#: **Two accepted ADRs disagree about this string, and the disagreement is
#: reported rather than resolved here.**
#:
#: ADR-039 section 11 writes the type as ``opening.balance.posted`` -- three
#: segments. Spec B section 1.4 fixes the form as ``<domeniu>.<actiune>``, and
#: ADR-038 makes the registry enforce it with a regular expression that admits
#: exactly two: ``sales.invoice_issued``, "not `sales.invoice.issued`", in that
#: module's own words. The three-segment spelling **cannot be registered**; it
#: raises `accounting.event_type_malformed` at import.
#:
#: Spelled to the convention, because ADR-038 is the decision that owns the
#: vocabulary's *form* while ADR-039 section 11 names the type in passing while
#: deciding about currencies and periods. One of the two documents needs a
#: one-word correction, and which one is the owner's call, not this module's.
EVENT_TYPE = "opening.balance_posted"

#: A **key into `HANDLERS`**, never an importable path (ADR-038 section 4).
HANDLER_REF = "opening.balance_posted.v1"

#: ``accounting_event.source_module``, as a string rather than
#: ``events.models.SourceModule`` -- importing that enum would be `D6`, and the
#: value is validated by a CHECK in the database, which is the barrier that holds.
#:
#: **``migration`` rather than a value of this module's own, and that is a
#: reported gap.** The vocabulary is ``sales``, ``purchases``, ``payroll``,
#: ``banking``, ``assets``, ``migration``, ``manual``; adding a seventh would be
#: an edit to another module's model and its CHECK constraint. ``migration`` is
#: the closest true statement -- opening balances are a company's history
#: arriving from wherever it was kept before -- and the batch's own ``source``
#: column carries the finer distinction Spec B section 8.1 asks for
#: (``manual`` / ``onec_import`` / ``other_system``).
SOURCE_MODULE = "migration"

#: The document behind the entry, and unlike the manual note it is a real row in
#: a real table -- the fourth link of the R13 chain resolves to something.
SOURCE_DOCUMENT_TYPE = "opening_balance_batch"

#: ``journal_entry.entry_type``, as a string rather than ``ledger.models.EntryType``.
#: Importing that enum is `D6` -- measured, not assumed: the dependency guard
#: reported it on the first run. The value is validated by
#: ``journal_entry_type_valid`` in the database, which is the barrier that holds,
#: and Spec B section 8.3 fixes which value it is.
ENTRY_TYPE = "opening"

#: One series per company for every journal entry unless the company configures a
#: template for this type (ADR-022). Deliberately not a series of its own for
#: ``opening``: splitting the register per entry type is a decision about how a
#: company's books look, it can be made later by configuring a template named for
#: the type, and baking it in now would make it unmakeable.
NUMBERING_DOCUMENT_TYPE = "journal_entry"

#: The entry's description, in Romanian, because it lands in a register (C33).
#:
#: A constant rather than formatted text: nothing here consults the active
#: language, which is the property C38 protects, and the date is rendered ISO --
#: a machine form that no locale changes. The `ro-MD` document formatting module
#: C38 names does not exist yet, and inventing half of it here would be worse
#: than an ISO date in one description.
DESCRIPTION = "Solduri inițiale la"


class OpeningLineError(OpeningBalanceError):
    """The batch cannot be turned into lines this ledger can hold.

    Reachable only through a replay of an event whose batch has since become
    unreadable, or through a caller that skipped validation -- both of which are
    refusals rather than states to repair.
    """

    code = "opening.batch_unpostable"


@dataclass(frozen=True, slots=True)
class OpeningLine:
    """One proposed line, before the mirror against the technical account.

    **Not the general handler contract** (F1.4.4, blocked on `C1`-`C5` of ADR-036
    section 11). It is the shape an opening balance takes: one account, one side,
    the dimension the analytical set carries, and -- for stock -- the quantity and
    its unit, which a journal line may hold only together
    (``journal_line_quantity_has_unit``).
    """

    account_id: uuid.UUID
    debit: Decimal
    credit: Decimal
    dimensions: Mapping[str, uuid.UUID] = field(default_factory=dict)
    quantity: Decimal | None = None
    uom_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class OpeningEntryResult:
    """What one call to ``post_batch`` settled.

    ``posted_now`` is False when the batch was already in the ledger -- either
    through this idempotency key or through an earlier one. A caller that cannot
    tell the two apart tells the accountant the balances loaded twice.
    """

    batch_id: uuid.UUID
    accounting_event_id: uuid.UUID
    journal_entry_id: uuid.UUID
    posted_now: bool


# --- the handler -------------------------------------------------------------


def record_opening_lines(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    accounting_date: date,
    functional_currency: str,
    payload: Mapping[str, Any],
) -> tuple[OpeningLine, ...]:
    """Turn one validated batch into the lines that post. Derive nothing.

    Registered as the treatment of ``opening.balance.posted`` and selected
    through the registry like any other, so the opening path has no privilege the
    automated ones lack. The signature is the one every treatment gets; a handler
    that needed a different set of arguments than its siblings would be the second
    path this design exists to prevent.

    The checks are run again here rather than trusted from validation. They are
    cheap, the batch is frozen so they cannot fail, and the point is R18: this
    function is what a replay in 2030 calls, and it must be able to say for itself
    that the rows it read are consistent.
    """
    del tenant_id  # the scope is the engine's to check, not the handler's

    raw = payload.get("batch_id")
    try:
        batch_id = uuid.UUID(str(raw))
    except (ValueError, AttributeError, TypeError):
        raise OpeningLineError(f"payload names batch {raw!r}, which is not an identifier") from None

    batch = batch_in_context(batch_id)
    if batch.company_id != company_id or batch.as_of_date != accounting_date:
        raise OpeningLineError(
            f"batch {batch.id} belongs to company {batch.company_id} as of "
            f"{batch.as_of_date}; the event says {company_id} as of {accounting_date}"
        )

    contents = load_contents(batch)
    check_contents(contents, functional_currency)
    return proposed_lines(contents)


def proposed_lines(contents: BatchContents) -> tuple[OpeningLine, ...]:
    """The balances that post, in the order the entry will read.

    **Ordered by account code**, which is how a trial balance is read and the only
    ordering an accountant can check against the sheet they typed from. The
    alternative -- the order the rows happen to come back in -- is a random UUID
    ordering wearing determinism's clothes: stable across two runs, meaningless to
    the person reading the register.

    The codes come from the chart, resolved at the posting date like every other
    question about an account. An account the chart does not carry sorts last and
    is refused a moment later by invariant 4; ordering is not the place to
    discover it.

    An account the analytical sets decompose contributes its **detail** rows and
    not its GL row. Both would double it, and which of the two is authoritative is
    not a choice: only the detail carries the dimension.
    """
    order = {
        account.id: index
        for index, account in enumerate(
            postable_accounts(contents.batch.company_id, contents.batch.as_of_date)
        )
    }
    last = len(order)

    detail = _detail_by_account(contents)
    lines: list[OpeningLine] = []
    for row in sorted(contents.gl, key=lambda gl: (order.get(gl.account_id, last), str(gl.id))):
        rows = detail.get(row.account_id)
        if rows is None:
            lines.append(OpeningLine(account_id=row.account_id, debit=row.debit, credit=row.credit))
        else:
            lines.extend(rows)
    return tuple(lines)


def _detail_by_account(contents: BatchContents) -> dict[uuid.UUID, list[OpeningLine]]:
    """Every analytical row, grouped under the GL account it decomposes.

    ``check_contents`` has already established that each of these accounts carries
    a GL row and that the two agree, so grouping here cannot lose a row: iterating
    the GL set reaches every group.
    """
    grouped: dict[uuid.UUID, list[OpeningLine]] = {}

    for row in (*contents.receivables, *contents.payables):
        grouped.setdefault(row.account_id, []).append(
            OpeningLine(
                account_id=row.account_id,
                debit=row.debit,
                credit=row.credit,
                dimensions={"partner": row.partner_id},
            )
        )

    for stock in contents.inventory:
        dimensions: dict[str, uuid.UUID] = {"item": stock.item_id}
        if stock.warehouse_id is not None:
            dimensions["warehouse"] = stock.warehouse_id
        grouped.setdefault(stock.account_id, []).append(
            OpeningLine(
                account_id=stock.account_id,
                debit=stock.debit,
                credit=stock.credit,
                dimensions=dimensions,
                quantity=stock.quantity,
                uom_id=stock.uom_id,
            )
        )

    for asset in contents.assets:
        grouped.setdefault(asset.cost_account_id, []).append(
            OpeningLine(
                account_id=asset.cost_account_id,
                debit=asset.entry_cost,
                credit=ZERO,
                dimensions={"asset": asset.asset_id},
            )
        )
        # A zero leg produces no line rather than a zero one: an asset bought last
        # month has no accumulated depreciation, and the ledger refuses a line
        # with no amount anyway (invariant 5, `journal_line_one_side_only`).
        if asset.accumulated_depreciation != ZERO:
            grouped.setdefault(asset.depreciation_account_id, []).append(
                OpeningLine(
                    account_id=asset.depreciation_account_id,
                    debit=ZERO,
                    credit=asset.accumulated_depreciation,
                    dimensions={"asset": asset.asset_id},
                )
            )

    return grouped


HANDLERS[HANDLER_REF] = record_opening_lines

register(
    EventType(
        name=EVENT_TYPE,
        #: Checked at emission, where a missing field is still the caller's bug.
        payload_fields=("batch_id", "as_of_date"),
        #: None. Opening balances name accounts directly, like a manual note:
        #: roles exist so that a *computed* treatment does not have to (ADR-036
        #: section 5.1), and nothing here is computed.
        account_roles=(),
        handlers=(HandlerVersion(implementation_ref=HANDLER_REF, valid_from=date.min),),
        description=(
            "The opening balances of one company, as of one date, carried into "
            "the ledger as a single entry against a technical opening account."
        ),
    )
)


# --- the service -------------------------------------------------------------


def post_batch(
    *,
    batch_id: uuid.UUID,
    functional_currency: str,
    idempotency_key: str,
    actor_user_id: uuid.UUID,
    request_id: str,
    capability_snapshot: dict[str, Any],
    occurred_at: datetime | None = None,
) -> OpeningEntryResult:
    """Carry a validated batch into the ledger, or refuse with a stable code.

    ``functional_currency`` is a **parameter, not a lookup**, for the reason R26
    gives for the capability profile: the currency a company keeps its books in
    lives on ``platform.tenancy``, and that module publishes no accessor for it,
    so reading it here would be the `D6` import the rule is about. Stating it also
    records it -- the caller says which currency it believes it is loading, and a
    balance that disagrees is refused rather than assumed away.

    ``capability_snapshot`` is the profile as ``platform.capabilities`` writes it.
    It selects the treatment (R26) and is stored on the event, so that reading
    this period back years later selects what today selected (R18).
    """
    batch = batch_in_context(batch_id)

    # Already in the ledger. Answered before the event is touched, because a
    # second posting under a *different* idempotency key would sail past every
    # check the event layer makes and double the whole trial balance.
    if batch.status == BatchStatus.POSTED:
        if batch.journal_entry_id is None:  # pragma: no cover -- CHECK forbids it
            raise BatchAlreadyPostedError(f"batch {batch.id} is posted and names no entry")
        event_id = _event_of(batch)
        return OpeningEntryResult(batch.id, event_id, batch.journal_entry_id, posted_now=False)

    assert_transition(batch, BatchStatus.POSTED)
    _assert_start_period_free(batch)

    treatment = selected_treatment(EVENT_TYPE, batch.as_of_date, capability_snapshot)
    contents = load_contents(batch)
    payload: dict[str, Any] = {
        "batch_id": str(batch.id),
        "as_of_date": batch.as_of_date.isoformat(),
        "source": batch.source,
        "counterpart_account_id": str(batch.counterpart_account_id),
        "sets": summary(contents),
    }

    lines: tuple[OpeningLine, ...] = treatment.handler(
        tenant_id=batch.tenant_id,
        company_id=batch.company_id,
        accounting_date=batch.as_of_date,
        functional_currency=functional_currency,
        payload=payload,
    )
    if not all(isinstance(line, OpeningLine) for line in lines):
        raise OpeningLineError(
            f"the treatment registered for {EVENT_TYPE} returned something other "
            f"than opening lines; a registration selects an implementation, and "
            f"this one does not match the type it was selected for"
        )

    event, created = emit(
        tenant_id=batch.tenant_id,
        company_id=batch.company_id,
        event_type=EVENT_TYPE,
        source_module=SOURCE_MODULE,
        source_document_type=SOURCE_DOCUMENT_TYPE,
        source_document_id=batch.id,
        occurred_at=occurred_at or datetime.now(UTC),
        accounting_date=batch.as_of_date,
        idempotency_key=idempotency_key,
        payload=payload,
        capability_snapshot=capability_snapshot,
        actor_user_id=actor_user_id,
        request_id=request_id,
    )

    if not created:
        settled = entry_id_of_event(event.id)
        if settled is not None:
            return OpeningEntryResult(batch.id, event.id, settled, posted_now=False)
        if event.status == "posted":
            raise EntryMissingForPostedEventError(
                f"event {event.id} is marked posted and no entry of it is visible; "
                f"writing a second one would double an effect that cannot be undone"
            )
        # Emitted and never posted -- a previous attempt that failed after the
        # event landed. Finishing it is the point of `failed` not being terminal.

    try:
        with transaction.atomic():
            entry_id = _write(
                batch,
                contents,
                lines,
                functional_currency=functional_currency,
                event_id=event.id,
                actor_user_id=actor_user_id,
                request_id=request_id,
                rule_ref=treatment.ref,
            )
    except (ApiError, NumberingError) as refusal:
        # Written onto the event rather than only raised: an event that failed to
        # post is work somebody has to finish, and an exception in a task
        # disappears into a log. Whether the row survives is the caller's
        # transaction -- an `ApiError` out of a request rolls back
        # `ATOMIC_REQUESTS` and takes the event with it, which is the right
        # outcome when a person is looking at the screen.
        mark_failed(event.id, code=refusal.code, detail={"event_type": EVENT_TYPE})
        raise

    return OpeningEntryResult(batch.id, event.id, entry_id, posted_now=True)


def _assert_start_period_free(batch: OpeningBalanceBatch) -> None:
    """ADR-039 section 11, with a stable code instead of a trigger message.

    A trigger refuses this in the database as well -- and that is the barrier that
    holds, because the 1C importer and any data migration bypass this service.
    What is added here is the code (C10) and the timing: refused before an event
    exists, so nothing lands in the retry queue that could never post.
    """
    posted = list(
        OpeningBalanceBatch.objects.filter(company_id=batch.company_id, status=BatchStatus.POSTED)
        .exclude(id=batch.id)
        .order_by("posted_at")
    )
    fixed = posted[0].as_of_date if posted else None
    if fixed is not None and fixed != batch.as_of_date:
        raise StartPeriodFixedError(
            f"company {batch.company_id} posted its opening balances as of {fixed}; "
            f"batch {batch.id} is dated {batch.as_of_date}. The start period of a "
            f"company is chosen once and does not move (ADR-039 section 11) -- a "
            f"correction is a reversal and a new batch at {fixed}"
        )
    # Same date, but is the earlier entry still standing? Two live opening
    # entries double every balance, and the counterpart nets to zero on each,
    # so nothing else would ever say so (accounting-reviewer, 2026-09-03). The
    # correction path stays exactly as Spec B section 8.3 keeps it: reverse,
    # then post again.
    standing = [
        prior
        for prior in posted
        if prior.journal_entry_id is not None and reversal_of_entry(prior.journal_entry_id) is None
    ]
    if standing:
        raise OpeningAlreadyPostedError(
            f"company {batch.company_id} already has opening balances posted as of "
            f"{batch.as_of_date} (batch {standing[0].id}, entry "
            f"{standing[0].journal_entry_id}) and that entry has not been reversed; a "
            f"second one would double every balance. Reverse it first, then post this batch"
        )


def _event_of(batch: OpeningBalanceBatch) -> uuid.UUID:
    """The event that posted this batch.

    Read back through the entry rather than stored on the batch: the entry names
    its event with a ``NOT NULL`` foreign key, so a second column here could only
    ever disagree with it.
    """
    entry_id = batch.journal_entry_id
    if entry_id is None:  # pragma: no cover -- a CHECK forbids it
        raise BatchAlreadyPostedError(f"batch {batch.id} is posted and names no entry")
    event_id = event_id_of_entry(entry_id)
    if event_id is None:  # pragma: no cover -- the column is NOT NULL
        raise EntryMissingForPostedEventError(f"entry {entry_id} names no accounting event")
    return event_id


def _write(
    batch: OpeningBalanceBatch,
    contents: BatchContents,
    lines: Sequence[OpeningLine],
    *,
    functional_currency: str,
    event_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    request_id: str,
    rule_ref: str,
) -> uuid.UUID:
    """Judge the proposal, hand it to the ledger, and close the batch.

    The order is the contract, and it is the manual note's order for the same
    reasons. ``verify`` refuses on the six invariants and returns the period, so
    nothing resolves it a second time and gets a different answer; the dimensions
    are checked next, because they are a property of the account and invariant 4
    has just established the accounts exist; the number is allocated last before
    the write, because allocation consumes one and a refusal afterwards would
    leave a permanent gap in the register (ADR-022) for an import that never
    happened.

    The batch is closed inside this transaction rather than after it. An entry in
    the ledger with a batch still saying ``validated`` would invite a second
    posting of the same balances, and the ledger has no UPDATE to take the first
    one back with.
    """
    mirrored = _with_counterpart(lines, batch.counterpart_account_id)

    period_id = verify(
        ProposedPosting(
            tenant_id=batch.tenant_id,
            company_id=batch.company_id,
            accounting_date=batch.as_of_date,
            accounting_event_id=event_id,
            origin=Origin(
                module=SOURCE_MODULE,
                document_type=SOURCE_DOCUMENT_TYPE,
                document_id=batch.id,
            ),
            lines=tuple(
                ProposedLine(
                    tenant_id=batch.tenant_id,
                    company_id=batch.company_id,
                    accounting_date=batch.as_of_date,
                    account_id=line.account_id,
                    debit=line.debit,
                    credit=line.credit,
                )
                for line in mirrored
            ),
        )
    )

    assert_dimensions_present(batch.company_id, batch.as_of_date, posting_dimensions(contents))

    # ADR-048: an opening balance computes nothing, so the fiscal date it names
    # is its own, and the chart is the one its accounts came from.
    chart = chart_version_of(batch.company_id)
    number = allocate(batch.tenant_id, batch.company_id, NUMBERING_DOCUMENT_TYPE, batch.as_of_date)

    entry_id = post_entry(
        tenant_id=batch.tenant_id,
        company_id=batch.company_id,
        entry_number=number.formatted,
        accounting_date=batch.as_of_date,
        period_id=period_id,
        accounting_event_id=event_id,
        entry_type=ENTRY_TYPE,
        description=f"{DESCRIPTION} {batch.as_of_date.isoformat()}",
        request_id=request_id,
        posted_by_user_id=actor_user_id,
        rule_ref=rule_ref,
        fiscal_effective_date=batch.as_of_date,
        chart_template_id=chart.template_id if chart is not None else None,
        lines=[
            LineToWrite(
                account_id=line.account_id,
                debit=line.debit,
                credit=line.credit,
                # The books are kept in this currency, so the transaction's own
                # amount is the same number and the rate is exactly 1 (ADR-039
                # section 3). Not a conversion: the other side of the line is
                # zero, so `debit + credit` is the amount and nothing rounds. A
                # balance in another currency never reaches here -- it is refused
                # in `batches._check_currency`.
                currency=functional_currency,
                amount_currency=line.debit + line.credit,
                exchange_rate=Decimal(1),
                accounting_date=batch.as_of_date,
                # Opening balances are the state of the books on that day; there
                # is no earlier document this system knows of, so all three dates
                # are the one date. The document behind a partner balance is
                # recorded on the batch row, where its own date lives.
                document_date=batch.as_of_date,
                rate_date=batch.as_of_date,
                quantity=line.quantity,
                uom_id=line.uom_id,
                dimensions=dict(line.dimensions),
            )
            for line in mirrored
        ],
    )

    mark_posted(event_id)

    batch.status = BatchStatus.POSTED
    batch.posted_at = datetime.now(UTC)
    batch.journal_entry_id = entry_id
    batch.save(update_fields=["status", "posted_at", "journal_entry_id", "updated_at"])
    return entry_id


def _with_counterpart(
    lines: Sequence[OpeningLine], counterpart_account_id: uuid.UUID
) -> tuple[OpeningLine, ...]:
    """Each balance, followed by its mirror on the technical opening account.

    Pairwise rather than two aggregate lines, and the difference is what a reader
    sees: Cartea Mare shows an account against the account it moved against, so a
    partner's opening balance has to face the technical account and not whatever
    unrelated creditor happened to be next in the entry.

    The quantity does **not** cross over. A quantity on the technical account
    would add stock to an account that holds none, and the unit column exists to
    make that visible rather than to be filled twice.
    """
    mirrored: list[OpeningLine] = []
    for line in lines:
        mirrored.append(line)
        mirrored.append(
            OpeningLine(
                account_id=counterpart_account_id,
                debit=line.credit,
                credit=line.debit,
            )
        )
    return tuple(mirrored)


# --- the storno pair ------------------------------------------------------------------
#
# Spec B section 8.3 keeps the correction path open: reverse the posted opening
# entry, then post a new batch at the same date. The reversal service selects
# the pair by suffix and refuses a type nobody registered, and until now nobody
# had -- so the path existed on paper only. The mirror handler names no roles:
# it uses the accounts already posted.
register(
    EventType(
        name=EVENT_TYPE + REVERSAL_SUFFIX,
        payload_fields=("reverses_entry_id", "reason"),
        account_roles=(),
        handlers=(HandlerVersion(implementation_ref=REVERSAL_HANDLER_REF, valid_from=date.min),),
        description=(
            "The cancellation of an opening-balance entry: the original's lines with "
            "debit and credit swapped, linked to the batch and to the entry it cancels "
            "(R14), so a corrected batch can be posted at the same date."
        ),
    )
)
