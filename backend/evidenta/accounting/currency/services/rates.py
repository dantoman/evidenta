"""Finding an exchange rate, and the history behind it.

Reading is open to every tenant: the official rate on a day is the same rate for
everyone, and a posted entry keeps the rate it was made at (`R10`), so the client
has to be able to see which rate that was. Writing goes through privileged path
`P-3` and is not here.

**Exact date, or a refusal.** `rate_on` matches the day asked for and nothing
else. Falling back to the last published rate would be a rule, not a
convenience -- the BNM publishes on banking days, and which rate applies to a
Saturday document is decided by the Cod fiscal and by the accounting policy, not
by whichever row happened to be nearest. `latest_before` exists for a caller that
has decided that question and wants to say so out loud; it is a different
function precisely so the choice is visible in the call site.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from evidenta.accounting.currency.models import ExchangeRate, RateType
from evidenta.platform.api.errors import ApiError


class RateNotFoundError(ApiError):
    """No rate of that type is published for that currency on that day.

    A refusal rather than an empty result: a document converted at a rate that
    does not exist carries an amount nobody can reproduce, and it carries it into
    an immutable entry.
    """

    code = "currency.rate_not_found"
    status = 404


def rate_on(currency: str, on: date, *, rate_type: str = RateType.BNM_OFFICIAL) -> Decimal:
    """The rate published for that currency, on that day, of that type."""
    value = (
        ExchangeRate.objects.filter(currency=currency.upper(), rate_date=on, rate_type=rate_type)
        .values_list("rate", flat=True)
        .first()
    )
    if value is None:
        raise RateNotFoundError(
            f"no {rate_type} rate for {currency.upper()} on {on}. A missing rate is "
            f"not a rate of one, and which rate applies on a day with none "
            f"published is a decision this function does not take."
        )
    return Decimal(value)


def latest_before(
    currency: str, on: date, *, rate_type: str = RateType.BNM_OFFICIAL
) -> tuple[date, Decimal]:
    """The most recent rate at or before a day, with the day it was published on.

    Returns the date as well as the rate, and that is the whole reason this
    function is separate: a caller that carries a rate forward from Friday to
    Sunday has to record *which* day it came from, or the document says it was
    converted at Sunday's rate and no such rate exists.
    """
    row = (
        ExchangeRate.objects.filter(
            currency=currency.upper(), rate_date__lte=on, rate_type=rate_type
        )
        .order_by("-rate_date")
        .values_list("rate_date", "rate")
        .first()
    )
    if row is None:
        raise RateNotFoundError(f"no {rate_type} rate for {currency.upper()} at or before {on}")
    published_on, value = row
    return published_on, Decimal(value)


def history(
    currency: str,
    *,
    since: date | None = None,
    until: date | None = None,
    rate_type: str = RateType.BNM_OFFICIAL,
) -> list[tuple[date, Decimal]]:
    """Every published rate for a currency, oldest first.

    The full series is kept, not just the current value: a recalculation of a
    closed period has to reach the rate that was in force then (`R18`), and a
    table that only held today's answer could not.
    """
    rows = ExchangeRate.objects.filter(currency=currency.upper(), rate_type=rate_type)
    if since is not None:
        rows = rows.filter(rate_date__gte=since)
    if until is not None:
        rows = rows.filter(rate_date__lte=until)
    return [
        (row_date, Decimal(value))
        for row_date, value in rows.order_by("rate_date").values_list("rate_date", "rate")
    ]
