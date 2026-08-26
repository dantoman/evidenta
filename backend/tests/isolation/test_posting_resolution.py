"""Turning a stored event into a treatment -- F1.4.1.

The selection rule itself is proved in the registry's own suite. What is proved
here is the half that makes it survive time: the capability set comes out of the
event, in the shape the profile service wrote, and an unreadable one is refused
rather than read as "no capabilities".

No database. These are pure functions over a registry and a dict, which is what
keeps them in the fast CI job.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest

from evidenta.accounting.events import registry
from evidenta.accounting.events.registry import (
    AmbiguousHandlerError,
    EventType,
    HandlerVersion,
    NoHandlerError,
)
from evidenta.accounting.posting.resolution import (
    UnreadableCapabilitySnapshotError,
    capabilities_from,
    treatment_for,
)

SNAPSHOT = {"version": 1, "on": "2026-06-01", "activated": ["vat"], "usable": ["vat"]}
PLAIN = {"version": 1, "on": "2026-06-01", "activated": [], "usable": []}


@pytest.fixture
def registered() -> Iterator[None]:
    """Two treatments of one event on one date, told apart by VAT.

    The shape R26 actually asks for: not a gate, but two ways of recording the
    same operation, chosen by what the company has.
    """
    registry.HANDLERS["fixture.with_vat"] = lambda **_: "with_vat"
    registry.HANDLERS["fixture.plain"] = lambda **_: "plain"
    registry.register(
        EventType(
            name="fixture.sale",
            payload_fields=("amount",),
            handlers=(
                HandlerVersion(
                    implementation_ref="fixture.with_vat",
                    valid_from=date(2026, 1, 1),
                    requires=frozenset({"vat"}),
                ),
                HandlerVersion(implementation_ref="fixture.plain", valid_from=date(2026, 1, 1)),
            ),
        )
    )
    yield
    registry.REGISTRY.pop("fixture.sale", None)
    registry.HANDLERS.pop("fixture.with_vat", None)
    registry.HANDLERS.pop("fixture.plain", None)


def test_the_profile_selects_between_two_treatments(registered: None) -> None:
    assert treatment_for("fixture.sale", date(2026, 6, 1), SNAPSHOT)() == "with_vat"
    assert treatment_for("fixture.sale", date(2026, 6, 1), PLAIN)() == "plain"


def test_a_snapshot_without_a_version_is_refused(registered: None) -> None:
    """The tempting fallback is "no capabilities", and it is the worst answer.

    A company with VAT would silently get the treatment written for one without
    it, the entry would balance, and nothing downstream would look wrong. `{}` is
    exactly the value every caller passed before the profile service existed.
    """
    with pytest.raises(UnreadableCapabilitySnapshotError) as excinfo:
        treatment_for("fixture.sale", date(2026, 6, 1), {})
    assert excinfo.value.code == "posting.unreadable_capability_snapshot"


def test_a_snapshot_from_a_newer_shape_is_refused() -> None:
    """A version bump exists because a meaning changed. Reading it optimistically
    is choosing to misunderstand it.
    """
    with pytest.raises(UnreadableCapabilitySnapshotError):
        capabilities_from({"version": 2, "usable": ["vat"]})


@pytest.mark.parametrize("value", [None, [], "vat", {"version": 1, "usable": "vat"}])
def test_a_malformed_snapshot_is_refused(value: object) -> None:
    with pytest.raises(UnreadableCapabilitySnapshotError):
        capabilities_from(value)


def test_a_usable_list_is_read_as_it_was_written() -> None:
    """The shape is the one `CapabilityProfile.as_snapshot()` produces -- the two
    halves of this contract are written in different modules and must not drift.
    """
    assert capabilities_from(SNAPSHOT) == frozenset({"vat"})
    assert capabilities_from(PLAIN) == frozenset()


def test_a_period_with_no_treatment_is_a_registration_gap(registered: None) -> None:
    """Distinct from "the company lacks the capability": the remedies differ.

    This one is closed by a deployment; the other is a question about how the
    tenant is configured.
    """
    with pytest.raises(NoHandlerError):
        treatment_for("fixture.sale", date(2025, 6, 1), PLAIN)


def test_two_incomparable_treatments_stay_ambiguous() -> None:
    """Most specific wins, but "most" has to exist.

    Two maximal treatments with incomparable requirements -- one needing VAT, one
    needing inventory, for a company holding both -- is a registration that cannot
    answer the question. Ordering by size, or by declaration order, would answer
    one the entry never asked.
    """
    registry.HANDLERS["fixture.a"] = lambda **_: "a"
    registry.HANDLERS["fixture.b"] = lambda **_: "b"
    registry.register(
        EventType(
            name="fixture.split",
            payload_fields=("amount",),
            handlers=(
                HandlerVersion(
                    implementation_ref="fixture.a",
                    valid_from=date(2026, 1, 1),
                    requires=frozenset({"vat"}),
                ),
                HandlerVersion(
                    implementation_ref="fixture.b",
                    valid_from=date(2026, 1, 1),
                    requires=frozenset({"inventory"}),
                ),
            ),
        )
    )
    try:
        both = {"version": 1, "on": "2026-06-01", "activated": [], "usable": ["vat", "inventory"]}
        with pytest.raises(AmbiguousHandlerError):
            treatment_for("fixture.split", date(2026, 6, 1), both)
    finally:
        registry.REGISTRY.pop("fixture.split", None)
        registry.HANDLERS.pop("fixture.a", None)
        registry.HANDLERS.pop("fixture.b", None)
