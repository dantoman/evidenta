"""Month arithmetic, in one place -- both period generators need the same edges.

Two entities in this module cut time into months, and they are deliberately not
the same entity: the accounting period, which is exactly one calendar month for
everyone (ADR-039 section 7), and the VAT fiscal period, which equals the
calendar month except for the last one of a cancelled registration (Codul fiscal
art. 114). Keeping the two concepts apart is the whole point of F1.5.3 -- but
"which day ends February 2027" is the same question for both, and two copies of
that answer is the kind of duplication that stays correct in both places right up
until one of them is fixed.

Every function takes a date and returns a date. Nothing here reads the clock: the
day on which a calculation runs must never change what it computes (R18).
"""

from __future__ import annotations

import calendar
from datetime import date


def first_day_of_month(day: date) -> date:
    return day.replace(day=1)


def last_day_of_month(day: date) -> date:
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


def first_day_of_next_month(day: date) -> date:
    return (
        day.replace(year=day.year + 1, month=1, day=1)
        if day.month == 12
        else day.replace(month=day.month + 1, day=1)
    )


def months_between(start: date, end: date) -> int:
    """Whole months covered by ``[start, end]``, both aligned to month edges."""
    return (end.year - start.year) * 12 + (end.month - start.month) + 1
