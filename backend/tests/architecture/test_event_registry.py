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

from collections.abc import Iterator
from contextlib import contextmanager
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
    saved_roles = set(reg.ACCOUNT_ROLES)
    yield
    reg.REGISTRY.clear()
    reg.REGISTRY.update(saved_registry)
    HANDLERS.clear()
    HANDLERS.update(saved_handlers)
    reg.DEPRECATED.clear()
    reg.DEPRECATED.update(saved_deprecated)
    reg.ACCOUNT_ROLES.clear()
    reg.ACCOUNT_ROLES.update(saved_roles)


def probe_handler(**_: object) -> list[object]:
    return []


# --- The name is the form Spec B fixes ---------------------------------------


@pytest.mark.parametrize(
    "name", ["fixture.sample_event", "purchases.invoice_received", "payroll.run_reversed"]
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
    register(EventType(name="fixture.sample_event", payload_fields=()))
    with pytest.raises(DuplicateEventTypeError):
        register(EventType(name="fixture.sample_event", payload_fields=()))


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
            name="fixture.sample_event",
            payload_fields=(),
            handlers=(
                HandlerVersion("probe.v1", date(2020, 1, 1), date(2024, 1, 1)),
                HandlerVersion("probe.v2", date(2024, 1, 1)),
            ),
        )
    )
    assert (
        resolve_handler("fixture.sample_event", date(2022, 6, 30), frozenset())
        is HANDLERS["probe.v1"]
    )
    assert (
        resolve_handler("fixture.sample_event", date(2024, 1, 1), frozenset())
        is HANDLERS["probe.v2"]
    )


def test_the_boundary_day_belongs_to_the_later_handler() -> None:
    """`[from, to)`, the same half-open window fiscal parameters use.

    An inclusive end here and an exclusive one there would differ on exactly one
    day a year -- found by a client at year end, not by a developer.
    """
    HANDLERS["probe.v1"] = probe_handler
    HANDLERS["probe.v2"] = probe_handler
    register(
        EventType(
            name="fixture.sample_event",
            payload_fields=(),
            handlers=(
                HandlerVersion("probe.v1", date(2020, 1, 1), date(2024, 1, 1)),
                HandlerVersion("probe.v2", date(2024, 1, 1)),
            ),
        )
    )
    assert (
        resolve_handler("fixture.sample_event", date(2023, 12, 31), frozenset())
        is HANDLERS["probe.v1"]
    )


def test_no_handler_for_the_period_is_an_error() -> None:
    """A type with no treatment for the period being posted has no safe default.

    The alternative -- posting to a fallback account -- is discovered in March
    for something that stopped working in November.
    """
    HANDLERS["probe.v2"] = probe_handler
    register(
        EventType(
            name="fixture.sample_event",
            payload_fields=(),
            handlers=(HandlerVersion("probe.v2", date(2024, 1, 1)),),
        )
    )
    with pytest.raises(NoHandlerError):
        resolve_handler("fixture.sample_event", date(2020, 1, 1), frozenset())


def test_two_handlers_covering_one_date_is_an_error() -> None:
    HANDLERS["probe.a"] = probe_handler
    HANDLERS["probe.b"] = probe_handler
    register(
        EventType(
            name="fixture.sample_event",
            payload_fields=(),
            handlers=(
                HandlerVersion("probe.a", date(2020, 1, 1)),
                HandlerVersion("probe.b", date(2022, 1, 1)),
            ),
        )
    )
    with pytest.raises(AmbiguousHandlerError):
        resolve_handler("fixture.sample_event", date(2023, 1, 1), frozenset())


def test_an_unregistered_type_cannot_be_resolved() -> None:
    with pytest.raises(UnknownEventTypeError):
        resolve_handler("sales.never_registered", date(2026, 1, 1), frozenset())


def test_a_registration_selects_and_never_imports() -> None:
    """The security property, stated as a test.

    A registration naming something outside HANDLERS is refused rather than
    resolved. `os.system` is used as the reference precisely because a version
    that imported would find it.
    """
    register(
        EventType(
            name="fixture.sample_event",
            payload_fields=(),
            handlers=(HandlerVersion("os.system", date(2020, 1, 1)),),
        )
    )
    with pytest.raises(NoHandlerError):
        resolve_handler("fixture.sample_event", date(2026, 1, 1), frozenset())


# --- The boot check, and its probes ------------------------------------------


def test_a_type_without_a_handler_is_reported() -> None:
    """The check that matters most: a type that can be emitted and not posted is
    a document that goes missing silently.
    """
    probe = {"fixture.sample_event": EventType("fixture.sample_event", ())}
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
        "fixture.sample_event": EventType(
            "fixture.sample_event",
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
        "fixture.sample_event": EventType(
            "fixture.sample_event",
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
        "fixture.sample_event": EventType(
            "fixture.sample_event",
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
        "fixture.sample_event": EventType(
            "fixture.sample_event",
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
    register(EventType(name="fixture.sample_event", payload_fields=()))
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
            name="fixture.sample_event",
            payload_fields=(),
            handlers=(HandlerVersion("probe.v1", date(2020, 1, 1)),),
        )
    )
    reg.deprecate("fixture.sample_event")
    assert "fixture.sample_event" in reg.DEPRECATED
    assert (
        resolve_handler("fixture.sample_event", date(2021, 1, 1), frozenset())
        is HANDLERS["probe.v1"]
    )


# --- Capabilities select the treatment, they do not gate it (R26) ------------


def test_two_treatments_of_one_event_coexist_on_one_date() -> None:
    """R26 as a test: the same operation, accounted for differently.

    Both handlers cover the day. The company's profile decides, and that is the
    reason `requires` is selection criteria rather than a gate -- a gate would
    have refused, and a refusal is not "accounted for differently".
    """
    HANDLERS["probe.with_vat"] = probe_handler
    HANDLERS["probe.without_vat"] = probe_handler
    register(
        EventType(
            name="fixture.sample_event",
            payload_fields=(),
            handlers=(
                HandlerVersion("probe.with_vat", date(2020, 1, 1), requires=frozenset({"vat"})),
                HandlerVersion("probe.without_vat", date(2020, 1, 1)),
            ),
        )
    )
    with_vat = resolve_handler("fixture.sample_event", date(2026, 1, 1), frozenset({"vat"}))
    without = resolve_handler("fixture.sample_event", date(2026, 1, 1), frozenset())
    assert with_vat is HANDLERS["probe.with_vat"]
    assert without is HANDLERS["probe.without_vat"]


def test_a_missing_capability_is_reported_as_such_not_as_a_missing_period() -> None:
    """The two failures are told apart because the fixes differ.

    "No treatment for this period" is a registration gap closed by a deployment.
    "Treatments exist and need capabilities this company lacks" is a tenant
    configuration question. Sending somebody to the wrong one costs an afternoon.
    """
    HANDLERS["probe.with_vat"] = probe_handler
    register(
        EventType(
            name="fixture.sample_event",
            payload_fields=(),
            handlers=(
                HandlerVersion("probe.with_vat", date(2020, 1, 1), requires=frozenset({"vat"})),
            ),
        )
    )
    with pytest.raises(NoHandlerError) as failure:
        resolve_handler("fixture.sample_event", date(2026, 1, 1), frozenset())
    assert "vat" in str(failure.value)
    assert "no handler" not in str(failure.value)


def test_handlers_differing_only_in_capability_are_not_an_overlap() -> None:
    """The consequence of R26 the guard has to know about.

    Checked together, a correct registration would be reported as broken -- and a
    guard that reports correct work is a guard people learn to ignore.
    """
    HANDLERS["probe.with_vat"] = probe_handler
    HANDLERS["probe.without_vat"] = probe_handler
    probe = {
        "fixture.sample_event": EventType(
            "fixture.sample_event",
            (),
            handlers=(
                HandlerVersion("probe.with_vat", date(2020, 1, 1), requires=frozenset({"vat"})),
                HandlerVersion("probe.without_vat", date(2020, 1, 1)),
            ),
        )
    }
    assert audit(probe) == []


def test_an_overlap_within_one_capability_set_is_still_reported() -> None:
    """The control for the grouping. Without it, `requires` would be a way to
    silence the overlap check rather than to express a distinction.
    """
    HANDLERS["probe.a"] = probe_handler
    HANDLERS["probe.b"] = probe_handler
    probe = {
        "fixture.sample_event": EventType(
            "fixture.sample_event",
            (),
            handlers=(
                HandlerVersion("probe.a", date(2020, 1, 1), requires=frozenset({"vat"})),
                HandlerVersion("probe.b", date(2024, 1, 1), requires=frozenset({"vat"})),
            ),
        )
    }
    assert any("open-ended" in p for p in audit(probe))


def test_incomparable_requirements_stay_ambiguous() -> None:
    """No tiebreak invented where the registration does not express one.

    One treatment needs VAT, another needs inventory, and a company has both.
    There is no reading of that registration which says one wins -- ordering them
    by size, or by declaration order, would answer a question nobody asked and
    would post under a treatment nobody chose.
    """
    HANDLERS["probe.vat"] = probe_handler
    HANDLERS["probe.inventory"] = probe_handler
    register(
        EventType(
            name="fixture.sample_event",
            payload_fields=(),
            handlers=(
                HandlerVersion("probe.vat", date(2020, 1, 1), requires=frozenset({"vat"})),
                HandlerVersion(
                    "probe.inventory", date(2020, 1, 1), requires=frozenset({"inventory"})
                ),
            ),
        )
    )
    with pytest.raises(AmbiguousHandlerError):
        resolve_handler("fixture.sample_event", date(2026, 1, 1), frozenset({"vat", "inventory"}))


def test_a_strict_superset_wins_over_the_general_treatment() -> None:
    """The control for "most specific wins".

    Without it the rule could be satisfied by picking either one, and the test
    above would pass on an implementation that simply took the first match.
    """
    HANDLERS["probe.general"] = probe_handler
    HANDLERS["probe.vat_inventory"] = probe_handler
    register(
        EventType(
            name="fixture.sample_event",
            payload_fields=(),
            handlers=(
                HandlerVersion("probe.general", date(2020, 1, 1), requires=frozenset({"vat"})),
                HandlerVersion(
                    "probe.vat_inventory",
                    date(2020, 1, 1),
                    requires=frozenset({"vat", "inventory"}),
                ),
            ),
        )
    )
    chosen = resolve_handler(
        "fixture.sample_event", date(2026, 1, 1), frozenset({"vat", "inventory"})
    )
    assert chosen is HANDLERS["probe.vat_inventory"]


# --- The account-role catalogue (ADR-038 section 5, point 3) ------------------


def test_an_unknown_account_role_is_reported() -> None:
    """The promise the ADR made and the code did not keep until now.

    `account_roles` was free text, so a typo became a role nothing could bind --
    found at posting, on a live document, rather than at startup.
    """
    reg.ACCOUNT_ROLES.update({"TVA_DEDUCTIBIL", "DATORII_FURNIZORI"})
    try:
        probe = {
            "purchases.invoice_received": EventType(
                "purchases.invoice_received",
                (),
                account_roles=("TVA_DEDUCTABIL",),  # one letter wrong
                handlers=(HandlerVersion("probe.v1", date(2020, 1, 1)),),
            )
        }
        HANDLERS["probe.v1"] = probe_handler
        problems = audit(probe)
        assert any("TVA_DEDUCTABIL" in p for p in problems), problems
    finally:
        # Discard only the probe roles. `clear()` used to be harmless because the
        # catalogue was empty; now it would wipe the real one for every test that
        # runs afterwards -- and those would pass, because an empty catalogue
        # checks nothing. A test that leaves a guard disabled behind it is worse
        # than the defect it was written for.
        reg.ACCOUNT_ROLES.difference_update({"TVA_DEDUCTIBIL", "DATORII_FURNIZORI"})


def test_a_known_role_passes() -> None:
    reg.ACCOUNT_ROLES.update({"TVA_DEDUCTIBIL"})
    try:
        HANDLERS["probe.v1"] = probe_handler
        probe = {
            "purchases.invoice_received": EventType(
                "purchases.invoice_received",
                (),
                account_roles=("TVA_DEDUCTIBIL",),
                handlers=(HandlerVersion("probe.v1", date(2020, 1, 1)),),
            )
        }
        assert audit(probe) == []
    finally:
        # Discard only the probe roles. `clear()` used to be harmless because the
        # catalogue was empty; now it would wipe the real one for every test that
        # runs afterwards -- and those would pass, because an empty catalogue
        # checks nothing. A test that leaves a guard disabled behind it is worse
        # than the defect it was written for.
        reg.ACCOUNT_ROLES.difference_update({"TVA_DEDUCTIBIL", "DATORII_FURNIZORI"})


@contextmanager
def empty_catalogue() -> Iterator[None]:
    """The catalogue as it was before `slots` existed, constructed on purpose.

    These two tests assert what the boot check does **while nothing has filled
    `ACCOUNT_ROLES`** -- that it says which roles it could not verify instead of
    passing quietly. That state used to be the default and is now a state the
    application leaves behind at startup, so the tests build it rather than
    happening to find it. A test that silently changed meaning when the catalogue
    arrived would be worse than one that failed.
    """
    saved = set(reg.ACCOUNT_ROLES)
    reg.ACCOUNT_ROLES.clear()
    try:
        yield
    finally:
        reg.ACCOUNT_ROLES.update(saved)


def test_an_empty_catalogue_checks_nothing() -> None:
    """Deliberate, and the same choice the type registry makes.

    The catalogue is populated by the module that binds roles to accounts, which
    A guard that refused every registration while the catalogue was empty would
    have been switched off before it ever caught anything.

    **The module that fills it now exists** -- `accounting.slots` registers its
    vocabulary at startup. So the empty state is built here rather than asserted
    globally: the old line said "nothing has filled this yet", which was a fact
    about the codebase and has stopped being true. What has to keep holding is the
    behaviour, not the emptiness.
    """
    HANDLERS["probe.v1"] = probe_handler
    probe = {
        "purchases.invoice_received": EventType(
            "purchases.invoice_received",
            (),
            account_roles=("ANYTHING_AT_ALL",),
            handlers=(HandlerVersion("probe.v1", date(2020, 1, 1)),),
        )
    }
    with empty_catalogue():
        assert audit(probe) == []

    # And with the real catalogue in place it is caught, which is the half that
    # only became testable when the catalogue arrived.
    assert any("ANYTHING_AT_ALL" in problem for problem in audit(probe))


def test_an_empty_catalogue_says_which_roles_it_could_not_check() -> None:
    """Not a failure, and not silent either.

    "Passes while the catalogue is empty" is the shape of every defect found in
    this codebase today: green because nothing shouted. A reader of the startup
    log has to be able to tell "the check ran and passed" from "the check could
    not run", and those are identical unless one of them says so.
    """
    HANDLERS["probe.v1"] = probe_handler
    probe = {
        "purchases.invoice_received": EventType(
            "purchases.invoice_received",
            (),
            account_roles=("TVA_DEDUCTIBIL", "DATORII_FURNIZORI"),
            handlers=(HandlerVersion("probe.v1", date(2020, 1, 1)),),
        )
    }
    with empty_catalogue():
        assert audit(probe) == []
        assert reg.unverified_roles(probe) == {"TVA_DEDUCTIBIL", "DATORII_FURNIZORI"}


def test_a_filled_catalogue_leaves_nothing_unverified() -> None:
    """The control. Without it, `unverified_roles` could return everything always
    and the test above would still pass.
    """
    reg.ACCOUNT_ROLES.update({"TVA_DEDUCTIBIL"})
    try:
        probe = {
            "purchases.invoice_received": EventType(
                "purchases.invoice_received", (), account_roles=("TVA_DEDUCTIBIL",)
            )
        }
        assert reg.unverified_roles(probe) == set()
    finally:
        # Discard only the probe roles. `clear()` used to be harmless because the
        # catalogue was empty; now it would wipe the real one for every test that
        # runs afterwards -- and those would pass, because an empty catalogue
        # checks nothing. A test that leaves a guard disabled behind it is worse
        # than the defect it was written for.
        reg.ACCOUNT_ROLES.difference_update({"TVA_DEDUCTIBIL", "DATORII_FURNIZORI"})


def test_the_boot_check_warns_rather_than_passing_quietly(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The disclosure reaches a log, which is where somebody will read it."""
    register(
        EventType(
            name="purchases.invoice_received",
            payload_fields=(),
            account_roles=("TVA_DEDUCTIBIL",),
            handlers=(HandlerVersion("probe.v1", date(2020, 1, 1)),),
        )
    )
    HANDLERS["probe.v1"] = probe_handler
    # Named explicitly: Django's logging configuration can leave the root logger
    # without a handler, and `at_level` alone then captures nothing -- a test
    # that would pass on a warning nobody emits.
    with (
        empty_catalogue(),
        caplog.at_level("WARNING", logger="evidenta.accounting.events.registry"),
    ):
        check_registry()
    assert "TVA_DEDUCTIBIL" in caplog.text
    assert "unverified" in caplog.text
