"""Writing exchange rates -- the other half of `rates.py`, behind privileged path `P-3`.

`rate_on` refuses a day with no rate rather than reaching for the nearest one,
and that refusal is only honest if there is a door through which the rate of a
day can arrive. This is the door. It is the same shape as the fiscal parameters'
(`load_fiscal_parameters`, `P-4`): rows come from a file, they are written
under the reference-data role, and every run leaves one row in
`privileged_access_log` (ADR-049). Nothing else in the process holds a
connection that can write `exchange_rate`.

**Idempotent on the natural key**, `(currency, rate_date, rate_type)` -- Spec B
section 7.2's unique constraint. A row already there with the same value is
counted and left alone; a row already there with a *different* value is
refused, never overwritten. The reason is `R10` one table over: an entry posted
last month stands on the rate this table held then, and a rate that changes
under it makes the entry unreproducible. A corrected official rate is a new
fact and gets a row of its own type (`manual`, with its source saying why).

**Two of the three types are loadable.** `bnm_official` is what the BNM
publishes; `manual` is what an operator keys in from the same publication when
the connector (`OD-76`) is not there. `contractual` is not a rate of a day, it
is a stipulation of a document (`document.rate_term = fixed`), and a file that
claimed one would be putting a contract term in a global table.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import IO

from evidenta.accounting.currency.models import ExchangeRate, RateType
from evidenta.platform.api.errors import ApiError

#: The file's columns, in the order the sample shows them. `source` is required
#: as a column and may be empty on a row: an official rate names its bulletin, a
#: manual one says who read it where.
COLUMNS = ("currency", "rate_date", "rate", "rate_type", "source")

LOADABLE_TYPES = (RateType.BNM_OFFICIAL, RateType.MANUAL)


class RateFileMalformedError(ApiError):
    """A row that cannot become a rate: wrong columns, a date that is not one, a
    rate that is not positive, a type this door does not load."""

    code = "currency.rate_file_malformed"
    status = 422


class RateConflictError(ApiError):
    """A rate for that day and type already exists with another value.

    Refused rather than replaced. The value already there may be under a posted
    entry, and an entry whose rate moved after posting is one nobody can
    reproduce. The correction is a new row of type `manual`, with its source.
    """

    code = "currency.rate_conflict"
    status = 409


@dataclass(frozen=True, slots=True)
class RateRow:
    currency: str
    rate_date: date
    rate: Decimal
    rate_type: str
    source: str | None


@dataclass(frozen=True, slots=True)
class LoadOutcome:
    created: int
    unchanged: int


def parse_rates(handle: IO[str]) -> tuple[RateRow, ...]:
    """Read the CSV, refusing the first row that is not a rate.

    The whole file is parsed before anything is written, so a malformed row in
    the middle leaves the table as it was rather than half-loaded.
    """
    reader = csv.DictReader(handle)
    header = tuple(reader.fieldnames or ())
    if header != COLUMNS:
        raise RateFileMalformedError(
            f"the file's columns are {header}; a rates file has exactly {COLUMNS}, in that order"
        )
    rows: list[RateRow] = []
    for number, raw in enumerate(reader, start=2):
        rows.append(_row(raw, number))
    if not rows:
        raise RateFileMalformedError("the file has a header and no rates")
    return tuple(rows)


def _row(raw: dict[str, str | None], number: int) -> RateRow:
    currency = (raw.get("currency") or "").strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise RateFileMalformedError(
            f"line {number}: currency {currency!r} is not a three-letter ISO 4217 code"
        )
    try:
        rate_date = date.fromisoformat((raw.get("rate_date") or "").strip())
    except ValueError:
        raise RateFileMalformedError(
            f"line {number}: rate_date {raw.get('rate_date')!r} is not a date (YYYY-MM-DD)"
        ) from None
    try:
        rate = Decimal((raw.get("rate") or "").strip())
    except InvalidOperation:
        raise RateFileMalformedError(
            f"line {number}: rate {raw.get('rate')!r} is not a number"
        ) from None
    if not rate.is_finite() or rate <= 0:
        raise RateFileMalformedError(
            f"line {number}: rate {rate} is not positive; a zero rate erases the amount"
        )
    exponent = rate.as_tuple().exponent
    if isinstance(exponent, int) and -exponent > 8:
        raise RateFileMalformedError(
            f"line {number}: rate {rate} carries more than the eight decimals the "
            f"column stores (Spec B section 7.2); rounding it here would load a rate "
            f"the BNM did not publish"
        )
    rate_type = (raw.get("rate_type") or "").strip()
    if rate_type not in LOADABLE_TYPES:
        raise RateFileMalformedError(
            f"line {number}: rate_type {rate_type!r} is not loadable; the file carries "
            f"{', '.join(LOADABLE_TYPES)} -- a contractual rate belongs to a document"
        )
    source = (raw.get("source") or "").strip() or None
    if source is None:
        # R15: a rate is reference data, and reference data names where it was
        # read -- the bulletin, the contract. A row without one cannot be
        # defended later, so it is refused at the door (fiscal reviewer).
        raise RateFileMalformedError(
            f"row {number}: a rate names its source (the BNM bulletin, the contract); "
            f"a rate with no provenance is not loaded"
        )
    return RateRow(
        currency=currency, rate_date=rate_date, rate=rate, rate_type=rate_type, source=source
    )


def load_rates(rows: Iterable[RateRow], *, using: str) -> LoadOutcome:
    """Write the rows on the given connection, once each, refusing a changed value.

    Meant to run inside `privileged_run`, which supplies the transaction and the
    log row; this function neither opens nor logs anything, so that a caller
    cannot get the write without the audit.
    """
    created = unchanged = 0
    fetched_at = datetime.now(tz=UTC)
    for row in rows:
        existing = (
            ExchangeRate.objects.using(using)
            .filter(currency=row.currency, rate_date=row.rate_date, rate_type=row.rate_type)
            .values_list("rate", flat=True)
            .first()
        )
        if existing is not None:
            if Decimal(existing) != row.rate:
                raise RateConflictError(
                    f"{row.rate_type} rate for {row.currency} on {row.rate_date} is already "
                    f"{existing}; the file says {row.rate}. A rate is not edited under the "
                    f"entries that stand on it -- a correction is a new row of type "
                    f"'manual', with its source"
                )
            unchanged += 1
            continue
        ExchangeRate.objects.using(using).create(
            currency=row.currency,
            rate_date=row.rate_date,
            rate=row.rate,
            rate_type=row.rate_type,
            source=row.source,
            fetched_at=fetched_at,
        )
        created += 1
    return LoadOutcome(created=created, unchanged=unchanged)
