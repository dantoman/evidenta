"""Every way an opening balance batch is refused, with a stable code -- C10.

One family, ``OpeningBalanceError``, so a caller that only has to say "this batch
did not load" catches the base while one that has to tell the accountant what to
fix branches on ``code``. The distinction matters more here than almost anywhere
else in the product: a batch is refused *whole* (Spec B section 8.2 cites V2
section 14, "refuz de import partial"), so the code is the only thing standing
between "your trial balance does not balance" and "row 4 700 names an account
that was closed in 2024".

**These are not `PostingRefusedError`.** That family is the engine's answer about
a proposal it has already been handed; these are the batch's answer about itself,
raised before any proposal exists. The two do meet: ``validate_batch`` calls the
engine's own dimension check rather than reimplementing it, so a batch can also
be refused with ``posting.account_not_postable`` or
``posting.missing_required_dimension``. That is deliberate -- one implementation
of each rule, wherever the caller reaches it from.
"""

from __future__ import annotations

from evidenta.platform.api.errors import ApiError


class OpeningBalanceError(ApiError):
    """Base of every refusal this module issues."""

    code = "opening.refused"
    status = 409


class BatchNotFoundError(OpeningBalanceError):
    """No batch with that id is visible in this context.

    "Not visible" rather than "does not exist": RLS has already narrowed the
    table, so another tenant's batch and a typo produce the same answer, which is
    the only one that does not leak the existence of the other row (IZ-04).
    """

    code = "opening.batch_not_found"
    status = 404


class BatchNotDraftError(OpeningBalanceError):
    """Lines were added or changed on a batch that has left ``draft``.

    The database refuses this too, with a trigger on all six line tables, and
    that is the barrier that holds against the 1C importer and any data
    migration. What is added here is a code and the batch's actual state.
    """

    code = "opening.batch_not_draft"


class IllegalBatchTransitionError(OpeningBalanceError):
    """The transition is not in the matrix.

    Notably ``posted -> anything``. Correcting a posted batch is a reversal and a
    new batch (Spec B section 8.3), never a status walked backwards: the entry it
    produced is in an append-only ledger and no status change can take it back.
    """

    code = "opening.illegal_batch_transition"


class EmptyGlSetError(OpeningBalanceError):
    """A batch with no GL rows.

    The GL set is the trial balance; the other five are decompositions of it. A
    batch without it has nothing to post and nothing to check the rest against --
    including a batch carrying only payroll cumulatives, which is refused here
    rather than posted as an entry with no lines. See
    ``services.posting`` for why that case is a reported gap and not a decision.
    """

    code = "opening.empty_gl_set"


class GlOutOfBalanceError(OpeningBalanceError):
    """Spec B section 8.2, first bullet: the trial balance does not balance.

    Refused before anything is written, so the accountant fixes the source rather
    than the ledger. Reconciling to zero is the condition of the import, not its
    goal (V2 section 14).
    """

    code = "opening.gl_out_of_balance"


class AnalyticalMismatchError(OpeningBalanceError):
    """Spec B section 8.2, second bullet: detail does not equal its control total.

    The one check that cannot be delegated to the engine, because the engine only
    ever sees the lines that were finally proposed -- by then the analytical rows
    *are* the balance, and there is nothing left to compare them with.
    """

    code = "opening.analytical_mismatch"


class AccountMissingFromGlError(OpeningBalanceError):
    """An analytical row names an account the GL set does not carry.

    Not the same defect as a mismatch, and telling them apart is the point: a
    mismatch means one of two numbers is wrong, this means the trial balance is
    incomplete. Loading it anyway would post a receivable with no synthetic
    balance behind it, and the difference would surface as an unexplained figure
    in the first balance sheet.
    """

    code = "opening.account_missing_from_gl"


class CounterpartInGlError(OpeningBalanceError):
    """The technical opening account appears in the GL set itself.

    Then its balance after posting is not zero, and the completeness test of Spec
    B section 8.3 stops being a test. The technical account is the other side of
    every opening line, never one of them.
    """

    code = "opening.counterpart_in_gl"


class ForeignCurrencyBalanceError(OpeningBalanceError):
    """A balance in a currency other than the company's functional one.

    Refused rather than converted, for the reason the manual note gives: the
    conversion needs a rounding rule (`DNB-08`, open, ADR-037 still `Propus`), and
    storing four numbers whose relation nothing checked would put a line in an
    append-only ledger that cannot be reconciled afterwards.

    Narrow and removable: the currency and the amount are already stored on the
    row, so the day the convention is decided this becomes a handler version with
    a later ``valid_from`` and the batches already posted stay exactly as they
    are.
    """

    code = "opening.foreign_currency_unsupported"


class StartPeriodFixedError(OpeningBalanceError):
    """The company already posted its opening balances as of another date.

    ADR-039 section 11: the start period of a company is chosen once, with an
    explicit warning, and does not move afterwards. A trigger refuses it in the
    database as well -- the importer and any data migration bypass this service,
    and moving the start of the books is exactly the kind of change that arrives
    through one of them.
    """

    code = "opening.start_period_fixed"


class BatchAlreadyPostedError(OpeningBalanceError):
    """The batch is already in the ledger, under a different idempotency key.

    Distinct from a replay, which returns the first result unchanged. This is a
    second posting attempt on a batch that has an entry -- refused, because there
    is no UPDATE in the ledger to take the double effect back (R10).
    """

    code = "opening.batch_already_posted"


class EntryMissingForPostedEventError(OpeningBalanceError):
    """The event says it posted, and no entry of it is visible.

    Not a state this module can produce -- the event is marked only after the
    write, in the same transaction. Reaching it means the two tables disagree,
    and writing a second entry would double an effect the ledger cannot undo.
    """

    code = "opening.entry_missing_for_posted_event"
