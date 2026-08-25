"""Allocating a document number -- ADR-022.

Four things the ADR says are not negotiable, and where each one lives:

1. **Uniqueness is enforced in the database** -- a unique constraint on
   ``document``, not a check here.
2. **No ``MAX(number) + 1``** -- a counter row, taken with ``SELECT FOR UPDATE``.
3. **A template is not applied retroactively** -- allocation happens once, and the
   formatted number is stored, not recomputed.
4. **Gaps are allowed and permanent** -- a cancelled document does not release its
   number.

Point 3 is the one that looks like an optimisation and is not. If the number were
formatted on read, changing a template would silently renumber every document
issued under the old one, and a register with reassigned numbers is not a
register.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from django.db import transaction

from evidenta.platform.numbering.models import (
    NumberingCounter,
    NumberingTemplate,
    ResetPolicy,
    YearFormat,
)


class NumberingError(RuntimeError):
    """A number cannot be allocated, with a stable code (C10)."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class AllocatedNumber:
    series: str
    number: int
    formatted: str
    fiscal_year: int


def resolve_template(company_id: uuid.UUID, document_type: str) -> NumberingTemplate:
    """The template for this type, else the company's general one.

    A type with neither is a configuration error and says so. Inventing a default
    here would produce numbers nobody chose, on documents that leave the company.
    """
    specific = NumberingTemplate.objects.filter(
        company_id=company_id, document_type=document_type
    ).first()
    if specific is not None:
        return specific

    general = NumberingTemplate.objects.filter(
        company_id=company_id, document_type__isnull=True
    ).first()
    if general is not None:
        return general

    raise NumberingError(
        "numbering.no_template",
        f"company {company_id} has no template for {document_type!r} and no general one",
    )


def period_key(template: NumberingTemplate, document_date: date) -> str:
    """The reset window this date falls in."""
    if template.reset_policy == ResetPolicy.YEARLY:
        return f"{document_date.year:04d}"
    if template.reset_policy == ResetPolicy.MONTHLY:
        return f"{document_date.year:04d}-{document_date.month:02d}"
    return ""


def format_number(template: NumberingTemplate, number: int, document_date: date) -> str:
    """Assemble the number from the template's parts."""
    parts: list[str] = []
    if template.prefix:
        parts.append(template.prefix)
    if template.series:
        parts.append(template.series)
    if template.include_year:
        year = document_date.year
        parts.append(
            f"{year:04d}" if template.year_format == YearFormat.FOUR_DIGIT else f"{year % 100:02d}"
        )
    parts.append(str(number).zfill(template.digits))
    if template.suffix:
        parts.append(template.suffix)
    return template.separator.join(parts)


def allocate(
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    document_type: str,
    document_date: date,
) -> AllocatedNumber:
    """Take the next number for this type and date.

    Must be called inside the document's own transaction. The counter row is
    locked for the rest of it, so two documents cannot take the same number, and
    the lock is held only for the allocation rather than for the whole document.
    """
    template = resolve_template(company_id, document_type)
    key = period_key(template, document_date)

    with transaction.atomic():
        counter, _ = NumberingCounter.objects.get_or_create(
            template=template,
            period_key=key,
            defaults={"tenant_id": tenant_id, "next_number": 1},
        )
        # Re-read under lock: get_or_create may have returned a row another
        # transaction is about to change.
        counter = NumberingCounter.objects.select_for_update().get(pk=counter.pk)

        number = counter.next_number
        counter.next_number = number + 1
        counter.save(update_fields=["next_number", "updated_at"])

    return AllocatedNumber(
        series=template.series,
        number=number,
        formatted=format_number(template, number, document_date),
        fiscal_year=document_date.year,
    )
