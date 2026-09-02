"""What was true about a company's fiscal standing on a date -- ADR-088.

**One question, one answer.** *Is this company a VAT payer on 20 January 2026?*
has to be answerable long after January, because `R18` makes recalculating a past
period use what was valid then. `company_vat_registration` was built for exactly
that -- dated, with a source, never a boolean -- and this is the service that
reads it as a whole rather than one row at a time.

**Versioned from the first row.** A snapshot without a version says nothing about
what the code that wrote it was reading, and the first time the shape grows,
every stamp already written becomes ambiguous.

**Absence is an answer, not a gap.** A company with no registration covering the
date gets `{"registered": false}`, not an empty object: "measured, and not
registered" and "nobody looked" are different facts, and the second is what an
empty stamp would leave a reader to guess.

Statuses arrive here as they get tables. IT-park residency has none yet (`OD-81`
names it, the code has never had it), and this service does not invent one: a
schema with no reader is what ADR-088 §5 declines to design.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from evidenta.platform.tenancy.models import CompanyVatRegistration

#: Bumped when the shape changes, never when a value does.
SNAPSHOT_VERSION = 1


def tax_status_at(company_id: uuid.UUID, on: date) -> dict[str, Any]:
    """The company's dated fiscal statuses in force on ``on``."""
    registration = (
        CompanyVatRegistration.objects.filter(company_id=company_id, valid_from__lte=on)
        .exclude(valid_to__lt=on)
        .order_by("-valid_from")
        .first()
    )

    vat: dict[str, Any]
    if registration is None:
        vat = {"registered": False}
    else:
        vat = {
            "registered": True,
            "code": registration.vat_code,
            "valid_from": str(registration.valid_from),
            "valid_to": None if registration.valid_to is None else str(registration.valid_to),
        }

    return {"version": SNAPSHOT_VERSION, "on": str(on), "vat": vat}


def registered_for_vat_over(company_id: uuid.UUID, start: date, end: date) -> bool:
    """Whether any registration touches the days ``start``..``end``, inclusive.

    The question a VAT fiscal period asks before it is opened: art. 114 makes the
    period the month, and a month in which the company was a payer for a single
    day is a month it declares. A registration that begins on the 15th therefore
    covers January -- overlap, not containment.
    """
    return (
        CompanyVatRegistration.objects.filter(company_id=company_id, valid_from__lte=end)
        .exclude(valid_to__lt=start)
        .exists()
    )
