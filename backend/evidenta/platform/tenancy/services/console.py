"""What the console may know about every space -- the `tenant` row, not its contents.

Through `rls.console_tenants()` (0076), which refuses under a tenant context and
refuses a caller who is not a live employee of the platform, then returns the
columns ADR-076 §4.3 names: subdomain, legal name, status, the dates, and two
counts. A count of companies is metadata about a space; what those companies
hold is not, and nothing here can reach it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from django.db import connection


@dataclass(frozen=True, slots=True)
class SpaceRow:
    id: uuid.UUID
    subdomain: str
    legal_name: str
    legal_form: str | None
    idno: str | None
    status: str
    claimed_at: datetime | None
    suspended_at: datetime | None
    offboarding_started_at: datetime | None
    archived_at: datetime | None
    created_at: datetime
    company_count: int
    member_count: int


def list_spaces() -> list[SpaceRow]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, subdomain, legal_name, legal_form, idno, status, claimed_at, "
            "suspended_at, offboarding_started_at, archived_at, created_at, company_count, "
            "member_count FROM rls.console_tenants()"
        )
        rows = cursor.fetchall()
    return [
        SpaceRow(
            id=row[0],
            subdomain=row[1],
            legal_name=row[2],
            legal_form=row[3],
            idno=row[4],
            status=row[5],
            claimed_at=row[6],
            suspended_at=row[7],
            offboarding_started_at=row[8],
            archived_at=row[9],
            created_at=row[10],
            company_count=int(row[11]),
            member_count=int(row[12]),
        )
        for row in rows
    ]
