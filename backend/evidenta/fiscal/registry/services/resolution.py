"""Selecting the implementation in force on a date -- R17, R18.

The registry answers "which code runs for this period", `fiscal.parameters`
answers "which value applies". Two questions, two modules, two public services --
see the note there on why the split is not incidental.

**An implementation is never deleted.** Recalculating a 2026 period in 2030 needs
the 2026 algorithm still present, so retired code stays in the repository and
stays covered by the regression corpus. Deleting it makes the recalculation
quietly wrong rather than impossible, which is worse.
"""

from __future__ import annotations

from datetime import date

from evidenta.fiscal.parameters.services.resolution import (
    FiscalResolutionError,
    in_force,
)
from evidenta.fiscal.registry.models import FiscalLogicVersion, LogicStatus

__all__ = ["FiscalResolutionError", "resolve_logic"]


def resolve_logic(logic_key: str, effective_date: date) -> FiscalLogicVersion:
    """The implementation in force on ``effective_date``.

    Recalculating a 2026 period in 2030 arrives here with a 2026 date and gets the
    2026 implementation. Nothing about the current year enters -- which is the
    whole reason `if year >= 2027` is forbidden in business code (R17). The
    implementation written for 2026 does not know 2027 exists; the registry does.
    """
    matches = list(
        in_force(
            FiscalLogicVersion.objects.filter(logic_key=logic_key, status=LogicStatus.ACTIVE),
            effective_date,
        )
    )
    if not matches:
        raise FiscalResolutionError(
            "fiscal.no_logic",
            f"no active implementation for {logic_key!r} on {effective_date}",
        )
    if len(matches) > 1:
        raise FiscalResolutionError(
            "fiscal.ambiguous_logic",
            f"{logic_key!r} has {len(matches)} implementations in force on "
            f"{effective_date}; the newest is not the answer, the configuration "
            f"is wrong",
        )
    return matches[0]
