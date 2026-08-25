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
