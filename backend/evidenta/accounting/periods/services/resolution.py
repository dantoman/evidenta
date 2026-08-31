"""Which period a date falls in, and whether it accepts postings -- R12.

This is the primitive the Posting Engine calls. It exists before the engine on
purpose: the rule "posting into a closed period is refused" belongs to the
engine, not to the interface (Spec B section 6.3), and the engine will refuse by
calling ``assert_postable`` rather than by reimplementing the state machine at
the point of posting.

**What is deliberately not here: the second barrier.** Spec B section 6.3 asks
for a ``BEFORE INSERT`` trigger on ``journal_entry`` that reads the period's
state, because the 1C importer, data migrations and any direct ``INSERT`` bypass
the engine. That trigger belongs to F1.2.1, where the table it sits on is
created. Until then this module is the only refusal, and it can be bypassed --
which is stated here rather than left for someone to discover.

**Which date.** ``accounting_date`` decides the period, never ``document_date``:
a document dated 28 March that arrives on 5 April, with March closed, posts in
April (ADR-039 section 9). The two dates both live on the journal line for
exactly that reason.
"""

from __future__ import annotations

import uuid
from datetime import date

from evidenta.accounting.periods.errors import (
    CompanyNotPostableError,
    PeriodLockedError,
    PeriodNotFoundError,
    PeriodNotOpenError,
)
from evidenta.accounting.periods.models import Period, PeriodStatus
from evidenta.platform.tenancy.services.companies import is_open_for_posting


def period_for(company_id: uuid.UUID, accounting_date: date) -> Period:
    """The period covering ``accounting_date``, or a loud refusal.

    No period is not the same as a closed period, and the codes differ. A hole in
    the calendar means the exercise was never opened -- answering it by creating
    a period on demand would let the first posting of an unopened year build its
    own container, and nobody would ever review the date that opened it.
    """
    period = Period.objects.filter(
        company_id=company_id, start_date__lte=accounting_date, end_date__gte=accounting_date
    ).first()
    if period is None:
        raise PeriodNotFoundError(
            f"no period covers {accounting_date} for company {company_id}; "
            f"the exercise containing that date has not been opened"
        )
    return period


def assert_postable(company_id: uuid.UUID, accounting_date: date) -> Period:
    """Return the period, or refuse because it does not accept postings.

    One code for ``closed`` and ``locked`` would be simpler and wrong: reopening
    answers the first and never answers the second, so a caller that cannot tell
    them apart cannot tell a user what to do next.
    """
    # The company before the period, and the order is the message: a closed
    # company has no open period anywhere, so asking about the calendar first
    # would answer a question nobody asked. Until ADR-083 this check did not
    # exist and `company.status` was read by nothing -- the value was there, the
    # rule was not.
    if not is_open_for_posting(company_id):
        raise CompanyNotPostableError(
            f"company {company_id} does not accept postings; "
            f"its books stay readable, but nothing new is written into them"
        )

    period = period_for(company_id, accounting_date)
    if period.status == PeriodStatus.LOCKED:
        raise PeriodLockedError(
            f"period {period.start_date:%Y-%m} is locked; {accounting_date} is corrected "
            f"with a reversal posted in the open period, not by reopening it"
        )
    if period.status != PeriodStatus.OPEN:
        raise PeriodNotOpenError(
            f"period {period.start_date:%Y-%m} is {period.status}; "
            f"{accounting_date} cannot be posted into it"
        )
    return period
