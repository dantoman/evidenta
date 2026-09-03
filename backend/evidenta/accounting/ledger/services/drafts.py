"""What the ledger holds that is not yet posted -- a count, for the closing door.

A draft entry dated inside a month is work in progress the closing would strand:
once the month is closed the engine refuses the posting, and the draft sits
there pointing at a period that no longer takes it. The closing checks ask how
many there are, and they ask **here** rather than reading `JournalEntry` from
`periods`: two modules that talk through each other's models are one module
with a seam (`D6`), and the dependency guard refuses the import.

Counted in the database, never listed: the caller shows a number beside a
button, and a list of every draft would be a page of rows to produce one
integer -- the reasoning `platform.documents.unposted_work` gives.
"""

from __future__ import annotations

import uuid
from datetime import date

from evidenta.accounting.ledger.models import EntryStatus, JournalEntry


def draft_entries_between(company_id: uuid.UUID, start: date, end: date) -> int:
    """Draft entries of the company dated in ``[start, end]``, both ends inclusive.

    Inclusive because the window is a period's, and a period's ``end_date`` is
    its last day (`periods.models.Period`), not the day after.
    """
    return JournalEntry.objects.filter(
        company_id=company_id,
        status=EntryStatus.DRAFT,
        accounting_date__gte=start,
        accounting_date__lte=end,
    ).count()
