"""Reading the opening payroll cumulatives -- the half ADR-061 left for `payroll`.

The table has held the shape since F1.7 and its docstring says outright that it
is *"read by `payroll` when that module exists"*. It exists now, so this is the
public service that lets it be read without `operations` importing
`accounting.opening`'s models (`D6`).

**Why it matters more than it looks.** A company put into service in the middle
of a year has already had salaries paid, exemptions granted and tax withheld
elsewhere. The cumulative method of HG 697/2014 point 38 computes from the start
of the fiscal year, so a payroll run that started from zero would grant the
year's exemptions a second time -- a withholding too low, arithmetically
consistent, and wrong for every remaining month of the year.

Amounts are magnitudes, never negative (ADR-061): the meaning is in `code`.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.db.models import Sum

from evidenta.accounting.opening.models import BatchStatus, OpeningBalancePayrollCumulative


def opening_cumulative(
    *, company_id: uuid.UUID, employee_id: uuid.UUID, code: str, year: int
) -> Decimal:
    """What was already accumulated under `code` before this system's first run.

    Only from **posted** batches: a draft batch is a work in progress, and a
    cumulative read from one would change under the calculation's feet.

    Returns zero when nothing was loaded, and that zero is honest rather than
    assumed -- a company that started in January has no prior cumulative, which is
    a different statement from "we do not know" and the two are distinguishable
    by whether a batch exists at all.
    """
    total = (
        OpeningBalancePayrollCumulative.objects.filter(
            batch__company_id=company_id,
            batch__status=BatchStatus.POSTED,
            employee_id=employee_id,
            code=code,
            from_date__year=year,
        ).aggregate(total=Sum("amount"))
    )["total"]
    return Decimal(total or 0)
