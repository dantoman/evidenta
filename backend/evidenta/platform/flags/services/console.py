"""Release rings and feature flags as the console sees them -- Spec A §13.5, R23.

Two catalogues and two assignments. The catalogues (`feature_flag`,
`release_ring`) are global and readable by the application role under any
context, so they come through the ORM. The assignments (`tenant_release_ring`,
`feature_flag_override`) are tenant-scoped and come through the staff-gated
functions of 0076. Read only: nothing in the product writes an assignment yet
(measured: the two tables have no service writer), so the console has nothing
to offer but the truth about them, and a button here would invent a path.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from django.db import connection

from evidenta.platform.flags.models import FeatureFlag, ReleaseRing


@dataclass(frozen=True, slots=True)
class FlagRow:
    key: str
    description: str
    default_state: bool
    is_compliance: bool


@dataclass(frozen=True, slots=True)
class RingRow:
    code: str
    description: str
    sequence: int


@dataclass(frozen=True, slots=True)
class RingAssignmentRow:
    subdomain: str
    legal_name: str
    ring_code: str
    assigned_at: datetime
    assigned_by_email: str | None


@dataclass(frozen=True, slots=True)
class OverrideRow:
    id: uuid.UUID
    subdomain: str
    legal_name: str
    flag_key: str
    state: bool
    reason: str
    expires_at: datetime
    created_at: datetime
    created_by_email: str | None


def list_flags() -> list[FlagRow]:
    return [
        FlagRow(
            key=str(flag.key),
            description=flag.description,
            default_state=bool(flag.default_state),
            is_compliance=bool(flag.is_compliance),
        )
        for flag in FeatureFlag.objects.order_by("key")
    ]


def list_rings() -> list[RingRow]:
    return [
        RingRow(code=str(ring.code), description=ring.description, sequence=int(ring.sequence))
        for ring in ReleaseRing.objects.order_by("sequence")
    ]


def list_ring_assignments() -> list[RingAssignmentRow]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT subdomain, legal_name, ring_code, assigned_at, assigned_by_email "
            "FROM rls.console_release_rings()"
        )
        rows = cursor.fetchall()
    return [RingAssignmentRow(*row) for row in rows]


def list_overrides() -> list[OverrideRow]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, subdomain, legal_name, flag_key, state, reason, expires_at, created_at, "
            "created_by_email FROM rls.console_flag_overrides()"
        )
        rows = cursor.fetchall()
    return [OverrideRow(*row) for row in rows]
