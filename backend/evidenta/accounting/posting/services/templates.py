"""Templates for typical operations -- F1.7.3, ADR-036 section 8.

    "Absorb presiunea de personalizare, fara divergenta semantica."

The whole of this module is one sentence long: **a template is expanded into the
payload of a manual note, and that payload is handed to `post_manual_entry`.**
There is no second write, no second event type, no second set of invariants, and
no branch in the engine that knows a template exists. `post_from_template` is
`payload_for` followed by `post_manual_entry`, and if it ever grows a third step
the boundary this task exists to hold has moved.

**The property, stated so it can be falsified.** Everything a template can express
is expressible in a hand-typed payload -- and strictly less, because a template
line carries no date and no currency. So the set of postings reachable through
templates is a subset of the set reachable by hand. A template that could produce
a posting a person cannot produce would be a second engine, which is the failure
ADR-036 sections 1.1 and 10 are about: 1C's posting layer is code that each
partner edits per client, and the cost is not the editing, it is the divergence.

**No accounting judgement is made here, deliberately.** Not whether the account
exists, not whether it may receive a posting, not whether the lines balance, not
whether the period is open, not whether a required dimension is missing. Every one
of those has a date in it and an answer that changes over time, and the engine
answers them at the moment of posting, once. What this module validates is the
*shape* of what it stores and of what it was handed -- which is what a form
validates -- and every accounting refusal reaches the caller with the same stable
code a hand-typed note would have got. There are tests for that, one per refusal.

**Why there is no arithmetic.** ADR-036 section 8 says "formule simple de suma".
An amount here is a fixed number or a number the person types; there is no
multiplier and therefore no product, no fraction, and no rounding. A template that
computed 20% of a base would be *deciding* `DNB-08` -- open, and blocking ADR-037
-- inside a shortcut, and the decision would arrive in the ledger before anyone
noticed it had been taken. The refusal is narrow and removable: when the rounding
convention exists, a computed amount is a new kind of amount source, and the
templates already defined keep meaning what they meant.

**Why a missing input is refused rather than defaulted to zero.** A zero line is
refused by invariant 5 anyway, so the defaulted note would fail -- but it would
fail with "zero amount on line 2" instead of "you did not fill in `suma`", and the
person would look at the second line rather than at the form.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.db import transaction

from evidenta.accounting.coa.dimensions import DIMENSION_KEYS
from evidenta.accounting.posting.models import (
    OperationTemplate,
    OperationTemplateDimension,
    OperationTemplateLine,
    Side,
)
from evidenta.accounting.posting.services.manual import ManualEntryResult, post_manual_entry
from evidenta.platform.api.errors import ApiError
from evidenta.platform.audit.services.recording import record

#: The scale of `journal_line.debit` and `.credit`. A fixed amount with a fifth
#: decimal would be rounded silently on the way in, and which way it rounds is
#: `DNB-08` -- so it is refused when the template is written, not when it is used.
SCALE = 4

#: An input name is a key, not a label: lowercase, `snake_case`, stable. The label
#: a person sees is interface (layer 0 of ADR-036) and lives in a resource file
#: (C32), never in this column.
INPUT_KEY = re.compile(r"^[a-z][a-z0-9_]*$")

#: The side of the line that carries no amount. Written as the string a person
#: would type, because the payload this module produces has to be indistinguishable
#: from one that was typed.
ZERO = "0"


# --- refusals (C10) ----------------------------------------------------------
#
# `ApiError` directly, not `PostingRefusedError`: nothing here refuses a posting.
# These are refusals about a shortcut and about a form -- the engine's own
# refusals reach the caller unchanged, which is the point.


class TemplateNotFoundError(ApiError):
    """No such template in this context.

    Covers "no such id", "not this company's" and "retired" without saying which,
    for the reason `coa` gives for the same answer: a message that distinguished
    them would confirm the existence of another company's row.
    """

    code = "posting.template_not_found"
    status = 404


class TemplateNameTakenError(ApiError):
    code = "posting.template_name_taken"
    status = 409


class TemplateMalformedError(ApiError):
    """The definition is not a set of lines that can be stored as given."""

    code = "posting.template_malformed"
    status = 400


class TemplateUnknownDimensionError(ApiError):
    """A dimension name outside the closed vocabulary of ADR-029."""

    code = "posting.template_unknown_dimension"
    status = 400


class TemplateAmountNotStorableError(ApiError):
    """A fixed amount the ledger's column cannot hold exactly."""

    code = "posting.template_amount_not_storable"
    status = 400


class TemplateInputMissingError(ApiError):
    code = "posting.template_input_missing"
    status = 400


class TemplateInputUnexpectedError(ApiError):
    """A value was supplied under a name the template does not use.

    Refused rather than ignored. A typed name that nothing reads is the failure
    mode where the person believes they set an amount and the note is posted
    without it -- and the note balances, because the template's other line used
    the name that was spelled correctly.
    """

    code = "posting.template_input_unexpected"
    status = 400


class TemplateInputInvalidError(ApiError):
    """An input value that is not text.

    The payload is stored as `jsonb` and fingerprinted for idempotency, so a value
    that cannot be written to JSON has no stable form. A `float` is refused for the
    same reason `post_manual_entry` refuses one: 0.1 is not a tenth in binary. The
    numeric judgement itself stays with the engine -- this is a serialisation
    check, not a parse.
    """

    code = "posting.template_input_invalid"
    status = 400


# --- what a template is made of ----------------------------------------------


@dataclass(frozen=True, slots=True)
class FromInput:
    """The value is typed by the person using the template, under this name.

    A marker rather than a string, so that "the amount is 500" and "the amount is
    whatever is typed under `suma`" cannot be confused at a call site -- and so
    that the exclusive pair of columns behind it is unreachable from here.
    """

    key: str


@dataclass(frozen=True, slots=True)
class TemplateLine:
    """One journal line a template proposes, in the caller's terms."""

    account_id: uuid.UUID
    side: str
    amount: Decimal | FromInput
    description: str | None = None
    dimensions: Mapping[str, uuid.UUID | FromInput] = field(default_factory=dict)


# --- defining and editing ----------------------------------------------------


@transaction.atomic
def define_template(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    name: str,
    entry_description: str,
    lines: Sequence[TemplateLine],
) -> OperationTemplate:
    """Store one typical operation. Returns the template.

    Layer 4 of ADR-036 is the client's own: this is a shortcut a company writes
    for itself, and nothing about it reaches another tenant or the product.
    """
    _check_definition(name=name, entry_description=entry_description, lines=lines)
    if OperationTemplate.objects.filter(company_id=company_id, name=name, is_active=True).exists():
        raise TemplateNameTakenError(
            f"this company already has a template called {name!r}; two shortcuts "
            f"with one name are picked from a list by guessing"
        )

    template = OperationTemplate.objects.create(
        tenant_id=tenant_id,
        company_id=company_id,
        name=name,
        entry_description=entry_description,
    )
    _write_lines(template, lines)
    _audit("operation_template.defined", template, new={"name": name, "lines": len(lines)})
    return template


@transaction.atomic
def redefine_template(
    template_id: uuid.UUID,
    *,
    company_id: uuid.UUID,
    name: str,
    entry_description: str,
    lines: Sequence[TemplateLine],
) -> OperationTemplate:
    """Replace what the template says. The lines are the ones now given.

    Editing is free (ADR-036 section 3, layer 4) and it is safe for one reason
    worth being explicit about: the payload is expanded at the moment of use, and
    the ledger is append-only. An entry already posted cannot change because its
    template did -- the same guarantee section 6.4 gives for account bindings, and
    there is a test that walks it.
    """
    _check_definition(name=name, entry_description=entry_description, lines=lines)
    template = _editable(template_id, company_id)
    if (
        OperationTemplate.objects.filter(company_id=company_id, name=name, is_active=True)
        .exclude(id=template.id)
        .exists()
    ):
        raise TemplateNameTakenError(f"this company already has a template called {name!r}")

    old = {"name": template.name, "lines": _line_count(template)}
    template.name = name
    template.entry_description = entry_description
    template.save(update_fields=["name", "entry_description", "updated_at"])

    OperationTemplateDimension.objects.filter(line__template_id=template.id).delete()
    OperationTemplateLine.objects.filter(template_id=template.id).delete()
    _write_lines(template, lines)

    _audit(
        "operation_template.redefined",
        template,
        old=old,
        new={"name": name, "lines": len(lines)},
    )
    return template


@transaction.atomic
def set_template_active(
    template_id: uuid.UUID, *, company_id: uuid.UUID, active: bool
) -> OperationTemplate:
    """Retire a template, or bring it back. Deletion is not offered.

    The application role holds no DELETE on `operation_template`, so this is the
    only way out -- and it is the right one: a shortcut a company used for a year
    is part of how its register came to look the way it does.
    """
    template = _editable(template_id, company_id)
    if template.is_active == active:
        return template
    if (
        active
        and OperationTemplate.objects.filter(
            company_id=company_id, name=template.name, is_active=True
        ).exists()
    ):
        raise TemplateNameTakenError(
            f"a different template called {template.name!r} is in use; rename it "
            f"before bringing this one back"
        )

    template.is_active = active
    template.save(update_fields=["is_active", "updated_at"])
    _audit(
        "operation_template.reactivated" if active else "operation_template.retired",
        template,
        old={"is_active": not active},
        new={"is_active": active},
    )
    return template


def _write_lines(template: OperationTemplate, lines: Sequence[TemplateLine]) -> None:
    for number, line in enumerate(lines, start=1):
        stored = OperationTemplateLine.objects.create(
            tenant_id=template.tenant_id,
            company_id=template.company_id,
            template=template,
            line_number=number,
            account_id=line.account_id,
            side=line.side,
            fixed_amount=line.amount if isinstance(line.amount, Decimal) else None,
            input_key=line.amount.key if isinstance(line.amount, FromInput) else None,
            description=line.description,
        )
        for dimension, value in line.dimensions.items():
            OperationTemplateDimension.objects.create(
                tenant_id=template.tenant_id,
                company_id=template.company_id,
                line=stored,
                dimension=dimension,
                fixed_value_id=value if isinstance(value, uuid.UUID) else None,
                input_key=value.key if isinstance(value, FromInput) else None,
            )


# --- reading -----------------------------------------------------------------


def inputs_of(template_id: uuid.UUID, *, company_id: uuid.UUID) -> tuple[str, ...]:
    """The names a form has to ask for, in the order the lines mention them.

    Derived from the lines rather than declared in a table of its own: two places
    saying which inputs a template has is one place too many, and the one that
    drifts is the one nothing reads at expansion.
    """
    template = _template(template_id, company_id)
    return _required_inputs(_lines_of(template))


def payload_for(
    template_id: uuid.UUID,
    *,
    company_id: uuid.UUID,
    inputs: Mapping[str, Any],
    description: str | None = None,
) -> dict[str, Any]:
    """The manual-note payload this template plus these inputs come to.

    Separate from posting on purpose: this is what lets an interface show the
    person the lines *before* they are posted -- which is the reason ADR-036
    section 8 calls templates safe. "Nota manuala e scrisa si verificata de un om
    inainte de postare" is a property of the workflow, and a workflow cannot have
    it if the only way to see the note is to post it.
    """
    template = _template(template_id, company_id)
    return _expand(template, inputs=inputs, description=description)


def post_from_template(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    template_id: uuid.UUID,
    accounting_date: date,
    functional_currency: str,
    note_id: uuid.UUID,
    inputs: Mapping[str, Any],
    idempotency_key: str,
    actor_user_id: uuid.UUID,
    request_id: str,
    capability_snapshot: dict[str, Any],
    description: str | None = None,
    occurred_at: datetime | None = None,
) -> ManualEntryResult:
    """Expand the template and post the note. Two steps, and the second is the engine.

    Every argument that is not the template or its inputs is passed straight
    through, because they are the manual note's arguments and this is a manual
    note. In particular there is **no way to name a source document**: the event is
    recorded with `manual` / `manual_journal_note` by `post_manual_entry` itself,
    so a template cannot be pointed at an invoice. That is ADR-036 section 8's
    "nu pot fi folosite pentru postarea automata a documentelor", held by the
    signature rather than by a check that could be argued with.
    """
    return post_manual_entry(
        tenant_id=tenant_id,
        company_id=company_id,
        accounting_date=accounting_date,
        functional_currency=functional_currency,
        note_id=note_id,
        payload=payload_for(
            template_id, company_id=company_id, inputs=inputs, description=description
        ),
        idempotency_key=idempotency_key,
        actor_user_id=actor_user_id,
        request_id=request_id,
        capability_snapshot=capability_snapshot,
        occurred_at=occurred_at,
    )


# --- expansion ---------------------------------------------------------------


def _expand(
    template: OperationTemplate,
    *,
    inputs: Mapping[str, Any],
    description: str | None,
) -> dict[str, Any]:
    lines = _lines_of(template)
    values = _checked_inputs(_required_inputs(lines), inputs)

    payload_lines: list[dict[str, Any]] = []
    for line in lines:
        amount = values[line.input_key] if line.input_key is not None else _text(line.fixed_amount)
        entry: dict[str, Any] = {
            "account_id": str(line.account_id),
            "debit": amount if line.side == Side.DEBIT else ZERO,
            "credit": amount if line.side == Side.CREDIT else ZERO,
        }
        if line.description is not None:
            entry["description"] = line.description
        dimensions = {
            item.dimension: (
                values[item.input_key] if item.input_key is not None else str(item.fixed_value_id)
            )
            for item in line.dimensions.all()
        }
        if dimensions:
            entry["dimensions"] = dimensions
        payload_lines.append(entry)

    return {
        "description": description if description is not None else template.entry_description,
        "lines": payload_lines,
    }


def _text(amount: Decimal | None) -> str:
    """A fixed amount, as the string a person would have typed.

    `str` of the stored value, never re-quantised: the column is `numeric(20,4)`
    and gives back what it holds, so 500 comes back as `500.0000` every time. A
    module that trimmed it would be choosing a presentation for the register, and
    the presentation of an amount is not this module's decision.
    """
    return str(amount)


def _required_inputs(lines: Sequence[OperationTemplateLine]) -> tuple[str, ...]:
    """Every name the lines mention, in order of first appearance, once each."""
    seen: dict[str, None] = {}
    for line in lines:
        # `is not None`, not truthiness: the pair of columns is exclusive by CHECK,
        # so an empty string is a *set* key, and treating it as unset here would
        # make the expansion look for a value nothing asked for.
        if line.input_key is not None:
            seen.setdefault(line.input_key, None)
        for item in line.dimensions.all():
            if item.input_key is not None:
                seen.setdefault(item.input_key, None)
    return tuple(seen)


def _checked_inputs(required: Sequence[str], given: Mapping[str, Any]) -> dict[str, str]:
    missing = sorted(set(required) - set(given))
    if missing:
        raise TemplateInputMissingError(
            f"this template asks for {', '.join(missing)}, and no value was given. "
            f"A note posted with a blank there would be refused for the wrong reason"
        )
    unexpected = sorted(set(given) - set(required))
    if unexpected:
        raise TemplateInputUnexpectedError(
            f"{', '.join(unexpected)} is not asked for by this template. A value "
            f"nothing reads is the one the person believes they set"
        )
    for key, value in given.items():
        if not isinstance(value, str):
            raise TemplateInputInvalidError(
                f"{key} is {type(value).__name__}. Values travel as text: the payload "
                f"is stored as JSON and fingerprinted, and a float is not exact"
            )
    return dict(given)


# --- loading -----------------------------------------------------------------


def _template(template_id: uuid.UUID, company_id: uuid.UUID) -> OperationTemplate:
    """A template that may be used. Retired ones are not visible to expansion."""
    template = OperationTemplate.objects.filter(
        id=template_id, company_id=company_id, is_active=True
    ).first()
    if template is None:
        raise TemplateNotFoundError(f"template {template_id} is not in use in this context")
    return template


def _editable(template_id: uuid.UUID, company_id: uuid.UUID) -> OperationTemplate:
    """A template that may be edited, retired or brought back."""
    template = OperationTemplate.objects.filter(id=template_id, company_id=company_id).first()
    if template is None:
        raise TemplateNotFoundError(f"template {template_id} is not visible in this context")
    return template


def _lines_of(template: OperationTemplate) -> list[OperationTemplateLine]:
    return list(
        OperationTemplateLine.objects.filter(template_id=template.id)
        .order_by("line_number")
        .prefetch_related("dimensions")
    )


def _line_count(template: OperationTemplate) -> int:
    return OperationTemplateLine.objects.filter(template_id=template.id).count()


# --- the definition, checked for shape ---------------------------------------


def _check_definition(*, name: str, entry_description: str, lines: Sequence[TemplateLine]) -> None:
    if not name.strip():
        raise TemplateMalformedError("a template needs a name; it is picked from a list")
    if not entry_description.strip():
        raise TemplateMalformedError(
            "a template needs the description its notes carry: a manual note is "
            "the only entry with no document behind it, and one without a sentence "
            "would be refused at posting every single time"
        )
    if not lines:
        raise TemplateMalformedError(
            "a template with no lines produces a note with no lines, which the "
            "engine refuses (invariant 5, and `posting.no_lines` before it)"
        )

    amount_keys: set[str] = set()
    dimension_keys: set[str] = set()
    for number, line in enumerate(lines, start=1):
        if line.side not in Side.values:
            raise TemplateMalformedError(
                f"line {number}: {line.side!r} is neither {Side.DEBIT} nor {Side.CREDIT}"
            )
        if isinstance(line.amount, FromInput):
            amount_keys.add(_check_key(line.amount.key, number))
        else:
            _check_amount(line.amount, number)

        unknown = sorted(set(line.dimensions) - set(DIMENSION_KEYS))
        if unknown:
            raise TemplateUnknownDimensionError(
                f"line {number}: {', '.join(unknown)} is not an analytical dimension. "
                f"The vocabulary is closed (ADR-029), and a name outside it would be "
                f"dropped on expansion, leaving a line that looks analysed"
            )
        for value in line.dimensions.values():
            if isinstance(value, FromInput):
                dimension_keys.add(_check_key(value.key, number))

    both = sorted(amount_keys & dimension_keys)
    if both:
        raise TemplateMalformedError(
            f"{', '.join(both)} is asked for as an amount and as an analytical "
            f"value. One string cannot be both a sum and a reference, and the form "
            f"would ask for it once"
        )


def _check_key(key: str, number: int) -> str:
    if not INPUT_KEY.match(key):
        raise TemplateMalformedError(
            f"line {number}: {key!r} is not an input name. Names are lowercase and "
            f"snake_case, because they are keys; what the person reads is a label, "
            f"and labels live in resource files (C32)"
        )
    return key


def _check_amount(amount: object, number: int) -> None:
    if not isinstance(amount, Decimal):
        raise TemplateMalformedError(
            f"line {number}: the amount is neither a decimal nor an input name"
        )
    if not amount.is_finite() or amount <= 0:
        raise TemplateAmountNotStorableError(
            f"line {number}: {amount} is not an amount a line can carry. A zero line "
            f"is refused by invariant 5 and a negative one by the ledger's own CHECK"
        )
    exponent = amount.as_tuple().exponent
    if isinstance(exponent, int) and -exponent > SCALE:
        raise TemplateAmountNotStorableError(
            f"line {number}: {amount} has more than {SCALE} decimals. The column "
            f"would round it silently, and which way it rounds is open (`DNB-08`)"
        )


def _audit(
    action: str,
    template: OperationTemplate,
    *,
    old: dict[str, Any] | None = None,
    new: dict[str, Any] | None = None,
) -> None:
    """Recorded from the service that made the change, explicitly -- never a signal (C4).

    A template is configuration a person edits, and the question asked later is
    the one row timestamps cannot answer: who changed the shortcut, and what did
    it say before.
    """
    record(
        action=action,
        entity_type="operation_template",
        entity_id=template.id,
        company_id=template.company_id,
        old_value=old,
        new_value=new,
    )
