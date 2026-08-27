"""What another module may ask about a company, without touching its table.

`D6`: modules talk through services, not through each other's models. The
posting engine needs one fact -- the currency the books are kept in -- and
`manual.post_manual_entry` already documents why it takes it as a parameter
rather than looking it up: no public service of this module exposed it. This is
that service.

Everything here reads under the policy, so a company this context cannot see is
absent rather than forbidden (IZ-04).
"""

from __future__ import annotations

import uuid

from evidenta.platform.api.errors import ApiError
from evidenta.platform.tenancy.models import Company


class CompanyNotVisibleError(ApiError):
    """The company does not exist, or this context cannot reach it."""

    code = "tenancy.company_not_visible"
    status = 404


def functional_currency(company_id: uuid.UUID) -> str:
    """The currency this company keeps its books in."""
    currency = (
        Company.objects.filter(id=company_id).values_list("functional_currency", flat=True).first()
    )
    if currency is None:
        raise CompanyNotVisibleError(f"company {company_id} is not visible in this context")
    return str(currency)
