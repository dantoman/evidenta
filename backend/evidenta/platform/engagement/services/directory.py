"""Who has delegated access to the workspace in context -- read-only.

Separate from ``lifecycle`` on purpose: that module moves an engagement through
the state machine, this one only reports. A screen that needs to say *whose
accountant can see these books* has no business importing the transitions.

The policy on ``engagement`` decides for both parties (``rls.can_see_engagement``),
so no filter here is a guard -- ``client_tenant_id`` is filtered because the
question is about this workspace as a **client**, not about engagements this
workspace's firm holds over others. The two are different rows and answering both
in one list would put a client and a mandate side by side.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from evidenta.platform.engagement.models import Engagement


@dataclass(frozen=True)
class DelegationView:
    engagement_id: uuid.UUID
    firm_name: str
    status: str
    covers_all_companies: bool
    valid_from: date
    valid_to: date | None


def delegations_for_client(tenant_id: uuid.UUID) -> tuple[DelegationView, ...]:
    rows = (
        Engagement.objects.filter(client_tenant_id=tenant_id)
        .select_related("firm")
        .order_by("-valid_from")
    )
    return tuple(
        DelegationView(
            engagement_id=row.id,
            firm_name=row.firm.name,
            status=row.status,
            covers_all_companies=row.covers_all_companies,
            valid_from=row.valid_from,
            valid_to=row.valid_to,
        )
        for row in rows
    )
