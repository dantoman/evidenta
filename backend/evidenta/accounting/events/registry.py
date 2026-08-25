"""The `event_type` registry -- ADR-038, task F1.3.2.

The core owns the vocabulary; modules **register** their types rather than the
core listing them. That inversion is what keeps `D2` intact: `sales` calls
`accounting.events.register(...)`, so `accounting` never imports `sales`, and the
direction `operations -> accounting.events` is exactly what `D3` permits.

Two things live here and nowhere else.

**The handler table is code.** A registry row names a key in `HANDLERS`; it never
names an importable path. `fiscal_logic_version` is written through privileged
path P-4, so feeding that column to an import would turn one privileged INSERT
into arbitrary code execution in the application role -- and the dependency
guard, which walks the AST, cannot see a dynamic import at all. Measured at F0.9
on `accounting.money_rounding`; the same shape applies here.

**Selection is by the effective date of the period.** A type may have several
handlers with disjoint validity intervals, and which one runs is decided by
`accounting_date`, never by "the newest" and never by the emitter. That is R17,
and R18 -- recalculating a 2026 period in 2030 must use the 2026 treatment --
cannot hold any other way.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from itertools import pairwise
from typing import Any

#: Two segments, `snake_case` in the second -- the form Spec B section 1.4 uses:
#: `sales.invoice_issued`, not `sales.invoice.issued`. A second naming convention
#: inside a closed vocabulary means half the types are written wrong before
#: anybody notices.
NAME = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")


class RegistryError(RuntimeError):
    """A stable code, not only a message (C10)."""

    code = "accounting.registry_error"

    def __init__(self, message: str) -> None:
        super().__init__(f"{self.code}: {message}")


class DuplicateEventTypeError(RegistryError):
    code = "accounting.event_type_duplicate"


class MalformedEventTypeError(RegistryError):
    code = "accounting.event_type_malformed"


class UnknownEventTypeError(RegistryError):
    code = "accounting.event_type_unknown"


class NoHandlerError(RegistryError):
    code = "accounting.no_handler"


class AmbiguousHandlerError(RegistryError):
    code = "accounting.ambiguous_handler"


@dataclass(frozen=True, slots=True)
class HandlerVersion:
    """One treatment of one event type, over a date interval and a capability set.

    `implementation_ref` is a **key into `HANDLERS`**, not a dotted path. See the
    module docstring for why that distinction is the security property rather
    than a style choice.

    `requires` is **selection criteria, not a gate**, and the difference is what
    R26 asks for: "the same operation is accounted for differently according to
    the active capabilities". A gate would refuse when a capability is missing;
    criteria let two treatments of one event coexist on one date -- one for a
    VAT-registered company, one for a company that is not -- and let the profile
    choose between them. Spec B section 4 draws the resolution that way already.
    """

    implementation_ref: str
    valid_from: date
    valid_to: date | None = None
    #: Capability keys this treatment needs. Empty means it applies whatever the
    #: company has, which is the common case.
    requires: frozenset[str] = frozenset()

    def covers(self, on: date) -> bool:
        """`[valid_from, valid_to)` -- the same half-open window fiscal
        parameters use, so the two cannot disagree on a boundary day."""
        return self.valid_from <= on and (self.valid_to is None or on < self.valid_to)

    def applies_to(self, capabilities: frozenset[str]) -> bool:
        return self.requires <= capabilities


@dataclass(frozen=True, slots=True)
class EventType:
    name: str
    #: Field names the payload must carry. Checked at emission, not at posting:
    #: a payload missing a field would otherwise be stored successfully and fail
    #: in the engine, far from the caller that produced it.
    payload_fields: tuple[str, ...]
    #: Semantic slots the handler asks for -- never account codes (ADR-036 5.1).
    account_roles: tuple[str, ...] = ()
    handlers: tuple[HandlerVersion, ...] = ()
    description: str = ""


#: The registered vocabulary. Populated by modules at import of their AppConfig.
REGISTRY: dict[str, EventType] = {}

#: Handler implementations, declared in code. A registry entry selects from this
#: table; it never loads from anywhere.
HANDLERS: dict[str, Callable[..., Any]] = {}

#: The account roles a handler may ask for -- the catalogue ADR-038 section 5
#: point 3 requires the boot check to validate against.
#:
#: It existed as a promise and not as code: `EventType.account_roles` was free
#: text, so a typo became a role nothing could ever bind, discovered at posting
#: rather than at startup. Registered by the module that owns the binding of
#: roles to accounts, on the same pattern as `HANDLERS` -- declared in code, never
#: loaded from a row.
#:
#: **Empty means "do not check".** A catalogue nobody has filled yet must not
#: refuse every registration; the same choice the type registry makes, and for the
#: same reason -- a guard that fires before the thing it guards exists teaches
#: people to switch it off.
ACCOUNT_ROLES: set[str] = set()

#: Types deprecated: no longer emittable, handlers kept so history stays
#: interpretable. There is no "deleted" -- a type ever emitted stays for good.
DEPRECATED: set[str] = set()


def register(event_type: EventType) -> EventType:
    if not NAME.match(event_type.name):
        raise MalformedEventTypeError(
            f"{event_type.name!r} is not `<domain>.<action>` in snake_case, the "
            f"form Spec B section 1.4 fixes"
        )
    if event_type.name in REGISTRY:
        raise DuplicateEventTypeError(
            f"{event_type.name!r} is already registered. A closed vocabulary with "
            f"two entries for one name is a vocabulary that answers differently "
            f"depending on import order."
        )
    REGISTRY[event_type.name] = event_type
    return event_type


def deprecate(name: str) -> None:
    """Stop new emissions; keep every handler.

    Not a deletion. A type that was ever emitted is referenced by rows in an
    append-only ledger, and its handlers are what make those rows readable years
    later.
    """
    if name not in REGISTRY:
        raise UnknownEventTypeError(name)
    DEPRECATED.add(name)


def resolve_handler(
    name: str, accounting_date: date, capabilities: frozenset[str]
) -> Callable[..., Any]:
    """The handler in force for that period and that company -- R17, R18, R26.

    `capabilities` has no default, deliberately. R26 requires the profile to be
    an **explicit input** to the Posting Engine, and a default of "none" would
    silently pick the treatment for a company without VAT, while a default of
    "all" would pick the one for a company that has it. Both are plausible wrong
    answers, which is the worst kind in a ledger.

    Zero matches or two are errors, never a choice. Taking the newest would
    answer a question the registration cannot actually answer, and a plausible
    wrong treatment is worse than a refusal, because it posts.
    """
    try:
        event_type = REGISTRY[name]
    except KeyError:
        raise UnknownEventTypeError(
            f"{name!r} is not registered. The vocabulary is closed: a module "
            f"registers its types, it does not emit arbitrary ones."
        ) from None

    on_date = [h for h in event_type.handlers if h.covers(accounting_date)]
    applicable = [h for h in on_date if h.applies_to(capabilities)]

    # The most specific treatment wins, and without this a registration cannot be
    # written at all: a handler with no requirements is satisfied by every
    # profile, so it would collide with every specialised one. Same rule as
    # `fiscal.parameters.resolve_parameter`, where a scoped value beats the
    # global one -- an entity whose own status changes the treatment, not a
    # preference.
    #
    # "Most specific" means: no other applicable handler requires a strict
    # superset. Two maximal handlers with incomparable requirements -- one
    # needing VAT, another needing inventory -- are left as an ambiguity rather
    # than ordered by some tiebreak, because there is no reading of the
    # registration that says which should win.
    matches = [
        h for h in applicable if not any(other.requires > h.requires for other in applicable)
    ]

    if not matches:
        # The two failures are told apart on purpose. "No treatment for this
        # period" is a registration gap, closed by a deployment. "Treatments
        # exist but need capabilities this company lacks" is a tenant
        # configuration question, and sending somebody to the wrong one of those
        # costs an afternoon.
        if on_date:
            needed = sorted({c for h in on_date for c in h.requires} - capabilities)
            raise NoHandlerError(
                f"{name!r} has treatments on {accounting_date}, none applying to "
                f"this company's capabilities. Missing: {', '.join(needed)}."
            )
        raise NoHandlerError(
            f"no handler for {name!r} on {accounting_date}. A type with no "
            f"treatment for the period being posted has no safe default."
        )
    if len(matches) > 1:
        raise AmbiguousHandlerError(
            f"{name!r} has {len(matches)} handlers covering {accounting_date} for "
            f"these capabilities; the newest is not the answer, the registration "
            f"is wrong"
        )

    ref = matches[0].implementation_ref
    try:
        return HANDLERS[ref]
    except KeyError:
        raise NoHandlerError(
            f"{name!r} names implementation {ref!r}, which this build does not "
            f"contain. A registration selects an implementation; it never "
            f"imports one."
        ) from None


# --- The boot check ----------------------------------------------------------


def audit(registry: Mapping[str, EventType] | None = None) -> list[str]:
    """Everything wrong with the registered vocabulary, as messages.

    Returns rather than raises, so one run reports every problem instead of the
    first. The caller decides whether that is fatal -- see `check_registry`.

    Takes the registry as a parameter so the checks have probes that can fail
    without touching the real vocabulary. A guard nobody has seen refuse is a
    guard whose shape nobody knows.
    """
    registry = REGISTRY if registry is None else registry
    problems: list[str] = []

    for name, event_type in sorted(registry.items()):
        if not NAME.match(name):
            problems.append(f"{name}: not `<domain>.<action>` in snake_case")
        if not event_type.handlers:
            problems.append(
                f"{name}: registered with no handler. A type that can be emitted "
                f"and not posted is a document that goes missing silently."
            )
        if ACCOUNT_ROLES:
            unknown = sorted(set(event_type.account_roles) - ACCOUNT_ROLES)
            if unknown:
                problems.append(
                    f"{name}: asks for account role(s) {', '.join(unknown)}, which "
                    f"are not in the catalogue. A role nothing can bind is a "
                    f"posting that fails on a live document."
                )

        for handler in event_type.handlers:
            if handler.implementation_ref not in HANDLERS:
                problems.append(
                    f"{name}: handler {handler.implementation_ref!r} is not in "
                    f"HANDLERS; this build cannot run it"
                )
            if handler.valid_to is not None and handler.valid_to <= handler.valid_from:
                problems.append(
                    f"{name}: handler {handler.implementation_ref!r} has an empty validity interval"
                )
        problems.extend(_interval_problems(name, event_type.handlers))

    return problems


def _interval_problems(name: str, handlers: tuple[HandlerVersion, ...]) -> list[str]:
    """Overlaps and gaps between the handlers of one type.

    Both matter, and for different reasons. An overlap makes `resolve_handler`
    refuse at posting time -- so the misconfiguration reaches somebody closing a
    month who cannot fix it. A gap is worse: it is silent until a document falls
    into it, which may be years after the registration was written.

    **Grouped by capability requirement**, and that grouping is the consequence
    of R26 the request for `requires` did not name. Two treatments covering the
    same day for different capability sets are not an overlap -- they are exactly
    what "the same operation is accounted for differently according to the active
    capabilities" means. Checking them together would report the correct
    registration as broken, which is how a guard teaches people to ignore it.

    The cost of the grouping is real and is accepted: a gap is only detected
    within one capability set, so a period covered for VAT-registered companies
    and uncovered for the rest is not reported here. Catching that needs the set
    of capability combinations that actually occur, which the registry does not
    know -- it is a question for the engine, against real tenants.
    """
    problems: list[str] = []
    by_requirement: dict[frozenset[str], list[HandlerVersion]] = {}
    for handler in handlers:
        by_requirement.setdefault(handler.requires, []).append(handler)
    for group in by_requirement.values():
        problems.extend(_ordered_problems(name, group))
    return problems


def _ordered_problems(name: str, handlers: list[HandlerVersion]) -> list[str]:
    problems: list[str] = []
    ordered = sorted(handlers, key=lambda h: h.valid_from)
    for earlier, later in pairwise(ordered):
        if earlier.valid_to is None:
            problems.append(
                f"{name}: handler {earlier.implementation_ref!r} is open-ended and "
                f"is followed by {later.implementation_ref!r} -- they overlap for "
                f"good"
            )
        elif earlier.valid_to > later.valid_from:
            problems.append(
                f"{name}: handlers {earlier.implementation_ref!r} and "
                f"{later.implementation_ref!r} overlap"
            )
        elif earlier.valid_to < later.valid_from:
            problems.append(
                f"{name}: a gap between {earlier.implementation_ref!r} and "
                f"{later.implementation_ref!r} -- {earlier.valid_to} to "
                f"{later.valid_from}. Silent until a document falls into it."
            )
    return problems


class RegistryInvalidError(RuntimeError):
    """The registered vocabulary cannot be served."""


def check_registry() -> None:
    """Raise if the vocabulary is unserviceable.

    **Called from CI and from the startup of processes that serve requests --
    deliberately not from `AppConfig.ready()`.** There, every `manage.py` command
    fails including `migrate`, so a deploy that lands code with a missing handler
    could not run the migration that fixes it. ADR-038 section 5.
    """
    problems = audit()
    if problems:
        raise RegistryInvalidError(
            "the event_type registry is not serviceable:\n  " + "\n  ".join(problems)
        )
