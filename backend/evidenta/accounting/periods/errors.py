"""Refusals from the period module, each with a stable code -- C10.

Every one of these is a refusal a caller branches on, and two of them are the
reason the module exists: posting into a period that is not open, and reopening
one that is locked. They are separate codes because the remedies differ -- the
first can be answered by reopening the period, the second never can.

They subclass ``ApiError`` so the middleware renders the code even when they
surface through a plain view.
"""

from __future__ import annotations

from evidenta.platform.api.errors import ApiError


class FiscalYearOverlapsError(ApiError):
    """Two exercises covering the same day is two answers to "which period".

    The database refuses it as well, with an exclusion constraint. This code
    exists so the caller gets a stable answer instead of an integrity error.
    """

    code = "periods.fiscal_year_overlaps"
    status = 409


class FiscalYearCodeTakenError(ApiError):
    code = "periods.fiscal_year_code_taken"
    status = 409


class FiscalYearNotFoundError(ApiError):
    """Not found, or not visible in this context -- deliberately one code.

    Distinguishing them would tell a caller that an id exists in another tenant
    (IZ-04): an inaccessible row is absent, never forbidden.
    """

    code = "periods.fiscal_year_not_found"
    status = 404


class FiscalYearClosedError(ApiError):
    """The exercise is closed, so nothing inside it moves again."""

    code = "periods.fiscal_year_closed"
    status = 409


class PeriodsStillOpenError(ApiError):
    """An exercise cannot close over periods that are still open.

    Closing the exercise locks its periods irreversibly; doing that to a period
    still accepting postings would lock work in progress out of its own month.
    """

    code = "periods.periods_still_open"
    status = 409


class InvalidFiscalYearWindowError(ApiError):
    """The exercise is not whole calendar months, or is longer than twelve.

    Both come from ADR-039 section 6: the accounting period is strictly monthly,
    so an exercise that starts mid-month cannot be divided into periods at all,
    and art. 24 knows no exercise longer than twelve months.
    """

    code = "periods.invalid_fiscal_year_window"
    status = 400


class CompanyNotVisibleError(ApiError):
    code = "periods.company_not_visible"
    status = 404


class PeriodNotFoundError(ApiError):
    """No period covers this date -- a hole in the calendar, not a refusal.

    Loud on purpose. The alternative, inventing a period on demand, would make
    the first posting of an unopened exercise create its own container, and the
    date that opened it would never be reviewed by anyone.
    """

    code = "periods.period_not_found"
    status = 404


class PeriodNotOpenError(ApiError):
    """The period exists and does not accept postings -- R12.

    Raised by the engine-facing primitive, never by the interface. The interface
    may also check, to say it earlier and more kindly; that is not where the rule
    lives.
    """

    code = "periods.period_not_open"
    status = 409


class PeriodLockedError(ApiError):
    """``locked`` is terminal. Correction goes through a reversal in an open period."""

    code = "periods.period_locked"
    status = 409


class VatPeriodNotFoundError(ApiError):
    """No VAT fiscal period covers this date.

    Distinct from ``PeriodNotFoundError`` and never a substitute for it: a
    company can have an open accounting period for March and no VAT period at
    all, because it is not registered. Answering the second question with the
    first code would tell a caller to open an exercise that is already open.
    """

    code = "periods.vat_period_not_found"
    status = 404


class VatPeriodOverlapsError(ApiError):
    """Two VAT fiscal periods over one day is two declarations for one day.

    Also raised when closing a registration would swallow periods that already
    exist for the months in between -- those months already have declarations
    attached to their own period, and merging them is not a silent operation.
    """

    code = "periods.vat_period_overlaps"
    status = 409


class InvalidVatPeriodWindowError(ApiError):
    """The window is not whole calendar months, or it ends before it starts.

    Codul fiscal art. 114 para. (1) makes the VAT fiscal period the calendar
    month, and para. (2) -- the only irregular case it names -- still begins on
    the first day of a month and ends on the last day of one.
    """

    code = "periods.invalid_vat_period_window"
    status = 400


class VatRegistrationAlreadyClosedError(ApiError):
    """A final period already covers these months.

    Its own code rather than ``VatPeriodOverlapsError``: the remedies differ.
    An overlap is fixed by naming different months; this one means the
    cancellation is already recorded, and recording it twice would move the end
    of the last fiscal period a taxpayer already declared on.
    """

    code = "periods.vat_registration_already_closed"
    status = 409


class ManagementAccountsNotSettledError(ApiError):
    """A class-8 account still carries a balance at the end of the period.

    ADR-039 section 10.1: the management accounts (clasa 8) have a zero balance
    at the reporting date. Settling them is part of the continuous flow of cost,
    through the ordinary postings of the documents, so at closing this is a
    **validation, not a posting** -- the month does not close until somebody
    has settled what the chart says must already be settled.
    """

    code = "periods.class8_not_settled"
    status = 409


class ResultAccountsCarryOpeningBalanceError(ApiError):
    """A class-6 or class-7 account enters the exercise with a balance.

    Result accounts start every exercise at zero: the previous year's closing
    swept them into 351. A balance carried in from before the exercise means
    the previous year was never closed in this system (or something was written
    past the engine), and closing this year would sweep last year's result into
    this year's -- silently. Refused, so the gap is fixed where it is.
    """

    code = "periods.result_accounts_not_at_zero"
    status = 409


class LastPeriodNotOpenError(ApiError):
    """The closing chain is dated the last day of the exercise, in its last period.

    Every other period must already be closed; the last one must still be open,
    because the chain is a posting and R12 admits no posting into a closed
    period. A last period closed for monthly reporting is reopened, with its
    reason, before the year is closed -- the audit shows that it happened.
    """

    code = "periods.last_period_not_open"
    status = 409
