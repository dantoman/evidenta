"""Closing a month and closing an exercise -- F1.5.4, ADR-039 section 10, ADR-050.

Two event types, not three (ADR-039 section 10):

    period.month_closed   the month is locked and the class-8 invariant is
                          validated; nothing is posted
    period.year_closed    the result accounts are closed through the engine, in
                          the order ADR-050 section 3.2 fixes

ADR-039 wrote them `period.month.closed` and `period.year.closed`, before the
registry existed. The registry enforces the form Spec B section 1.4 fixes --
`<domain>.<action>`, two segments, snake_case -- and refuses a third segment, so
the names registered are the two above. The ADR's names are the same events.

**The month.** Closing a month posts nothing. The management accounts (clasa 8)
are settled through the ordinary postings of the documents as cost flows, so at
the reporting date they have a zero balance -- a *validation*, not a posting
(ADR-039 section 10.1). The check lives on the period primitive itself
(`periods.services.lifecycle.close_period`), so no path closes a month around it;
this service is the door that also records the event, so that the vocabulary of
what happened to the company's books is complete (`R13`: the closing is an event
somebody can point at).

**The exercise.** The chain is one posting, dated the last day of the exercise,
in its last period, and it is the form of the act, not a choice:

    1. classes 6 and 7 to 351, **without 731**
    3. 731 to 351
    4. 351 to 333

Step 2 of ADR-050 -- recording the income tax on 731 -- is the accountant's (or
the tax module's) posting **before** the year is closed: its amount is a fiscal
calculation over the year's revenues and expenses, not a function of the ledger
the chain reads. The chain closes 731 as its own correspondence, so the profit
before tax stays legible in the entry's formulas and in the statement -- the
reason the owner gave for keeping 731 apart. Step 5 -- the balance-sheet reform,
334 settled and 333 to 332 -- is **not** here: the act names the moment
("la reformarea bilanţului") and never defines it (`OD-22` research, section 4);
which event carries it is `OD-73`, and a posting on a moment nobody has fixed
would be a decision taken in code.

**The handler is pure** (ADR-036 section 5.1). It reads the balances from the
event's payload and returns formulas; it does not read the ledger. The *service*
reads the ledger -- through the trial balance, the same aggregation the report
uses -- and writes what it read into the payload, so the event says what the
closing stood on and a recalculation years later closes the same numbers (R18).

**Roles, not accounts** (ADR-036 section 5.1, ADR-050 section 3.1). 351, 731 and
333 are `REZULTAT_FINANCIAR_TOTAL`, `CHELTUIALA_IMPOZIT_VENIT` and
`PROFIT_NET_PERIOADA`, resolved for the company at the closing date and written
into the payload as the accounts they resolved to. The class-6 and class-7
accounts are the company's own, from its chart, selected by the first character
of the code -- the class the norm speaks of.

**No amount is computed.** Every formula carries a sum the ledger already holds,
to the last of its four decimals; nothing is rounded, because nothing is derived.

**The last period must be open.** The chain is a posting, and R12 admits no
posting into a closed period. A December closed for monthly reporting is reopened
with its reason before the year is closed, and the audit shows it -- the honest
alternative to an exception in the engine for "closing entries", which is a
decision the owner has not taken.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.db import transaction

from evidenta.accounting.coa.services.accounts import names_for
from evidenta.accounting.events.registry import (
    HANDLERS,
    EventType,
    HandlerVersion,
    register,
)
from evidenta.accounting.events.services.emission import emit
from evidenta.accounting.events.services.lifecycle import mark_failed, mark_posted
from evidenta.accounting.ledger.services.trial_balance import trial_balance
from evidenta.accounting.ledger.services.writing import entry_id_of_event
from evidenta.accounting.periods.errors import (
    FiscalYearClosedError,
    LastPeriodNotOpenError,
    PeriodsMissingError,
    PeriodsStillOpenError,
    ResultAccountsCarryOpeningBalanceError,
)
from evidenta.accounting.periods.services.lifecycle import (
    close_fiscal_year,
    close_period,
    exercise_with_periods,
)
from evidenta.accounting.posting.formula import Formula
from evidenta.accounting.posting.invariants import Origin, PostingRefusedError
from evidenta.accounting.posting.resolution import selected_treatment
from evidenta.accounting.posting.services.formulas import post_formulas
from evidenta.accounting.slots.services.binding import resolve_role
from evidenta.platform.api.errors import ApiError
from evidenta.platform.numbering.services.allocation import NumberingError

EVENT_MONTH = "period.month_closed"
EVENT_YEAR = "period.year_closed"

#: Keys into `HANDLERS` (ADR-038 section 4), never importable paths.
HANDLER_MONTH = "period.month_closed.v1"
HANDLER_YEAR = "period.year_closed.v1"

#: `accounting_event.source_module`, as the string the database validates.
SOURCE_MODULE = "periods"

#: The chain's slots (ADR-050 section 3.1). Names from the catalogue; the
#: accounts they mean are the company's, at the closing date.
ROLE_TOTAL = "REZULTAT_FINANCIAR_TOTAL"
ROLE_TAX = "CHELTUIALA_IMPOZIT_VENIT"
ROLE_NET = "PROFIT_NET_PERIOADA"

#: The classes the chain closes, by the chart's structure: the first character of
#: the code. `account_class` says which statement a balance lands in; the class is
#: what the act closes.
RESULT_CLASSES = ("6", "7")

MDL_RATE = Decimal(1)


class ClosingPayloadError(PostingRefusedError):
    """The payload is not what the closing handler was registered to read.

    A bug in the service that emitted it, which is on the stack -- refused rather
    than posted around.
    """

    code = "posting.closing_payload_malformed"
    status = 400


@dataclass(frozen=True, slots=True)
class MonthClosingResult:
    period_id: uuid.UUID
    accounting_event_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class YearClosingResult:
    fiscal_year_id: uuid.UUID
    accounting_event_id: uuid.UUID
    #: None when the exercise had nothing to close: an event, no entry.
    journal_entry_id: uuid.UUID | None
    formulas: int
    periods_locked: int


# --- the handlers, pure -----------------------------------------------------------


def record_month_closed(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    accounting_date: date,
    functional_currency: str,
    payload: Mapping[str, Any],
) -> tuple[Formula, ...]:
    """The month's closing produces no lines. Registered so that it is selected
    like every other treatment, and so that the vocabulary is closed on it."""
    del tenant_id, company_id, accounting_date, functional_currency, payload
    return ()


def close_result_accounts(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    accounting_date: date,
    functional_currency: str,
    payload: Mapping[str, Any],
) -> tuple[Formula, ...]:
    """The chain of ADR-050 section 3.2, steps 1, 3 and 4, from the payload's balances.

    Signs: a balance is debit-positive. An account with a debit balance (an
    expense, ordinarily) closes as `Dt 351 / Ct account`; a credit balance (a
    revenue) as `Dt account / Ct 351`. What 351 then holds is the sum of those
    balances, and it leaves to 333 in the direction that makes 351 zero: a credit
    balance is a profit (`Dt 351 / Ct 333`), a debit balance a loss
    (`Dt 333 / Ct 351`).
    """
    del tenant_id, company_id
    roles = _mapping(payload, "role_accounts")
    try:
        total = uuid.UUID(str(roles[ROLE_TOTAL]))
        net = uuid.UUID(str(roles[ROLE_NET]))
    except (KeyError, ValueError):
        raise ClosingPayloadError(
            f"the payload names no account for {ROLE_TOTAL} or {ROLE_NET}; the "
            f"service resolves the roles and writes them, so their absence is its bug"
        ) from None
    tax_code = str(payload.get("tax_account_code") or "")
    balances = payload.get("balances")
    if not isinstance(balances, list):
        raise ClosingPayloadError("the payload carries `balances`, a list of account balances")

    def formula(debit: uuid.UUID, credit: uuid.UUID, amount: Decimal, text: str) -> Formula:
        return Formula(
            debit_account_id=debit,
            credit_account_id=credit,
            amount=amount,
            currency=functional_currency,
            amount_currency=amount,
            exchange_rate=MDL_RATE,
            rate_date=accounting_date,
            document_date=accounting_date,
            description=text,
        )

    def sweep(row: Mapping[str, Any], text: str) -> Formula | None:
        account = uuid.UUID(str(row["account_id"]))
        amount = Decimal(str(row["balance"]))
        if amount == 0:
            return None
        if amount > 0:
            return formula(total, account, amount, text)
        return formula(account, total, -amount, text)

    results: list[Formula] = []
    tax: list[Formula] = []
    swept = Decimal(0)
    for row in balances:
        if not isinstance(row, Mapping):
            raise ClosingPayloadError(
                "each balance is an object with account_id, account_code, balance"
            )
        code = str(row.get("account_code", ""))
        target = tax if tax_code and code.startswith(tax_code) else results
        text = (
            "Închiderea cheltuielilor privind impozitul pe venit"
            if target is tax
            else "Închiderea conturilor de venituri și cheltuieli"
        )
        item = sweep(row, text)
        if item is not None:
            target.append(item)
            swept += Decimal(str(row["balance"]))

    chain = [*results, *tax]
    if swept < 0:
        chain.append(formula(total, net, -swept, "Profit net al perioadei de gestiune"))
    elif swept > 0:
        chain.append(formula(net, total, swept, "Pierdere netă a perioadei de gestiune"))
    return tuple(chain)


def _mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise ClosingPayloadError(f"the payload carries `{key}` as an object")
    return value


HANDLERS[HANDLER_MONTH] = record_month_closed
HANDLERS[HANDLER_YEAR] = close_result_accounts

register(
    EventType(
        name=EVENT_MONTH,
        payload_fields=("period_id", "start_date", "end_date"),
        account_roles=(),
        handlers=(HandlerVersion(implementation_ref=HANDLER_MONTH, valid_from=date.min),),
        description=(
            "A month closed: postings refused from now on, the management accounts "
            "validated at zero. Records nothing in the ledger."
        ),
    )
)

register(
    EventType(
        name=EVENT_YEAR,
        payload_fields=("fiscal_year_id", "balances", "role_accounts", "tax_account_code"),
        account_roles=(ROLE_TOTAL, ROLE_TAX, ROLE_NET),
        handlers=(HandlerVersion(implementation_ref=HANDLER_YEAR, valid_from=date.min),),
        description=(
            "An exercise closed: the result accounts swept to the total result, "
            "the income tax expense apart, the net result to the period's profit."
        ),
    )
)


# --- the services ------------------------------------------------------------------


@transaction.atomic
def close_month(
    period_id: uuid.UUID,
    *,
    actor_user_id: uuid.UUID,
    request_id: str,
    capability_snapshot: dict[str, Any],
    occurred_at: datetime | None = None,
) -> MonthClosingResult:
    """Close the month and record that it closed. Posts nothing.

    The state change and the class-8 check are the primitive's; the event is
    this door's. One transaction: a month is not closed without its event, and no
    event says a month closed that did not.
    """
    period = close_period(period_id)
    event, _ = emit(
        tenant_id=period.tenant_id,
        company_id=period.company_id,
        event_type=EVENT_MONTH,
        source_module=SOURCE_MODULE,
        source_document_type="period",
        source_document_id=period.id,
        occurred_at=occurred_at or datetime.now(UTC),
        accounting_date=period.end_date,
        # A month reopened and closed again is a second closing, not a replay of
        # the first: the count is part of the key.
        idempotency_key=f"{EVENT_MONTH}:{period.id}:{period.reopened_count}",
        payload={
            "period_id": str(period.id),
            "period_no": period.period_no,
            "start_date": period.start_date.isoformat(),
            "end_date": period.end_date.isoformat(),
        },
        capability_snapshot=capability_snapshot,
        actor_user_id=actor_user_id,
        request_id=request_id,
    )
    treatment = selected_treatment(EVENT_MONTH, period.end_date, capability_snapshot)
    produced = treatment.handler(
        tenant_id=period.tenant_id,
        company_id=period.company_id,
        accounting_date=period.end_date,
        functional_currency="",
        payload=event.payload,
    )
    if produced:
        raise ClosingPayloadError(
            f"the treatment registered for {EVENT_MONTH} produced formulas; closing a "
            f"month posts nothing (ADR-039 section 10)"
        )
    mark_posted(event.id)
    return MonthClosingResult(period_id=period.id, accounting_event_id=event.id)


@transaction.atomic
def close_year(
    fiscal_year_id: uuid.UUID,
    *,
    functional_currency: str,
    actor_user_id: uuid.UUID,
    request_id: str,
    capability_snapshot: dict[str, Any],
    occurred_at: datetime | None = None,
) -> YearClosingResult:
    """Post the closing chain, close the last month, close the exercise, lock it.

    One transaction, in that order. The chain is dated the exercise's last day
    and lands in its last period, which must still be open (R12); every other
    period must already be closed. After the chain the last month closes -- with
    its class-8 check -- and the exercise closes, which locks every period.

    ``functional_currency`` is a parameter for the reason `services.manual`
    gives: the caller states the currency it believes the books are kept in.
    """
    year, periods = exercise_with_periods(fiscal_year_id)
    if year.status != "open":
        raise FiscalYearClosedError(f"exercise {year.code} is already closed")
    if not periods:
        raise PeriodsMissingError(
            f"exercise {year.code} has no periods; an exercise is opened with its months "
            f"(`open_fiscal_year`), and one without them has nothing to close"
        )
    # The months have to tile the exercise: a gap would be closed over silently,
    # and the chain would declare an exercise finished with a month nobody kept.
    # Unreachable through `open_fiscal_year`, which writes every month at once;
    # asserted anyway, because an import path that skips it would not say so.
    expected = year.start_date
    for period in periods:
        if period.start_date != expected:
            raise PeriodsMissingError(
                f"exercise {year.code} has a gap before {period.start_date:%Y-%m}: its "
                f"months do not cover the exercise, so it cannot be closed as a whole"
            )
        expected = period.end_date + timedelta(days=1)
    if expected != year.end_date + timedelta(days=1):
        raise PeriodsMissingError(
            f"exercise {year.code} ends {year.end_date:%d.%m.%Y} but its last month ends "
            f"{periods[-1].end_date:%d.%m.%Y}; the months do not cover the exercise"
        )
    last = periods[-1]
    still_open = [p.period_no for p in periods[:-1] if p.status == "open"]
    if still_open:
        numbers = ", ".join(str(n) for n in still_open)
        raise PeriodsStillOpenError(
            f"exercise {year.code} still has open periods before the last ({numbers}); "
            f"each month closes before the year does"
        )
    if last.status != "open":
        raise LastPeriodNotOpenError(
            f"period {last.start_date:%Y-%m} is {last.status}; the closing chain is a "
            f"posting dated {year.end_date:%d.%m.%Y} and needs that month open -- reopen "
            f"it with a reason, then close the year"
        )

    balances = trial_balance(year.company_id, year.start_date, year.end_date)
    result_rows = [row for row in balances.rows if row.account_code[:1] in RESULT_CLASSES]
    carried = [(row.account_code, row.opening) for row in result_rows if row.opening != 0]
    if carried:
        listed = ", ".join(f"{code} ({opening})" for code, opening in carried)
        raise ResultAccountsCarryOpeningBalanceError(
            f"result accounts enter exercise {year.code} with a balance -- {listed}. The "
            f"previous exercise was not closed here; closing this one would sweep its "
            f"result into this year's"
        )

    role_accounts = {
        role: resolve_role(year.company_id, role, year.end_date)
        for role in (ROLE_TOTAL, ROLE_TAX, ROLE_NET)
    }
    tax_naming = names_for(year.company_id, [role_accounts[ROLE_TAX]])
    tax_code = tax_naming.get(role_accounts[ROLE_TAX], ("", ""))[0]

    payload: dict[str, Any] = {
        "fiscal_year_id": str(year.id),
        "code": year.code,
        "start_date": year.start_date.isoformat(),
        "end_date": year.end_date.isoformat(),
        "balances": [
            {
                "account_id": str(row.account_id),
                "account_code": row.account_code,
                "balance": str(row.closing),
            }
            for row in result_rows
            if row.closing != 0
        ],
        "role_accounts": {role: str(account) for role, account in role_accounts.items()},
        "tax_account_code": tax_code,
    }

    event, created = emit(
        tenant_id=year.tenant_id,
        company_id=year.company_id,
        event_type=EVENT_YEAR,
        source_module=SOURCE_MODULE,
        source_document_type="fiscal_year",
        source_document_id=year.id,
        occurred_at=occurred_at or datetime.now(UTC),
        accounting_date=year.end_date,
        idempotency_key=f"{EVENT_YEAR}:{year.id}",
        payload=payload,
        capability_snapshot=capability_snapshot,
        actor_user_id=actor_user_id,
        request_id=request_id,
    )

    entry_id: uuid.UUID | None = None
    formulas_posted = 0
    settled = entry_id_of_event(event.id) if not created else None
    if settled is not None:
        entry_id = settled
    elif not created and event.status == "posted":
        # Posted with no entry: an exercise that had nothing to close. Legitimate,
        # and finished -- the remaining steps below are what a replay completes.
        pass
    else:
        treatment = selected_treatment(EVENT_YEAR, year.end_date, capability_snapshot)
        produced = treatment.handler(
            tenant_id=year.tenant_id,
            company_id=year.company_id,
            accounting_date=year.end_date,
            functional_currency=functional_currency,
            payload=event.payload,
        )
        if not all(isinstance(item, Formula) for item in produced):
            raise ClosingPayloadError(
                f"the treatment registered for {EVENT_YEAR} returned something other than formulas"
            )
        formulas: Sequence[Formula] = tuple(produced)
        if formulas:
            try:
                result = post_formulas(
                    tenant_id=year.tenant_id,
                    company_id=year.company_id,
                    accounting_date=year.end_date,
                    functional_currency=functional_currency,
                    accounting_event_id=event.id,
                    origin=Origin(
                        module=SOURCE_MODULE, document_type="fiscal_year", document_id=year.id
                    ),
                    rule_ref=treatment.ref,
                    description=f"Închiderea exercițiului {year.code}",
                    request_id=request_id,
                    actor_user_id=actor_user_id,
                    formulas=formulas,
                    entry_type="closing",
                )
            except (ApiError, NumberingError) as refusal:
                mark_failed(event.id, code=refusal.code, detail={"event_type": EVENT_YEAR})
                raise
            entry_id = result.journal_entry_id
            formulas_posted = result.formulas
        mark_posted(event.id)

    close_month(
        last.id,
        actor_user_id=actor_user_id,
        request_id=request_id,
        capability_snapshot=capability_snapshot,
        occurred_at=occurred_at,
    )
    closed = close_fiscal_year(year.id)
    locked = sum(1 for _ in periods)
    del closed
    return YearClosingResult(
        fiscal_year_id=year.id,
        accounting_event_id=event.id,
        journal_entry_id=entry_id,
        formulas=formulas_posted,
        periods_locked=locked,
    )
