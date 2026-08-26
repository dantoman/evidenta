"""The capability profile -- R25, R26, Spec A section 1.8.

R26 makes the profile an **explicit input** of the posting engine: the same
operation is recorded differently depending on what the company has active. Until
now nothing could produce one. `accounting_event.capability_snapshot` is a
required column, so every caller had to invent its value -- and a caller that
passed `{}` got a company with no capabilities, silently and plausibly.

**Activation is an entity, not a boolean** (R25), which is why the profile has two
sets rather than one. A capability whose initialisation is still `required` or
`in_progress` is activated and **not yet usable**: posting under it would produce
entries the initialisation exists to set up -- opening balances that are not
loaded, payroll cumulatives that start from zero mid-year.

**Tenant-level and company-level rows are a union, not a precedence.** The model
has no way to express a denial: `effective_to` ends an activation, it does not
negate a broader one, and the exclusion constraint keeps the two scopes from
colliding. So "either row in force" is the only reading the schema supports --
derived from it rather than chosen, which matters because the spec does not say.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from django.db.models import Q

from evidenta.platform.api.lookup import NotFoundError
from evidenta.platform.capabilities.models import (
    CapabilityActivation,
    InitialisationState,
)
from evidenta.platform.tenancy.services.access import company_visible_in_context

#: States in which an activation may actually be posted under. The other two --
#: `required` and `in_progress` -- mean the capability is switched on and its
#: setup is unfinished.
_USABLE = (InitialisationState.NOT_REQUIRED, InitialisationState.COMPLETE)

#: Version of the snapshot shape. It is stored on every accounting event and read
#: back years later when a period is recalculated, so the shape is a contract:
#: adding a key is safe, changing the meaning of one is not, and this is how a
#: reader tells which meaning it is holding.
SNAPSHOT_VERSION = 1


@dataclass(frozen=True, slots=True)
class CapabilityProfile:
    """What one company had active on one date.

    Carries the date it was computed for, because a profile without one is a
    claim about "now" -- and recalculating a closed period must be able to say
    which day's answer it used (R18).
    """

    company_id: uuid.UUID
    on_date: date
    activated: frozenset[str]
    usable: frozenset[str]

    def has(self, capability_key: str) -> bool:
        """Whether the engine may post under this capability.

        Deliberately the *usable* set. A caller that wanted "switched on but not
        ready" is asking a different question and should read `activated` -- and
        having to name it is the point.
        """
        return capability_key in self.usable

    def pending(self) -> frozenset[str]:
        """Activated, initialisation unfinished. The set a screen warns about."""
        return self.activated - self.usable

    def as_snapshot(self) -> dict[str, Any]:
        """The value stored on an accounting event (Spec B section 1.1).

        Sorted lists rather than sets: this goes into `jsonb` and is compared
        against later snapshots, and an unordered dump would make two identical
        profiles look different.
        """
        return {
            "version": SNAPSHOT_VERSION,
            "on": self.on_date.isoformat(),
            "activated": sorted(self.activated),
            "usable": sorted(self.usable),
        }


def active_profile(company_id: uuid.UUID, on_date: date) -> CapabilityProfile:
    """The profile of one company on one date.

    The date is a parameter and the clock is never read: recalculating a 2026
    period in 2030 has to see the 2026 profile, and a resolver that could fall
    back to "today" would answer with this year's capabilities -- silently, and
    looking correct (R18).

    The validity window is half-open, ``[effective_from, effective_to)``, matching
    the exclusion constraint on the table. It is written out here rather than
    shared with `fiscal.parameters.in_force`, which applies the same convention:
    `platform` imports no other layer, and a shared helper would invert the
    dependency graph for four lines of query.

    **The company is checked before the query, and that is not ceremony.** RLS
    narrows the rows to this tenant, so a company identifier belonging to somebody
    else returns no company-level rows -- but it still returns this tenant's
    *tenant-level* ones. The profile would come back non-empty for a company the
    caller cannot see, and an engine reading it would post as though those
    capabilities applied. Absent rather than forbidden (IZ-04): the answer does
    not say whether the identifier exists elsewhere.
    """
    if not company_visible_in_context(company_id):
        raise NotFoundError(f"company {company_id} is not visible in this context")

    rows = CapabilityActivation.objects.filter(
        Q(company_id=company_id) | Q(company__isnull=True),
        effective_from__lte=on_date,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=on_date))

    activated: set[str] = set()
    usable: set[str] = set()
    for key, state in rows.values_list("capability_key", "initialisation_state"):
        activated.add(key)
        if state in _USABLE:
            usable.add(key)

    return CapabilityProfile(
        company_id=company_id,
        on_date=on_date,
        activated=frozenset(activated),
        usable=frozenset(usable),
    )
