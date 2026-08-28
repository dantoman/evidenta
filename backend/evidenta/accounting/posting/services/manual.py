"""The manual journal note -- F1.7.1, Spec B section 1.5.

    "Chiar si o nota manuala trece prin `accounting_event` (R9). Tipul este
    `manual.journal_entry`, iar `payload` contine liniile propuse de utilizator.
    Posting Engine le valideaza (echilibru, conturi existente si active, perioada
    deschisa, dimensiuni obligatorii) si le posteaza."

And the reason, which is the actual criterion of the task:

    "altfel apar doua cai catre ledger, iar lineage-ul, idempotenta si enumerarea
    efectelor trebuie implementate de doua ori. A doua implementare este
    intotdeauna cea care se strica."

So there is no shortcut here. A manual note takes the same seven steps a posting
produced by `sales` will take: a treatment is selected from the registry by
effective date and capability profile (R17, R26), an accounting event is recorded
under an idempotency key (R19), the six invariants are checked (ADR-036 section
5.2), the account's mandatory dimensions are checked, a number is allocated from
the company's own template (ADR-022), the entry is written by the ledger, and the
event is marked posted.

**What is different about it, and it is only one thing: nothing is derived.** A
handler for a sales invoice computes lines from an economic fact. This handler
reads the lines the user typed and refuses everything it cannot store exactly --
a float amount, a fifth decimal, a foreign currency. Deriving would mean a
rounding rule, and which rule that is (`DNB-08`) is open. The task says it in as
many words: the engine "posteaza **fara sa derive** liniile".

**Where the payload is refused, and where the event is.** A malformed payload is a
bug in the caller, which is on the stack right now, so it is refused before any
event exists -- the same division `events.services.emission` states for the same
reason. A posting the engine judges and rejects -- out of balance, closed period,
blocked account, missing dimension -- happens after the event is recorded, and is
written onto it as `status = 'failed'` with a stable code (C10), which is what
`accounting_event.posting_error` and the retry queue exist for.

Whether that failed row *survives* is the caller's transaction, not this module's:
an `ApiError` raised out of a request rolls back `ATOMIC_REQUESTS`, and the whole
attempt -- event included -- disappears, which is the right outcome when a person
is looking at the screen and will simply fix the note. A task that commits
deliberately keeps the row and the queue entry.

**No account code appears here, and none ever should** (R15, `OD-22`/`OD-23`). The
user names accounts by id; the engine asks the chart whether that id may receive
a posting on that date. The chart's content is an open decision, and a plausible
`221` written into this module would be that content arriving through the back
door.

**The description is the user's, in Romanian, and is never generated.** It lands
in the register (C33), and C38 is about text *this system* produces -- it produces
none here. What it does refuse is an empty one: a manual note is the single entry
with no document behind it, and without a sentence nobody can say later what it
was.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction

from evidenta.accounting.coa.dimensions import DIMENSION_KEYS
from evidenta.accounting.coa.services.chart import chart_version_of
from evidenta.accounting.events.registry import (
    HANDLERS,
    EventType,
    HandlerVersion,
    register,
)
from evidenta.accounting.events.services.emission import emit
from evidenta.accounting.events.services.lifecycle import mark_failed, mark_posted
from evidenta.accounting.ledger.services.writing import (
    LineToWrite,
    entry_id_of_event,
    post_entry,
)
from evidenta.accounting.posting.dimensions import (
    LineDimensions,
    assert_dimensions_present,
)
from evidenta.accounting.posting.invariants import (
    Origin,
    PostingRefusedError,
    ProposedLine,
    ProposedPosting,
    verify,
)
from evidenta.accounting.posting.resolution import selected_treatment
from evidenta.platform.api.errors import ApiError
from evidenta.platform.numbering.services.allocation import NumberingError, allocate

#: Spec B section 1.5 names it. Two segments, `snake_case` -- the form the
#: registry enforces.
EVENT_TYPE = "manual.journal_entry"

#: The implementation key. A **key into `HANDLERS`**, never an importable path:
#: ADR-038 section 4, where the distinction is a security property rather than a
#: style choice.
HANDLER_REF = "manual.journal_entry.v1"

#: `accounting_event.source_module`, as a string rather than
#: `events.models.SourceModule`. Importing that enum would be `D6` -- a service
#: reaching into another module's models -- and the value is validated by
#: `accounting_event_source_module_valid` in the database, which is the barrier
#: that holds. The same choice `events.services.lifecycle` makes for the period
#: codes it names.
SOURCE_MODULE = "manual"

#: The document behind the entry. There is no table of manual notes at F1, so the
#: identifier is the caller's -- see `post_manual_entry`.
SOURCE_DOCUMENT_TYPE = "manual_journal_note"

#: The numbering type the entry's number is drawn from (ADR-022). One series per
#: company for every journal entry, unless the company configures a template for
#: this type; with neither, `resolve_template` falls back to the company's general
#: template and refuses only when there is none.
#:
#: **Deliberately not one series per `entry_type`**, which is one reading of Spec B
#: section 1.2's "numerotare per companie, tip si an". Splitting the register into
#: five series is a decision about how a company's books look, and it can be made
#: later by configuring templates named for the type. Baking it in now would make
#: it unmakeable.
NUMBERING_DOCUMENT_TYPE = "journal_entry"

#: `journal_line.debit` and `.credit` are `numeric(20,4)`. PostgreSQL would round
#: a fifth decimal silently on INSERT, and a rounding nobody decided is exactly
#: what `DNB-08` is open about -- so the engine refuses the value instead of
#: storing a different one than it was given.
SCALE = 4


class ManualPayloadError(PostingRefusedError):
    """The payload is not a set of lines this engine can store as given.

    A caller bug, refused **before** an accounting event exists: the module that
    produced it is on the stack, and an event recorded here could never post, so
    it would sit in the retry queue for ever looking like work.
    """

    code = "posting.manual_payload_malformed"
    status = 400


class ForeignCurrencyNoteError(PostingRefusedError):
    """A manual note in a currency other than the company's functional one.

    Refused rather than converted, and rather than stored unchecked. Converting
    needs a rounding rule (`DNB-08`, open, `ADR-037` still `Propus`); storing the
    user's own four numbers without checking that `amount_currency x
    exchange_rate` equals the functional amount would put a line in an
    append-only ledger that nothing can ever reconcile.

    The refusal is narrow and removable: when the rounding convention is decided,
    a manual note in EUR becomes a handler version with a later `valid_from`, and
    the entries posted before it stay exactly as they were.
    """

    code = "posting.manual_foreign_currency_unsupported"
    status = 409


class EventAlreadyPostedError(PostingRefusedError):
    """The event says it posted, and no entry is visible.

    Not a state the engine can produce -- it marks the event only after the write
    -- so reaching it means the two tables disagree. Refusing is the only safe
    answer: writing a second entry would double the effect, and the ledger has no
    UPDATE to take it back with (R10).
    """

    code = "posting.entry_missing_for_posted_event"
    status = 409


@dataclass(frozen=True, slots=True)
class ManualLine:
    """One line as the user proposed it, parsed and nothing more.

    **Not the general handler contract** (F1.4.4, blocked on `C1`-`C5` of ADR-036
    section 11). It is the shape of a *manual* line: the six columns the
    invariants are about, the three dates, the currency triple that a domestic
    line fixes at 1, and the dimensions. A handler that computes lines from an
    economic fact will need more than this, and what exactly is that task's
    question, not this one's.
    """

    account_id: uuid.UUID
    debit: Decimal
    credit: Decimal
    accounting_date: date
    document_date: date
    currency: str
    description: str | None = None
    dimensions: Mapping[str, uuid.UUID] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ManualEntryResult:
    """What one call to `post_manual_entry` settled.

    `posted_now` is False when the idempotency key found an entry an earlier
    arrival had already written. A caller that cannot tell the two apart sends
    the notification twice -- the same reason `emit` returns a `created` flag.
    """

    accounting_event_id: uuid.UUID
    journal_entry_id: uuid.UUID
    posted_now: bool


# --- the handler -------------------------------------------------------------


def record_manual_lines(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    accounting_date: date,
    functional_currency: str,
    payload: Mapping[str, Any],
) -> tuple[ManualLine, ...]:
    """Read the user's lines out of the payload. Compute nothing.

    Registered as the treatment of `manual.journal_entry` and selected through
    the registry like any other, so that the manual path has no privilege the
    automated ones lack. `tenant_id` and `company_id` are unused today and are
    part of the call because every other treatment will need them -- a handler
    that had to be given a different set of arguments than its siblings would be
    the second path this task exists to prevent.
    """
    del tenant_id, company_id  # the scope is the engine's to check, not the parser's

    raw = payload.get("lines")
    if not isinstance(raw, list) or not raw:
        raise ManualPayloadError(
            "a manual note carries a non-empty `lines` list; an entry that "
            "records nothing is not a note, it is an empty form"
        )

    return tuple(
        _line(item, number, accounting_date, functional_currency)
        for number, item in enumerate(raw, start=1)
    )


def _line(item: Any, number: int, posting_date: date, functional_currency: str) -> ManualLine:
    if not isinstance(item, dict):
        raise ManualPayloadError(f"line {number} is {type(item).__name__}, not an object")

    currency = item.get("currency", functional_currency)
    if currency != functional_currency:
        raise ForeignCurrencyNoteError(
            f"line {number} is in {currency}, and this company keeps its books in "
            f"{functional_currency}. A manual note in another currency needs the "
            f"conversion and rounding convention, which is open (DNB-08)"
        )

    accounting_date = _date(item.get("accounting_date"), posting_date, number, "accounting_date")
    return ManualLine(
        account_id=_uuid(item.get("account_id"), number, "account_id"),
        debit=_amount(item.get("debit", 0), number, "debit"),
        credit=_amount(item.get("credit", 0), number, "credit"),
        accounting_date=accounting_date,
        document_date=_date(item.get("document_date"), accounting_date, number, "document_date"),
        currency=str(currency),
        description=_text(item.get("description"), number),
        dimensions=_dimensions(item.get("dimensions"), number),
    )


def _uuid(value: Any, number: int, field: str) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        raise ManualPayloadError(
            f"line {number}: {field} is {value!r}, which is not an identifier"
        ) from None


def _amount(value: Any, number: int, field: str) -> Decimal:
    """A decimal written exactly, or a refusal.

    **A float is refused rather than converted.** `0.1` is not a tenth in binary,
    and a ledger that accepted it would store the nearest representable number and
    balance by luck. JSON has no decimal type, so an amount travels as a string --
    which is also what keeps `payload` serialisable, since `json.dumps` cannot
    write a `Decimal` at all.
    """
    # `bool` is here with `float` because `bool` is an `int` in Python, so
    # `Decimal(True)` is a perfectly good 1 -- an amount arriving as `true` would
    # post a leu and nothing would object.
    if isinstance(value, bool | float):
        raise ManualPayloadError(
            f"line {number}: {field} is {value!r}. Amounts travel as strings; a "
            f"float is not exact, and an amount that is not exact is not an amount"
        )
    try:
        amount = Decimal(value) if isinstance(value, int | Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ManualPayloadError(f"line {number}: {field} is {value!r}, not a number") from None

    if not amount.is_finite():
        raise ManualPayloadError(f"line {number}: {field} is {value!r}, not a finite number")

    exponent = amount.as_tuple().exponent
    if isinstance(exponent, int) and -exponent > SCALE:
        raise ManualPayloadError(
            f"line {number}: {field} has more than {SCALE} decimals ({amount}). The "
            f"column would round it silently, and which way it rounds is an open "
            f"decision (DNB-08) -- so the value is refused, not altered"
        )
    return amount


def _date(value: Any, fallback: date, number: int, field: str) -> date:
    if value is None:
        return fallback
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        raise ManualPayloadError(
            f"line {number}: {field} is {value!r}, not a date in ISO form"
        ) from None


def _text(value: Any, number: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ManualPayloadError(f"line {number}: description is {type(value).__name__}, not text")
    return value


def _dimensions(value: Any, number: int) -> dict[str, uuid.UUID]:
    """The analytical values the user attached, keyed by ADR-029 name.

    Names, not columns: `partner`, `dim_1`. A name outside the closed vocabulary
    is refused **here**, at the payload, and not left to the ledger's own guard --
    which also exists, and is the barrier for a caller that skips this module.
    The difference is what it costs: refused here, nothing has happened; refused
    there, an event is recorded and a document number has been consumed, and a
    number consumed is a permanent gap in the register (ADR-022) for a note that
    never existed.
    """
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ManualPayloadError(
            f"line {number}: dimensions is {type(value).__name__}, not an object"
        )

    unknown = sorted(set(map(str, value)) - set(DIMENSION_KEYS))
    if unknown:
        raise ManualPayloadError(
            f"line {number}: {', '.join(unknown)} is not an analytical dimension. "
            f"The vocabulary is closed (ADR-029) and a name outside it would be "
            f"dropped, leaving a line that looks analysed without being it"
        )

    return {
        str(key): _uuid(item, number, f"dimensions.{key}")
        for key, item in value.items()
        if item is not None
    }


HANDLERS[HANDLER_REF] = record_manual_lines

register(
    EventType(
        name=EVENT_TYPE,
        #: Checked at emission, where a missing field is still the caller's bug.
        #: `description` is here rather than only in the parser for that reason.
        payload_fields=("lines", "description"),
        #: None, and that is the difference from every other treatment. A manual
        #: note names accounts directly; roles exist so that a *computed*
        #: treatment does not have to (ADR-036 section 5.1).
        account_roles=(),
        handlers=(HandlerVersion(implementation_ref=HANDLER_REF, valid_from=date.min),),
        description=(
            "A journal entry proposed line by line by a person. The engine "
            "validates and posts it; it derives nothing."
        ),
    )
)


# --- the service -------------------------------------------------------------


def post_manual_entry(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    accounting_date: date,
    functional_currency: str,
    note_id: uuid.UUID,
    payload: dict[str, Any],
    idempotency_key: str,
    actor_user_id: uuid.UUID,
    request_id: str,
    capability_snapshot: dict[str, Any],
    occurred_at: datetime | None = None,
) -> ManualEntryResult:
    """Record a manual note and post it, or refuse with a stable code.

    `functional_currency` is a **parameter, not a lookup**, for the reason R26
    gives for the capability profile: the currency a company keeps its books in
    lives on `platform.tenancy`, and no public service of that module exposes it
    today, so reading it here would be the `D6` import the rule is about. Making
    it explicit also makes it recorded -- the caller states which currency it
    believes it is posting in, and a mismatch with the line is refused rather than
    assumed away.

    `note_id` is the identifier of the note as a document (R13's fourth link).
    There is no table of manual notes at F1, so the caller allocates it -- which
    is also what makes a retry idempotent, since the same note keeps the same id.
    When notes become stored documents, this is the column that points at one.

    `capability_snapshot` is the profile as `platform.capabilities` writes it. It
    selects the treatment (R26) and is stored on the event, so that recalculating
    this period years later selects what today selected (R18).
    """
    treatment = selected_treatment(EVENT_TYPE, accounting_date, capability_snapshot)
    lines: tuple[ManualLine, ...] = treatment.handler(
        tenant_id=tenant_id,
        company_id=company_id,
        accounting_date=accounting_date,
        functional_currency=functional_currency,
        payload=payload,
    )
    if not all(isinstance(line, ManualLine) for line in lines):
        raise ManualPayloadError(
            f"the treatment registered for {EVENT_TYPE} returned something other "
            f"than manual lines; a registration selects an implementation, and "
            f"this one does not match the type it was selected for"
        )

    description = payload.get("description")
    if not isinstance(description, str) or not description.strip():
        raise ManualPayloadError(
            "a manual note needs a description. It is the only entry with no "
            "document behind it, so without one nothing says later what it was"
        )

    event, created = emit(
        tenant_id=tenant_id,
        company_id=company_id,
        event_type=EVENT_TYPE,
        source_module=SOURCE_MODULE,
        source_document_type=SOURCE_DOCUMENT_TYPE,
        source_document_id=note_id,
        occurred_at=occurred_at or datetime.now(UTC),
        accounting_date=accounting_date,
        idempotency_key=idempotency_key,
        payload=payload,
        capability_snapshot=capability_snapshot,
        actor_user_id=actor_user_id,
        request_id=request_id,
    )

    if not created:
        settled = entry_id_of_event(event.id)
        if settled is not None:
            return ManualEntryResult(event.id, settled, posted_now=False)
        if event.status == "posted":
            raise EventAlreadyPostedError(
                f"event {event.id} is marked posted and no entry of it is visible; "
                f"writing a second one would double an effect that cannot be undone"
            )
        # Emitted and never posted -- a previous attempt that failed after the
        # event landed. Finishing it is the point of `failed` not being terminal.

    try:
        with transaction.atomic():
            entry_id = _write(
                event_id=event.id,
                tenant_id=tenant_id,
                company_id=company_id,
                accounting_date=accounting_date,
                note_id=note_id,
                description=description,
                request_id=request_id,
                actor_user_id=actor_user_id,
                lines=lines,
                rule_ref=treatment.ref,
            )
    except (ApiError, NumberingError) as refusal:
        # The reason is written onto the event rather than only raised: an event
        # that failed to post is work somebody has to finish, and an exception in
        # a task disappears into a log. Whether the row survives is the caller's
        # transaction -- see the module docstring.
        mark_failed(event.id, code=refusal.code, detail={"event_type": EVENT_TYPE})
        raise

    mark_posted(event.id)
    return ManualEntryResult(event.id, entry_id, posted_now=True)


def _write(
    *,
    event_id: uuid.UUID,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    accounting_date: date,
    note_id: uuid.UUID,
    description: str,
    request_id: str,
    actor_user_id: uuid.UUID,
    lines: Sequence[ManualLine],
    rule_ref: str,
) -> uuid.UUID:
    """Judge the proposal and hand it to the ledger. Returns the entry's id.

    The order is the contract. `verify` refuses on the six invariants and returns
    the period, so nothing else resolves it a second time; the dimensions are
    checked next, because they are a property of the account and invariant 4 has
    just established that the accounts exist; the number is allocated last before
    the write, because allocation consumes one and a refusal after it would leave
    a permanent gap in the register for a note that never existed.
    """
    period_id = verify(
        ProposedPosting(
            tenant_id=tenant_id,
            company_id=company_id,
            accounting_date=accounting_date,
            accounting_event_id=event_id,
            origin=Origin(
                module=SOURCE_MODULE,
                document_type=SOURCE_DOCUMENT_TYPE,
                document_id=note_id,
            ),
            lines=tuple(
                ProposedLine(
                    tenant_id=tenant_id,
                    company_id=company_id,
                    accounting_date=line.accounting_date,
                    account_id=line.account_id,
                    debit=line.debit,
                    credit=line.credit,
                )
                for line in lines
            ),
        )
    )

    assert_dimensions_present(
        company_id,
        accounting_date,
        [LineDimensions(line.account_id, dict(line.dimensions)) for line in lines],
    )

    # The three versions the note stood on (ADR-048). A manual note computes
    # nothing, so the fiscal date it names is its own; the chart is the one its
    # accounts were read from, when the company has one.
    chart = chart_version_of(company_id)
    number = allocate(tenant_id, company_id, NUMBERING_DOCUMENT_TYPE, accounting_date)

    return post_entry(
        tenant_id=tenant_id,
        company_id=company_id,
        entry_number=number.formatted,
        accounting_date=accounting_date,
        period_id=period_id,
        accounting_event_id=event_id,
        description=description,
        request_id=request_id,
        posted_by_user_id=actor_user_id,
        rule_ref=rule_ref,
        fiscal_effective_date=accounting_date,
        chart_template_id=chart.template_id if chart is not None else None,
        lines=[
            LineToWrite(
                account_id=line.account_id,
                debit=line.debit,
                credit=line.credit,
                currency=line.currency,
                # The transaction is in the functional currency, so its own amount
                # is the same number and the rate is exactly 1 (ADR-039 section 3).
                # Not a conversion: the other side of the line is zero, so
                # `debit + credit` is the amount, and no rounding rule is involved.
                amount_currency=line.debit + line.credit,
                exchange_rate=Decimal(1),
                accounting_date=line.accounting_date,
                document_date=line.document_date,
                # At rate 1 there is no rate to have taken on a day. The column is
                # NOT NULL, so it carries the line's own date rather than a
                # borrowed one -- and the day a foreign-currency note becomes
                # possible, this is where the real rate date arrives.
                rate_date=line.accounting_date,
                description=line.description,
                dimensions=dict(line.dimensions),
            )
            for line in lines
        ],
    )
