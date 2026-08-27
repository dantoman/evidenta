"""Creating a numbering template -- the choice a company makes once.

`allocation.resolve_template` refuses a document type with no template, and is
right to: a number invented at allocation time would go out on documents that
leave the company. The other half of that refusal is this -- somewhere a template
gets chosen, and creating a company is when.

A service rather than a model import, because the caller is another module
(`tenancy`) and `D6` is the rule: modules talk through services.
"""

from __future__ import annotations

import uuid

from evidenta.platform.numbering.models import NumberingTemplate, ResetPolicy, YearFormat


def create_general_template(
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    *,
    digits: int = 6,
    separator: str = "-",
) -> NumberingTemplate:
    """The company's fallback template: every document type with none of its own.

    Yearly reset with the year in the number, which is what a register that
    restarts each exercise needs in order to stay unambiguous across years. A
    company that wants something else changes it; what it cannot do is have none,
    because then its first journal entry cannot be numbered.
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
    )
