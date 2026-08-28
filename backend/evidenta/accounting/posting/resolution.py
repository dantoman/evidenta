"""Choosing the treatment for one accounting event -- F1.4.1, R17, R18, R26.

The selection itself lives in `accounting.events.registry`: event type plus
effective date plus capability set, most specific wins, zero or two is an error.
This module does not repeat it. What it adds is the half that turns a stored
event into the three arguments that selection needs -- and one of those, the
capability set, is stored as `jsonb` and read back years later.

**Nothing here takes an `AccountingEvent`.** `D6` forbids reaching into another
module's models, and the exception for schema composition covers `models`, not
services -- so the caller, which already holds the event, passes its values. The
signature is the boundary.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from evidenta.accounting.events.registry import (
    implementation_of,
    resolve_handler,
    resolve_version,
)
from evidenta.platform.api.errors import ApiError
from evidenta.platform.capabilities.services.profile import SNAPSHOT_VERSION


class UnreadableCapabilitySnapshotError(ApiError):
    """The snapshot is missing, malformed, or of a shape this code cannot read.

    **Refusing is the whole point.** The tempting fallback is "no capabilities",
    and it is the worst available answer: a company with VAT would silently get
    the treatment written for a company without it, the entry would balance, and
    nothing downstream would look wrong. R26 makes the profile an explicit input
    precisely so that a missing one cannot be mistaken for an empty one.

    A snapshot from a *newer* shape is refused for the same reason rather than
    read optimistically -- a version bump exists because a meaning changed.
    """

    code = "posting.unreadable_capability_snapshot"
    status = 409


def capabilities_from(snapshot: Any) -> frozenset[str]:
    """The usable capability keys recorded on an event.

    ``usable``, not ``activated``: a capability whose initialisation is still
    running would select the treatment that assumes the setup it has not
    finished -- opening balances not loaded, payroll cumulatives starting from
    zero mid-year. See `platform.capabilities.services.profile`.
    """
    if not isinstance(snapshot, dict):
        raise UnreadableCapabilitySnapshotError(
            f"capability snapshot is {type(snapshot).__name__}, not an object"
        )

    version = snapshot.get("version")
    if version != SNAPSHOT_VERSION:
        raise UnreadableCapabilitySnapshotError(
            f"capability snapshot is version {version!r}; this code reads "
            f"version {SNAPSHOT_VERSION}. A snapshot with no version predates the "
            f"profile service and records nothing about what the company had."
        )

    usable = snapshot.get("usable")
    if not isinstance(usable, list) or not all(isinstance(key, str) for key in usable):
        raise UnreadableCapabilitySnapshotError("capability snapshot has no readable `usable` list")

    return frozenset(usable)


@dataclass(frozen=True, slots=True)
class Treatment:
    """A selected treatment: the callable, and the reference that names it.

    The reference is what the entry header stamps as `rule_ref` (ADR-048). A
    callable alone cannot be written down, and a stamp that had to be looked up
    again from the registry would say what the registry says *now*.
    """

    ref: str
    handler: Callable[..., Any]


def selected_treatment(
    event_type: str, accounting_date: date, capability_snapshot: Any
) -> Treatment:
    """`treatment_for`, keeping the reference beside the callable."""
    version = resolve_version(event_type, accounting_date, capabilities_from(capability_snapshot))
    return Treatment(ref=version.implementation_ref, handler=implementation_of(event_type, version))


def treatment_for(
    event_type: str, accounting_date: date, capability_snapshot: Any
) -> Callable[..., Any]:
    """The handler that records this event, or a refusal naming why.

    Both inputs come from the event, not from the clock and not from the current
    state of the company: recalculating a 2026 period in 2030 has to select what
    2026 selected. That is R18, and it only holds because the capability set was
    captured when the event was recorded rather than looked up now -- the company
    may have gained VAT since.
    """
    return resolve_handler(event_type, accounting_date, capabilities_from(capability_snapshot))
