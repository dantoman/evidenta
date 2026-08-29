"""The one door to the reference-data connection -- Spec A section 6.1, ADR-049.

Every privileged path owes two things: it runs under a role that can write what
it writes and nothing else, and it leaves a row in ``privileged_access_log`` in
the same transaction. This module is where both happen, so that a loader cannot
get the connection without also getting the audit row.

The ``refdata`` alias is deliberately not importable from settings by name
anywhere else. A service that quietly reached for a privileged connection would
be a privileged path nobody declared -- the exact shape that ``OD-67`` recorded
as the stopgap (``using=`` supplied by the caller) and ADR-049 replaced.
"""

from __future__ import annotations

import getpass
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from django.db import transaction

from evidenta.platform.audit.models import PrivilegedAccessLog, PrivilegedPath

# The path codes are part of this service's contract: a loader names its path
# here, and it must not reach into `audit.models` for the enumeration (D6).
__all__ = ["REFDATA_ALIAS", "PrivilegedPath", "PrivilegedRun", "privileged_run"]

#: The Django connection alias of the reference-data role (ADR-049).
REFDATA_ALIAS = "refdata"


@dataclass
class PrivilegedRun:
    """What the log row will say. The body of the run fills ``payload`` as it goes."""

    path_code: str
    actor: str
    request_id: str
    actor_user_id: uuid.UUID | None = None
    tenant_id: uuid.UUID | None = None
    tenant_count: int | None = None
    justification: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


def default_actor() -> str:
    """Who is at the keyboard, when nobody said. Operator commands run from a
    shell; the OS login is the honest answer and is what an operator would be
    asked at a review."""
    try:
        return f"os:{getpass.getuser()}"
    except (KeyError, OSError):  # pragma: no cover - no passwd entry (containers)
        return "os:unknown"


@contextmanager
def privileged_run(
    path_code: str,
    *,
    actor: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    request_id: str | None = None,
    tenant_id: uuid.UUID | None = None,
    tenant_count: int | None = None,
    justification: str | None = None,
    payload: dict[str, Any] | None = None,
    using: str = REFDATA_ALIAS,
) -> Iterator[PrivilegedRun]:
    """Open the privileged transaction and record the run when it commits.

    The log row is written **last**, inside the same transaction: a run that
    fails leaves neither its writes nor a row claiming it happened, and a run that
    succeeds cannot commit without its row. ``payload`` is whatever the body
    adds to ``run.payload`` -- counts, identifiers, the file name -- never the
    data written.

    ``using`` exists for the tests that prove the refusals: a run pointed at the
    application connection must be refused by the database, and the way to show
    that is to try.
    """
    if path_code not in PrivilegedPath.values:
        raise ValueError(f"{path_code!r} is not a privileged path (Spec A 6.2, ADR-049)")
    run = PrivilegedRun(
        path_code=path_code,
        actor=actor or default_actor(),
        request_id=request_id or f"run:{uuid.uuid4()}",
        actor_user_id=actor_user_id,
        tenant_id=tenant_id,
        tenant_count=tenant_count,
        justification=justification,
        payload=dict(payload or {}),
    )
    with transaction.atomic(using=using):
        yield run
        PrivilegedAccessLog.objects.using(using).create(
            occurred_at=datetime.now(tz=UTC),
            path_code=run.path_code,
            actor_user_id=run.actor_user_id,
            actor=run.actor,
            subject_tenant_id=run.tenant_id,
            tenant_count=run.tenant_count,
            request_id=run.request_id,
            justification=run.justification,
            payload=run.payload or None,
        )
