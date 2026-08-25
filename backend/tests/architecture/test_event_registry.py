"""The `event_type` registry -- F1.3.2, ADR-038.

No database. The registry is code, and that is the point being defended: a
registration selects from a table of implementations declared in this build, it
never names an importable path. Feeding `implementation_ref` to an import would
turn one privileged INSERT into arbitrary code execution in the application role,
and the dependency guard -- which walks the AST -- would see nothing.

Every rule here has a probe that fails. The checks take the registry as a
parameter so the probes never touch the real vocabulary; a guard nobody has
watched refuse is a guard whose shape nobody knows.
"""

from __future__ import annotations

from datetime import date

import pytest

from evidenta.accounting.events import registry as reg
from evidenta.accounting.events.registry import (
    HANDLERS,
    AmbiguousHandlerError,
    DuplicateEventTypeError,
    EventType,
    HandlerVersion,
    MalformedEventTypeError,
    NoHandlerError,
    RegistryInvalidError,
    UnknownEventTypeError,
    audit,
    check_registry,
    register,
    resolve_handler,
)


@pytest.fixture(autouse=True)
def clean_registry():
    """Probes register into the real dicts, so they are restored afterwards.

    The alternative -- a parallel registry object -- would test a different
    mechanism from the one that ships.
    """
    saved_registry = dict(reg.REGISTRY)
    saved_handlers = dict(HANDLERS)
    saved_deprecated = set(reg.DEPRECATED)
    yield
    reg.REGISTRY.clear()
    reg.REGISTRY.update(saved_registry)
    HANDLERS.clear()
    HANDLERS.update(saved_handlers)
    reg.DEPRECATED.clear()
    reg.DEPRECATED.update(saved_deprecated)


def probe_handler(**_: object) -> list[object]:
    return []


# --- The name is the form Spec B fixes ---------------------------------------


@pytest.mark.parametrize(
    "name", ["sales.invoice_issued", "purchases.invoice_received", "payroll.run_approved"]
)
def test_the_spec_b_form_is_accepted(name: str) -> None:
    register(EventType(name=name, payload_fields=("amount",)))
    assert name in reg.REGISTRY


@pytest.mark.parametrize(
    "name",
    [
        "sales.invoice.issued",  # three segments -- the shape the draft ADR used
        "Sales.invoice_issued",  # capitals
        "invoice_issued",  # no namespace
        "sales.",  # empty action
    ],
)
def test_other_forms_are_refused(name: str) -> None:
    """A second naming convention inside a closed vocabulary means half the types
    are written wrong before anybody notices.
    """
    with pytest.raises(MalformedEventTypeError):
        register(EventType(name=name, payload_fields=()))


def test_a_duplicate_registration_is_refused() -> None:
    """Two entries for one name make the vocabulary answer differently depending
    on import order -- the same defect as a contract file that accepts two rows
    for one table and silently keeps the last.
    """
    register(EventType(name="sales.invoice_issued", payload_fields=()))
    with pytest.raises(DuplicateEventTypeError):
        register(EventType(name="sales.invoice_issued", payload_fields=()))


# --- Selection is by the period's date, never by "the newest" -----------------


def test_the_handler_of_the_period_is_selected_not_the_newest() -> None:
    """R17 and R18 in one assertion.

    Both handlers are registered and neither is "current". The date decides,
    which is exactly what makes `if year >= 2027` unnecessary in business code.
    """
    HANDLERS["probe.v1"] = probe_handler
    HANDLERS["probe.v2"] = probe_handler
    register(
        EventType(
            name="sales.invoice_issued",
            payload_fields=(),
            handlers=(
                HandlerVersion("probe.v1", date(2020, 1, 1), date(2024, 1, 1)),
                HandlerVersion("probe.v2", date(2024, 1, 1)),
            ),
        )
    )
    assert resolve_handler("sales.invoice_issued", date(2022, 6, 30)) is HANDLERS["probe.v1"]
    assert resolve_handler("sales.invoice_issued", date(2024, 1, 1)) is HANDLERS["probe.v2"]


def test_the_boundary_day_belongs_to_the_later_handler() -> None:
    """`[from, to)`, the same half-open window fiscal parameters use.

    An inclusive end here and an exclusive one there would differ on exactly one
    day a year -- found by a client at year end, not by a developer.
    """
    HANDLERS["probe.v1"] = probe_handler
    HANDLERS["probe.v2"] = probe_handler
    register(
        EventType(
            name="sales.invoice_issued",
            payload_fields=(),
            handlers=(
                HandlerVersion("probe.v1", date(2020, 1, 1), date(2024, 1, 1)),
                HandlerVersion("probe.v2", date(2024, 1, 1)),
            ),
        )
    )
    assert resolve_handler("sales.invoice_issued", date(2023, 12, 31)) is HANDLERS["probe.v1"]


def test_no_handler_for_the_period_is_an_error() -> None:
    """A type with no treatment for the period being posted has no safe default.

    The alternative -- posting to a fallback account -- is discovered in March
    for something that stopped working in November.
    """
    HANDLERS["probe.v2"] = probe_handler
    register(
        EventType(
            name="sales.invoice_issued",
            payload_fields=(),
            handlers=(HandlerVersion("probe.v2", date(2024, 1, 1)),),
        )
    )
    with pytest.raises(NoHandlerError):
        resolve_handler("sales.invoice_issued", date(2020, 1, 1))


def test_two_handlers_covering_one_date_is_an_error() -> None:
    HANDLERS["probe.a"] = probe_handler
    HANDLERS["probe.b"] = probe_handler
    register(
        EventType(
            name="sales.invoice_issued",
            payload_fields=(),
            handlers=(
                HandlerVersion("probe.a", date(2020, 1, 1)),
                HandlerVersion("probe.b", date(2022, 1, 1)),
            ),
        )
    )
    with pytest.raises(AmbiguousHandlerError):
        resolve_handler("sales.invoice_issued", date(2023, 1, 1))


def test_an_unregistered_type_cannot_be_resolved() -> None:
    with pytest.raises(UnknownEventTypeError):
        resolve_handler("sales.never_registered", date(2026, 1, 1))


def test_a_registration_selects_and_never_imports() -> None:
    """The security property, stated as a test.

    A registration naming something outside HANDLERS is refused rather than
    resolved. `os.system` is used as the reference precisely because a version
    that imported would find it.
    """
    register(
        EventType(
            name="sales.invoice_issued",
            payload_fields=(),
            handlers=(HandlerVersion("os.system", date(2020, 1, 1)),),
        )
    )
    with pytest.raises(NoHandlerError):
        resolve_handler("sales.invoice_issued", date(2026, 1, 1))


# --- The boot check, and its probes ------------------------------------------


def test_a_type_without_a_handler_is_reported() -> None:
    """The check that matters most: a type that can be emitted and not posted is
    a document that goes missing silently.
    """
    probe = {"sales.invoice_issued": EventType("sales.invoice_issued", ())}
    problems = audit(probe)
    assert any("no handler" in p for p in problems)


def test_a_gap_between_handlers_is_reported() -> None:
    """A gap is worse than an overlap. An overlap refuses at posting time, in
    front of somebody; a gap is silent until a document falls into it, possibly
    years after the registration was written.
    """
    HANDLERS["probe.a"] = probe_handler
    HANDLERS["probe.b"] = probe_handler
    probe = {
        "sales.invoice_issued": EventType(
            "sales.invoice_issued",
            (),
            handlers=(
                HandlerVersion("probe.a", date(2020, 1, 1), date(2023, 1, 1)),
                HandlerVersion("probe.b", date(2024, 1, 1)),
            ),
        )
    }
    problems = audit(probe)
    assert any("gap" in p for p in problems), problems


def test_an_overlap_is_reported() -> None:
    HANDLERS["probe.a"] = probe_handler
    HANDLERS["probe.b"] = probe_handler
    probe = {
        "sales.invoice_issued": EventType(
            "sales.invoice_issued",
            (),
            handlers=(
                HandlerVersion("probe.a", date(2020, 1, 1), date(2025, 1, 1)),
                HandlerVersion("probe.b", date(2024, 1, 1)),
            ),
        )
    }
    assert any("overlap" in p for p in audit(probe))


def test_an_open_ended_handler_followed_by_another_is_reported() -> None:
    """The overlap that is easy to write and hard to see: no `valid_to` on the
    first, so it covers everything the second was meant to take over.
    """
    HANDLERS["probe.a"] = probe_handler
    HANDLERS["probe.b"] = probe_handler
    probe = {
        "sales.invoice_issued": EventType(
            "sales.invoice_issued",
            (),
            handlers=(
                HandlerVersion("probe.a", date(2020, 1, 1)),
                HandlerVersion("probe.b", date(2024, 1, 1)),
            ),
        )
    }
    assert any("open-ended" in p for p in audit(probe))


def test_a_handler_this_build_lacks_is_reported() -> None:
    probe = {
        "sales.invoice_issued": EventType(
            "sales.invoice_issued",
            (),
            handlers=(HandlerVersion("probe.absent", date(2020, 1, 1)),),
        )
    }
    assert any("HANDLERS" in p for p in audit(probe))


def test_the_shipped_registry_is_serviceable() -> None:
    """The real check, run here as well as at process startup.

    Empty today: no module registers a type yet, and an empty vocabulary is
    serviceable. It stops being empty at F1.4.4, and this test is what will
    refuse the first registration that arrives without a handler.
    """
    check_registry()


def test_check_registry_refuses_an_unserviceable_vocabulary() -> None:
    """The probe for the boot check itself."""
    register(EventType(name="sales.invoice_issued", payload_fields=()))
    with pytest.raises(RegistryInvalidError):
        check_registry()


# --- Deprecation is not deletion ---------------------------------------------


def test_a_deprecated_type_keeps_its_handlers() -> None:
    """A type ever emitted is referenced by rows in an append-only ledger, and
    its handlers are what make those rows readable years later.
    """
    HANDLERS["probe.v1"] = probe_handler
    register(
        EventType(
            name="sales.invoice_issued",
            payload_fields=(),
            handlers=(HandlerVersion("probe.v1", date(2020, 1, 1)),),
        )
    )
    reg.deprecate("sales.invoice_issued")
    assert "sales.invoice_issued" in reg.DEPRECATED
    assert resolve_handler("sales.invoice_issued", date(2021, 1, 1)) is HANDLERS["probe.v1"]
