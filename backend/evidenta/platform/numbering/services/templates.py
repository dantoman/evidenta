"""Creating a document series -- the choice a company makes, and can change.

`allocation.resolve_template` refuses a document type with no series in force,
and is right to: a number invented at allocation time would go out on documents
that leave the company. The other half of that refusal is here -- somewhere a
series gets chosen, and creating a company is when the first one is.

A service rather than a model import, because the callers are other modules
(`tenancy` at provisioning, `operations` when a company changes its series) and
`D6` is the rule: modules talk through services.

**Superseding, not editing.** A series that is already in force is not rewritten
when the company wants a different shape -- it is closed on a date and a new one
opens the next day. Rewriting it would renumber documents already issued under
it the next time anything re-read the template, and a register with reassigned
numbers is not a register (ADR-022, point 3).
"""

from __future__ import annotations

import uuid
from datetime import date

from django.db import transaction

from evidenta.platform.api.errors import ApiError
from evidenta.platform.numbering.models import (
    NumberingTemplate,
    ResetPolicy,
    YearFormat,
)
from evidenta.platform.numbering.regimes import NumberingRegime


class SeriesOverlapError(ApiError):
    """Two series would answer for the same document type on the same day.

    The database refuses it too -- `numbering_template_no_overlap`. This is the
    stable code (C10), not the guarantee.
    """

    code = "numbering.series_overlap"
    status = 409


class SeriesNotFoundError(ApiError):
    code = "numbering.series_not_found"
    status = 404


class SeriesAlreadyClosedError(ApiError):
    code = "numbering.series_already_closed"
    status = 409


def create_general_template(
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    *,
    valid_from: date,
    digits: int = 6,
    separator: str = "-",
) -> NumberingTemplate:
    """The company's fallback series: every document type with none of its own.

    Yearly reset with the year in the number, which is what a register that
    restarts each exercise needs in order to stay unambiguous across years. A
    company that wants something else changes it; what it cannot do is have none,
    because then its first journal entry cannot be numbered.

    ``valid_from`` is required and is the day the company's books start, passed
    by the caller. No default: a series valid from "today" would leave a document
    dated before the company was created without a number, and one valid from the
    beginning of time would be a claim nobody made.
    """
    return NumberingTemplate.objects.create(
        tenant_id=tenant_id,
        company_id=company_id,
        document_type=None,
        series="",
        prefix="",
        suffix="",
        separator=separator,
        digits=digits,
        include_year=True,
        year_format=YearFormat.FOUR_DIGIT,
        reset_policy=ResetPolicy.YEARLY,
        regime=NumberingRegime.OWN,
        valid_from=valid_from,
    )


@transaction.atomic
def create_series(
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    *,
    document_type: str | None,
    valid_from: date,
    valid_to: date | None = None,
    regime: str = NumberingRegime.OWN,
    series: str = "",
    prefix: str = "",
    suffix: str = "",
    separator: str = "-",
    digits: int = 6,
    include_year: bool = True,
    year_format: str = YearFormat.FOUR_DIGIT,
    reset_policy: str = ResetPolicy.YEARLY,
) -> NumberingTemplate:
    """Open a series for one document type, or for the company as a whole.

    ``document_type=None`` is the general series. The overlap is refused by the
    database; the check here exists to answer with a stable code instead of an
    integrity error, and it is not the guarantee -- two concurrent writers reach
    the constraint, not this branch.
    """
    clashing = NumberingTemplate.objects.filter(company_id=company_id, document_type=document_type)
    for existing in clashing:
        if _overlaps(existing.valid_from, existing.valid_to, valid_from, valid_to):
            raise SeriesOverlapError(
                f"a series for {document_type or 'every type'} is already in force "
                f"from {existing.valid_from} to {existing.valid_to or 'further notice'}"
            )

    return NumberingTemplate.objects.create(
        tenant_id=tenant_id,
        company_id=company_id,
        document_type=document_type,
        series=series,
        prefix=prefix,
        suffix=suffix,
        separator=separator,
        digits=digits,
        include_year=include_year,
        year_format=year_format,
        reset_policy=reset_policy,
        regime=regime,
        valid_from=valid_from,
        valid_to=valid_to,
    )


@transaction.atomic
def close_series(series_id: uuid.UUID, *, last_day: date) -> NumberingTemplate:
    """End a series on a day, so a successor can open the next one.

    The only supported way to stop using a series. Deleting it would orphan every
    document numbered under it, and editing its shape would change what those
    numbers mean.
    """
    template = NumberingTemplate.objects.select_for_update().filter(id=series_id).first()
    if template is None:
        raise SeriesNotFoundError(f"series {series_id} is not visible in this context")
    if template.valid_to is not None:
        raise SeriesAlreadyClosedError(f"series {series_id} already ends on {template.valid_to}")
    if last_day < template.valid_from:
        raise SeriesOverlapError(
            f"a series cannot end on {last_day}, before it starts on {template.valid_from}"
        )

    # Stored as the half-open upper bound: the first day the series no longer
    # applies. `last_day` is what a human says; the column is what the window
    # means, and conflating the two is the off-by-one day this system has
    # already paid for once.
    template.valid_to = date.fromordinal(last_day.toordinal() + 1)
    template.save(update_fields=["valid_to", "updated_at"])
    return template


def _overlaps(a_from: date, a_to: date | None, b_from: date, b_to: date | None) -> bool:
    """Half-open ``[from, to)`` intersection, with None meaning no upper bound."""
    if a_to is not None and a_to <= b_from:
        return False
    return not (b_to is not None and b_to <= a_from)
