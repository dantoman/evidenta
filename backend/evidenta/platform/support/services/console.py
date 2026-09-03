"""The platform's half of a support grant -- the request, from the console (ADR-077 §5).

`P-7` is `rls.request_support_access`: a SECURITY DEFINER function that verifies,
in SQL, that the caller is a live `support` employee on the console host, that the
space exists and is not archived, that the ticket and the justification are
there, and that no live request or grant already exists -- then writes the
unapproved row and the `P-7` log row in one transaction. The request gives no
access; the client's approval does.

The list is `rls.console_support_grants()`, staff-gated like every console read
(0076), and shows the company as an identifier only: its name is the client's.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from django.db import DatabaseError, connection, transaction

from evidenta.platform.tenancy.subdomain import resolve_tenant


class RequestRefusedError(RuntimeError):
    """The function refused the request. ``code`` follows the SQLSTATE it raised with."""

    def __init__(self, code: str, status: int, message: str) -> None:
        self.code = code
        self.status = status
        super().__init__(message)


#: SQLSTATE -> stable code. The function speaks in states; the client in codes.
_REFUSALS = {
    "42501": ("support.request_refused", 403),
    "22023": ("support.request_invalid", 400),
    "23505": ("support.request_exists", 409),
}


def request_grant(
    *, subdomain: str, company_id: uuid.UUID | None, request_ref: str, justification: str
) -> uuid.UUID:
    resolved = resolve_tenant(subdomain.strip().lower())
    if resolved is None:
        raise RequestRefusedError("support.space_not_found", 404, f"no space {subdomain!r}")
    try:
        # Its own savepoint: a refusal raised by the function must not leave the
        # request's transaction aborted -- the error middleware answers on it.
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "SELECT rls.request_support_access(%s, %s, %s, %s)",
                [resolved.tenant_id, company_id, request_ref, justification],
            )
            row = cursor.fetchone()
    except DatabaseError as error:
        state = getattr(getattr(error, "__cause__", None), "sqlstate", None)
        code, status = _REFUSALS.get(str(state), ("support.request_refused", 403))
        raise RequestRefusedError(code, status, _first_line(error)) from error
    # ADR-077 §6: the client's members hear about the request at once. The
    # function writes those rows itself -- the Python dispatch goes through
    # `rls.notify_tenant_members`, which asks `rls.has_tenant_access`, and the
    # console has no tenant context to satisfy it with (measured: it refused).
    return uuid.UUID(str(row[0]))


def _first_line(error: BaseException) -> str:
    text = str(error).strip()
    return text.split("\n", 1)[0].replace("evidenta: ", "")


@dataclass(frozen=True, slots=True)
class ConsoleGrantRow:
    id: uuid.UUID
    subdomain: str
    legal_name: str
    company_id: uuid.UUID | None
    requested_by_email: str
    request_ref: str
    justification: str
    requested_at: datetime
    approved_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None

    @property
    def status(self) -> str:
        if self.revoked_at is not None:
            return "revoked"
        if self.approved_at is None:
            return "pending"
        if self.expires_at is not None and self.expires_at <= datetime.now(tz=UTC):
            return "expired"
        return "active"


def list_grants() -> list[ConsoleGrantRow]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, subdomain, legal_name, company_id, requested_by_email, request_ref, "
            "justification, requested_at, approved_at, expires_at, revoked_at "
            "FROM rls.console_support_grants()"
        )
        rows = cursor.fetchall()
    return [ConsoleGrantRow(*row) for row in rows]
