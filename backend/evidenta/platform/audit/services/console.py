"""Reading `privileged_access_log` for the console -- Spec A §6.3, ADR-076 §4.3.

The table is `platform_log`: the application role holds no privilege on it, so
until now nobody read it through the product. The console reads it through
`rls.console_privileged_log()` (0076) -- staff-gated, refused under a tenant
context, filtered by typed parameters and capped -- and shows exactly the log
row: who ran which path, when, on which space, with what parameters. Never
what the run wrote; the log never held that either.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.db import connection

from evidenta.platform.audit.models import PrivilegedPath

#: What the console may ask for at most. The function caps at the same number.
MAX_ROWS = 500


@dataclass(frozen=True, slots=True)
class LogRow:
    id: int
    occurred_at: datetime
    path_code: str
    actor: str
    actor_user_id: uuid.UUID | None
    actor_email: str | None
    subject_tenant_id: uuid.UUID | None
    subject_subdomain: str | None
    tenant_count: int | None
    request_id: str
    justification: str | None
    payload: dict[str, Any] | None


def path_catalogue() -> list[dict[str, str]]:
    """The codes a row may carry, for the filter -- from the same enumeration the
    CHECK constraint enforces."""
    return [{"code": str(code), "label": str(label)} for code, label in PrivilegedPath.choices]


def privileged_log(
    *, path_code: str | None = None, subdomain: str | None = None, limit: int = 100
) -> list[LogRow]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, occurred_at, path_code, actor, actor_user_id, actor_email, "
            "subject_tenant_id, subject_subdomain, tenant_count, request_id, justification, "
            "payload FROM rls.console_privileged_log(%s, %s, %s)",
            [path_code or None, subdomain or None, min(max(int(limit), 1), MAX_ROWS)],
        )
        rows = cursor.fetchall()
    return [
        LogRow(
            id=int(row[0]),
            occurred_at=row[1],
            path_code=row[2],
            actor=row[3],
            actor_user_id=row[4],
            actor_email=row[5],
            subject_tenant_id=row[6],
            subject_subdomain=row[7],
            tenant_count=row[8],
            request_id=row[9],
            justification=row[10],
            payload=row[11],
        )
        for row in rows
    ]
