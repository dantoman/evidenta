"""What stands between a month and its closing -- G1, computed on the server.

The engine refuses a closing on exactly one ground, the class-8 invariant
(`lifecycle.assert_management_accounts_settled`, ADR-039 section 10.1). Everything
else here is a **warning**: work the closing would strand rather than a rule it
breaks. A validated invoice that has not reached the ledger is a numbered legal
document whose posting will be refused the moment the month closes (`R12`), and
it lands in the blocked queue rather than in the register -- nothing in the act
forbids closing over it, and an accountant who knows the invoice is a duplicate
about to be cancelled may close anyway. So each check says whether it *blocks*,
and only the engine's own refusal does.

**Every count is the owning module's.** Documents are `platform.documents`',
draft entries the ledger's, unposted events the event store's -- each asked
through the module's public service and never through its models (`D6`), the
way the panel's overview reads the same tables. Class 8 is read the way the
closing itself reads it: through the trial balance, up to the period's last day.

**What is not counted, and why it is said rather than hidden.** A payroll run
approved and not posted lives in `operations.payroll`, which `accounting` may
not import (`D2`); its posting, once emitted, is an accounting event and *is*
counted under `events_not_posted` if it failed -- but a run never submitted is
invisible from here, and the screen says so. Unbound roles and an unmatched bank
statement (`13-lista-de-deblocare`, G1) wait for the modules that produce them.

**The window is the period's.** Which month a document belongs to is decided by
``accounting_date`` and never by ``document_date`` (ADR-039 section 9): an
invoice dated 28 March that arrives on 5 April with March closed is April's work,
and March's checks do not count it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from evidenta.accounting.events.services.lifecycle import unposted_between
from evidenta.accounting.ledger.services.drafts import draft_entries_between
from evidenta.accounting.periods.models import Period
from evidenta.accounting.periods.services.lifecycle import (
    period_in_context,
    unsettled_management_accounts,
)
from evidenta.platform.documents.registry import registered
from evidenta.platform.documents.services.lifecycle import unposted_work

#: The check codes -- stable, like error codes (`C10`): the screen keys its
#: labels on them, so renaming one is a breaking change of the same kind.
CHECK_DOCUMENTS_CONFIRMED = "documents_confirmed_not_posted"
CHECK_DOCUMENTS_DRAFT = "documents_draft"
CHECK_ENTRIES_DRAFT = "journal_entries_draft"
CHECK_EVENTS_UNPOSTED = "events_not_posted"
CHECK_MANAGEMENT_ACCOUNTS = "management_accounts_unsettled"


@dataclass(frozen=True, slots=True)
class ClosingCheck:
    """One thing looked at before the month closes.

    ``blocking`` is the engine's word, not the screen's: true only where
    `close_period` would refuse. A screen may still ask before closing over a
    warning; it may not close over a blocker, and the server would not let it.
    """

    code: str
    count: int
    blocking: bool


def closing_checks(period_id: uuid.UUID) -> tuple[ClosingCheck, ...]:
    """The checks for one period, in a fixed order, every one present.

    Present with a zero rather than absent: a check that disappears when it has
    nothing to say looks, on the screen, like a check nobody ran.
    """
    period = period_in_context(period_id)
    return (
        *_document_checks(period),
        ClosingCheck(
            code=CHECK_ENTRIES_DRAFT,
            count=draft_entries_between(period.company_id, period.start_date, period.end_date),
            blocking=False,
        ),
        ClosingCheck(
            code=CHECK_EVENTS_UNPOSTED,
            count=unposted_between(period.company_id, period.start_date, period.end_date),
            blocking=False,
        ),
        ClosingCheck(
            code=CHECK_MANAGEMENT_ACCOUNTS,
            count=len(unsettled_management_accounts(period)),
            blocking=True,
        ),
    )


def _document_checks(period: Period) -> tuple[ClosingCheck, ClosingCheck]:
    """Every registered document type, across every owning module.

    The panel asks per family; the closing asks for the month, and a family
    with no document in it contributes nothing. The registry's list rather than
    one spelled here: which types exist is the modules' vocabulary.
    """
    types = [spec.code for spec in registered()]
    work = unposted_work(period.company_id, types, start=period.start_date, end=period.end_date)
    confirmed = sum(row.confirmed for row in work)
    draft = sum(row.draft for row in work)
    return (
        ClosingCheck(code=CHECK_DOCUMENTS_CONFIRMED, count=confirmed, blocking=False),
        ClosingCheck(code=CHECK_DOCUMENTS_DRAFT, count=draft, blocking=False),
    )
