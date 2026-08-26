"""Resolving the parameter in force on a date -- R17, R18.

This lives beside the table it reads rather than in the registry, and the split
is the point: `fiscal.registry` selects *implementations*, this selects *values*,
and a caller that needs both asks two public services. Putting one resolver in
the other's module would have made a service import another module's models --
`D6`, and the case the rule is actually aimed at.

Every function takes the date and none of them reads the clock. That is the
design, not caution: a resolver that could fall back to "today" would make
recalculating a closed period return this year's answer, and the mistake would be
silent and correct-looking.

**Zero matches or two are errors, never a choice.** Taking the newest, or the
first, answers a question the configuration cannot actually answer -- and in a
ledger a plausible wrong number is worse than a refusal, because it gets posted.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from django.db.models import Model, Q, QuerySet

from evidenta.fiscal.parameters.models import (
    FiscalParameter,
    FiscalParameterConfidenceEvent,
    ParameterScope,
    ParameterStatus,
    SourceConfidence,
)


class FiscalResolutionError(RuntimeError):
    """Nothing applies, or more than one does. Both are configuration errors."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def in_force[M: Model](rows: QuerySet[M], effective_date: date) -> QuerySet[M]:
    """Rows whose validity window contains the date. Half-open: ``[from, to)``.

    Public because `fiscal.registry` applies the same window to its own table and
    the two must not drift -- an inclusive `valid_to` in one of them and an
    exclusive one in the other would differ on exactly one day a year, which is
    the kind of defect that is found by a client rather than by a test.
    """
    return rows.filter(valid_from__lte=effective_date).filter(
        Q(valid_to__isnull=True) | Q(valid_to__gt=effective_date)
    )


def resolve_parameter(
    parameter_key: str,
    effective_date: date,
    *,
    scope_ref: uuid.UUID | None = None,
) -> FiscalParameter:
    """The parameter in force on ``effective_date``.

    A scoped value wins over the global one where it exists -- an entity whose own
    status changes the rule, not a preference. Both are matched against the same
    date.
    """
    active = FiscalParameter.objects.filter(
        parameter_key=parameter_key, status=ParameterStatus.ACTIVE
    )

    if scope_ref is not None:
        scoped = list(in_force(active.filter(scope_ref=scope_ref), effective_date))
        if len(scoped) > 1:
            raise FiscalResolutionError(
                "fiscal.ambiguous_parameter",
                f"{parameter_key!r} has {len(scoped)} scoped values in force on {effective_date}",
            )
        if scoped:
            return scoped[0]

    globals_ = list(in_force(active.filter(scope=ParameterScope.GLOBAL), effective_date))
    if not globals_:
        raise FiscalResolutionError(
            "fiscal.no_parameter",
            f"no active value for {parameter_key!r} on {effective_date}. A rate "
            f"that is missing is not a rate of zero.",
        )
    if len(globals_) > 1:
        raise FiscalResolutionError(
            "fiscal.ambiguous_parameter",
            f"{parameter_key!r} has {len(globals_)} global values in force on {effective_date}",
        )
    return globals_[0]


def confidence_at(parameter_id: uuid.UUID, at: datetime) -> str:
    """What `source_confidence` was at an instant, not what it is now.

    Answers the question an inspection asks -- *at the date you filed, what were
    you relying on?* -- which the column alone stops being able to answer the
    moment a value is confirmed.

    Raises rather than assuming when the history does not reach back that far. A
    parameter whose earliest recorded state is later than the instant asked about
    cannot say what it was before, and PROVISIONAL would be a guess dressed as an
    answer -- in the direction that looks prudent, which is exactly what makes it
    hard to notice.
    """
    event = (
        FiscalParameterConfidenceEvent.objects.filter(
            parameter_id=parameter_id, effective_at__lte=at
        )
        .order_by("-effective_at", "-recorded_at")
        .first()
    )
    if event is None:
        raise FiscalResolutionError(
            "fiscal.no_confidence_history",
            f"parameter {parameter_id} has no recorded confidence at or before {at}. "
            f"Its history does not reach back that far, and a default here would be "
            f"a guess about what someone relied on.",
        )
    return str(event.confidence)


def provisional_in_force(
    effective_date: date,
    *,
    parameter_keys: list[str] | None = None,
    as_known_at: datetime | None = None,
) -> list[FiscalParameter]:
    """Values in force on ``effective_date`` that were inferred rather than read.

    The question a compliance screen asks before a declaration is filed: is
    anything this calculation depends on still standing on an inference? Answering
    it afterwards is worth much less -- the declaration has been submitted by then.

    Returns rows, not a boolean, because "something is provisional" is not
    actionable and "the 2026 personal exemption is provisional, here is what the
    inference rests on" is. Ordering is by key so the same date always renders the
    same list.

    ``effective_date`` is the fiscal window; ``as_known_at`` is the instant the
    question is asked *about*. They are different axes and both matter: without
    the second, this reports today's beliefs about a past period, so once a value
    is confirmed it reports that nothing was ever provisional -- which is false
    about the filing and true only about now. Left at None it means "as things
    stand", which is the right default for the screen shown before filing.
    """
    rows = FiscalParameter.objects.filter(status=ParameterStatus.ACTIVE)
    if parameter_keys is not None:
        rows = rows.filter(parameter_key__in=parameter_keys)
    candidates = list(in_force(rows, effective_date).order_by("parameter_key", "valid_from"))

    if as_known_at is None:
        return [r for r in candidates if r.source_confidence == SourceConfidence.PROVISIONAL]

    return [
        r for r in candidates if confidence_at(r.id, as_known_at) == SourceConfidence.PROVISIONAL
    ]
