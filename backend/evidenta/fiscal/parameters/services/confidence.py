"""Moving a parameter between confirmed and inferred, without losing the past.

Confirming a value does not change the value. That is what makes the transition
easy to record badly: it looks like an edit to one column, and an edit erases the
state a past calculation actually relied on.

So the transition is written in two places at once -- the current state on the
parameter, for the common query, and an append-only event, for the question an
inspection asks. One call, one transaction, no way to do half of it.

**This runs on the privileged path, never on the application connection.**
`fiscal_parameter` and this table are global and have INSERT/UPDATE revoked from
`evidenta_app`; a tenant must not be able to declare that a rate is now
confirmed. Spec A calls that path `P-4`, and since ADR-049 it has a mechanism:
the reference-data role, reached through ``privileged_run``, which writes the
``privileged_access_log`` row in the same transaction. ``using`` stays as an
argument for one reason -- the tests that prove the refusals point it at the
application connection and watch the database say no.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from evidenta.fiscal.parameters.models import (
    FiscalParameter,
    FiscalParameterConfidenceEvent,
    SourceConfidence,
)
from evidenta.platform.audit.services.privileged import (
    REFDATA_ALIAS,
    PrivilegedPath,
    privileged_run,
)


class ConfidenceTransitionError(RuntimeError):
    """The transition was refused. Never a silent no-op."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def set_confidence(
    parameter: FiscalParameter,
    confidence: str,
    *,
    note: str,
    effective_at: datetime,
    provisional_reason: str | None = None,
    recorded_by_user_id: uuid.UUID | None = None,
    actor: str | None = None,
    using: str = REFDATA_ALIAS,
) -> FiscalParameterConfidenceEvent:
    """Record a confidence state and make it current.

    ``note`` is required and is the answer to "why did this change" -- "the tax
    service published the annual note on 2027-03-30" is an answer, "confirmed" is
    not. ``effective_at`` is supplied rather than defaulted to now() because
    backfilling a state that predates this table is a real case.

    Writing the same state twice is refused. It would add an event that changes
    nothing while making the history look like something happened, which is worse
    than no history at all -- a reader would date the transition to the wrong
    moment.
    """
    with privileged_run(
        PrivilegedPath.P4_FISCAL_RULES,
        actor=actor,
        actor_user_id=recorded_by_user_id,
        payload={
            "operation": "set_confidence",
            "parameter_key": parameter.parameter_key,
            "confidence": confidence,
        },
        using=using,
    ):
        return _set_confidence(
            parameter,
            confidence,
            note=note,
            effective_at=effective_at,
            provisional_reason=provisional_reason,
            recorded_by_user_id=recorded_by_user_id,
            using=using,
        )


def _set_confidence(
    parameter: FiscalParameter,
    confidence: str,
    *,
    note: str,
    effective_at: datetime,
    provisional_reason: str | None,
    recorded_by_user_id: uuid.UUID | None,
    using: str,
) -> FiscalParameterConfidenceEvent:
    if confidence not in SourceConfidence.values:
        raise ConfidenceTransitionError(
            "fiscal.unknown_confidence", f"{confidence!r} is not a confidence state"
        )
    if not note.strip():
        raise ConfidenceTransitionError(
            "fiscal.confidence_note_required",
            "a confidence transition without a stated reason cannot be audited",
        )
    if confidence == SourceConfidence.PROVISIONAL and not (provisional_reason or "").strip():
        raise ConfidenceTransitionError(
            "fiscal.provisional_reason_required",
            "marking a value inferred requires saying what the inference rests on",
        )

    latest = (
        FiscalParameterConfidenceEvent.objects.using(using)
        .filter(parameter=parameter)
        .order_by("-effective_at", "-recorded_at")
        .first()
    )
    if latest is not None:
        if latest.confidence == confidence:
            raise ConfidenceTransitionError(
                "fiscal.confidence_unchanged",
                f"parameter {parameter.pk} is already {confidence}; recording it again "
                f"would date the transition to the wrong moment",
            )
        if effective_at < latest.effective_at:
            raise ConfidenceTransitionError(
                "fiscal.confidence_out_of_order",
                f"{effective_at} precedes the last recorded state at {latest.effective_at}; "
                f"the history is append-only and cannot be interleaved",
            )

    event = FiscalParameterConfidenceEvent.objects.using(using).create(
        parameter=parameter,
        confidence=confidence,
        provisional_reason=provisional_reason,
        note=note,
        effective_at=effective_at,
        recorded_by_user_id=recorded_by_user_id,
    )

    # The current state stays on the parameter so the common query does not have
    # to walk the history; the event is what makes the past recoverable.
    parameter.source_confidence = confidence
    parameter.provisional_reason = provisional_reason
    parameter.save(
        using=using,
        update_fields=["source_confidence", "provisional_reason", "updated_at"],
    )

    return event
