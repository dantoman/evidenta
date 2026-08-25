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
from datetime import date

from django.db.models import Q, QuerySet

from evidenta.fiscal.parameters.models import (
    FiscalParameter,
    ParameterScope,
    ParameterStatus,
)


class FiscalResolutionError(RuntimeError):
    """Nothing applies, or more than one does. Both are configuration errors."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def in_force[M](rows: QuerySet[M], effective_date: date) -> QuerySet[M]:
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
