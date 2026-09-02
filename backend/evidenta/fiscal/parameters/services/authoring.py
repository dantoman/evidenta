"""Writing a fiscal parameter and turning it live -- the one door for both callers.

Two things write `fiscal_parameter`: the file loader an operator runs from a shell
(`load_fiscal_parameters`, `activate_fiscal_parameters`) and, since ADR-076, the
console's screen. They used to be one caller, so the rules lived in the command.
With a second caller they would have been copied, and two copies of "an active
value is never edited" drift the first time one of them learns a new field.

So the rules are here and both doors call them. What stays in each door is the
door's own shape: the file's `[[act]]` references and its `value` check
("approving the file must not approve something else"), the request's
serializer and its permission class. Neither knows which connection the other
uses -- both pass `using`, and both run inside `privileged_run` (`P-4`), which is
what writes the log row.

The rules, restated once (`R15`, `OD-92`, amendment D.1):

* every parameter names its act, and the act carries the date it entered into
  force -- "the rate was 20%" is not an answer without "under which act, from
  when";
* nothing goes live from a write: rows arrive `draft`, and activation is a
  separate act by a named approver;
* an active value and the margin that dates it are never edited -- a new claim is
  a new row with its own `valid_from`;
* a margin that is present says what establishes it; a margin that is absent says
  why, and a row without a margin cannot be activated, because the resolver could
  never select it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Literal

from evidenta.fiscal.parameters.models import (
    FiscalParameter,
    FiscalParameterSource,
    MarginBasis,
    ParameterScope,
    ParameterStatus,
    SourceConfidence,
    ValueType,
)
from evidenta.platform.legislation.services.registry import Act, register_act


class AuthoringError(Exception):
    """A write refused by the rules above. ``code`` is stable (C10)."""

    code = "fiscal.parameter_invalid"
    status = 400


class ParameterInvalidError(AuthoringError):
    """The claim is incomplete: no act, no effective date, a margin without its basis."""


class ActiveNotEditedError(AuthoringError):
    """The write would change an active value or the margin that dates it."""

    code = "fiscal.active_not_edited"
    status = 409


class ParameterNotFoundError(AuthoringError):
    code = "fiscal.parameter_not_found"
    status = 404


class MarginMissingError(AuthoringError):
    """Activation asked for a row whose margin was never established (OD-92)."""

    code = "fiscal.margin_missing"
    status = 409


class NotADraftError(AuthoringError):
    code = "fiscal.not_a_draft"
    status = 409


@dataclass(frozen=True, slots=True)
class ParameterDraft:
    """One claim about the law, as a caller states it.

    ``act`` is where the value was **read**; ``margin_act`` is whose final article
    **dates** it, when that is a different act (the ordinary case for amendments)
    -- absent, the value's act is taken to carry its own margin.
    """

    key: str
    value_type: str
    value: Any
    act: Act
    unit: str | None = None
    scope: str = ParameterScope.GLOBAL
    scope_ref: uuid.UUID | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    margin_basis: str | None = None
    margin_reference: str | None = None
    margin_act: Act | None = None
    observed_in: str | None = None
    confidence: str = SourceConfidence.PROVISIONAL
    provisional_reason: str | None = None


Outcome = Literal["created", "updated", "unchanged"]


@dataclass(frozen=True, slots=True)
class Written:
    outcome: Outcome
    row: FiscalParameter


#: What may not change on an active row -- the value and the margin that dates
#: it. The provenance fields are here for the reason `OD-92` exists: a margin is
#: defensible only if what establishes it can be read back unchanged, and a
#: citation edited in place after activation leaves the row claiming a source it
#: no longer has, with no new row and no history to show the swap.
PROTECTED_WHEN_ACTIVE = frozenset(
    {"value", "value_type", "unit", "margin_basis", "margin_act", "margin_reference"}
)


def register_source(act: Act, *, using: str) -> FiscalParameterSource:
    """The source row for an act, created or brought up to date.

    Refuses an act with no ``effective_from``: the act is recorded in the
    registry regardless -- a citation is a citation -- but no parameter can hang
    off it until the date it entered into force is known.
    """
    registry_row = register_act(act, using=using)
    if act.effective_from is None:
        raise ParameterInvalidError(
            f"act {act.act_type} {act.act_number} din {act.act_date} has no `effective_from`. "
            f"R15 wants the date the act entered into force; a value without it cannot be "
            f"defended"
        )
    source, _ = FiscalParameterSource.objects.using(using).update_or_create(
        act_type=act.act_type,
        act_number=act.act_number,
        act_date=act.act_date,
        defaults={
            "effective_from": act.effective_from,
            "url": act.url,
            "notes": act.notes,
            "act": registry_row,
        },
    )
    return source


def write_parameter(draft: ParameterDraft, *, using: str) -> Written:
    """Write one claim as a draft, or bring the matching draft up to date.

    Matched on ``(key, scope, scope_ref, valid_from)``; a second identical write
    changes nothing and says so. A caller that means a *different* value from the
    same date on an active row is refused -- that is a new row with a new margin,
    and it is a decision, not a write.
    """
    key = draft.key.strip()
    if not key:
        raise ParameterInvalidError("a parameter has no `key`")
    if draft.value_type not in ValueType.values:
        raise ParameterInvalidError(
            f"parameter {key!r}: value_type {draft.value_type!r} is not one of {ValueType.values}"
        )
    if draft.scope not in ParameterScope.values:
        raise ParameterInvalidError(
            f"parameter {key!r}: scope {draft.scope!r} is not one of {ParameterScope.values}"
        )
    if draft.confidence not in SourceConfidence.values:
        raise ParameterInvalidError(
            f"parameter {key!r}: confidence {draft.confidence!r} is not one of "
            f"{SourceConfidence.values}"
        )
    reason = (draft.provisional_reason or "").strip() or None
    if draft.confidence == SourceConfidence.PROVISIONAL and reason is None:
        raise ParameterInvalidError(
            f"parameter {key!r}: a provisional value states what the inference rests on"
        )

    source = register_source(draft.act, using=using)

    # `OD-92`: the margin and the observation are two claims, kept apart. A
    # `valid_from` is a margin and may only be written with what establishes it;
    # a value whose margin was never read carries `observed_in` instead and stays
    # unresolvable -- the honest state rather than a date nobody can check.
    margin_act = None
    margin_basis = draft.margin_basis
    margin_reference = (draft.margin_reference or "").strip() or None
    if draft.valid_from is not None:
        if margin_basis not in MarginBasis.values:
            raise ParameterInvalidError(
                f"parameter {key!r}: a `valid_from` needs `margin_basis` "
                f"(`act` or `platform_convention`) -- OD-92"
            )
        if margin_reference is None:
            raise ParameterInvalidError(
                f"parameter {key!r}: a `valid_from` needs `margin_reference`, "
                f"the article or the ADR that establishes it -- OD-92"
            )
        if margin_basis == MarginBasis.ACT:
            margin_act = register_source(draft.margin_act or draft.act, using=using).act
    elif reason is None:
        raise ParameterInvalidError(
            f"parameter {key!r}: without a `valid_from` the row states why -- OD-92"
        )
    if (
        draft.valid_to is not None
        and draft.valid_from is not None
        and draft.valid_to <= draft.valid_from
    ):
        raise ParameterInvalidError(
            f"parameter {key!r}: `valid_to` {draft.valid_to} is not after `valid_from` "
            f"{draft.valid_from}"
        )

    fields: dict[str, Any] = {
        "value_type": draft.value_type,
        "value": draft.value,
        "unit": (draft.unit or "").strip() or None,
        "valid_to": draft.valid_to,
        "source": source,
        "source_confidence": draft.confidence,
        "provisional_reason": reason if draft.confidence == SourceConfidence.PROVISIONAL else None,
        "margin_basis": margin_basis if draft.valid_from is not None else None,
        "margin_act": margin_act,
        "margin_reference": margin_reference if draft.valid_from is not None else None,
        "observed_in": (draft.observed_in or "").strip() or None,
    }
    existing = (
        FiscalParameter.objects.using(using)
        .filter(
            parameter_key=key,
            scope=draft.scope,
            scope_ref=draft.scope_ref,
            valid_from=draft.valid_from,
        )
        .first()
    )
    if existing is None:
        row = FiscalParameter.objects.using(using).create(
            parameter_key=key,
            scope=draft.scope,
            scope_ref=draft.scope_ref,
            valid_from=draft.valid_from,
            status=ParameterStatus.DRAFT,
            **fields,
        )
        return Written("created", row)

    changed = {
        name: value
        for name, value in fields.items()
        if _stored(existing, name) != _incoming(name, value)
    }
    if not changed:
        return Written("unchanged", existing)
    if existing.status == ParameterStatus.ACTIVE and (PROTECTED_WHEN_ACTIVE & set(changed)):
        touched = sorted(PROTECTED_WHEN_ACTIVE & set(changed))
        raise ActiveNotEditedError(
            f"parameter {key!r} valid from {draft.valid_from} is active; the write changes "
            f"{touched}. An active value and the margin that dates it are not edited "
            f"(R15, OD-92): a new claim is a new row with its own valid_from"
        )
    for name, value in changed.items():
        setattr(existing, name, value)
    existing.save(using=using, update_fields=[*changed, "updated_at"])
    return Written("updated", existing)


def _stored(row: FiscalParameter, name: str) -> Any:
    if name in ("source", "margin_act"):
        return getattr(row, name + "_id")
    return getattr(row, name)


def _incoming(name: str, value: Any) -> Any:
    if name in ("source", "margin_act"):
        return None if value is None else value.pk
    return value


@dataclass(frozen=True, slots=True)
class Activated:
    outcome: Literal["activated", "already_active"]
    row: FiscalParameter


def activate_parameter(parameter_id: uuid.UUID, *, approver: uuid.UUID, using: str) -> Activated:
    """Turn a draft live, as ``approver`` -- the practising accountant's act.

    Only a draft is activated; an active row is left alone and reported as such,
    so a second click and a second run of the command are the same non-event. A
    row whose margin was never established is refused **by name**: the resolver
    filters `valid_from <= date`, which a NULL never satisfies, so activating it
    would be an approval that approves nothing -- and it would read as done.
    """
    row = FiscalParameter.objects.using(using).filter(pk=parameter_id).first()
    if row is None:
        raise ParameterNotFoundError(f"parameter {parameter_id} is not loaded")
    return activate_row(row, approver=approver, using=using)


def activate_row(row: FiscalParameter, *, approver: uuid.UUID, using: str) -> Activated:
    """The activation itself, on a row the caller has already found and checked."""
    if row.valid_from is None:
        raise MarginMissingError(
            f"parameter {row.parameter_key!r} has no margin: the row carries "
            f"`observed_in`, not `valid_from`, because the article that sets the "
            f"date has not been read (OD-92). Activating it would approve a value "
            f"the resolver can never select -- an approval that approves nothing. "
            f"Read the final article of the modifying act, write `valid_from` with "
            f"`margin_basis` and `margin_reference`, then activate."
        )
    if row.status == ParameterStatus.ACTIVE:
        return Activated("already_active", row)
    if row.status != ParameterStatus.DRAFT:
        raise NotADraftError(
            f"parameter {row.parameter_key!r} is {row.status}; only a draft is activated here"
        )
    row.status = ParameterStatus.ACTIVE
    row.approved_by_user_id = approver
    row.approved_at = datetime.now(tz=UTC)
    row.save(
        using=using,
        update_fields=["status", "approved_by_user_id", "approved_at", "updated_at"],
    )
    return Activated("activated", row)
