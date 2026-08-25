"""Generating append-only volume, through the application role and its policies.

The point of generating rather than importing: the volume model (`docs/_bootstrap
/11-volume-model.md`) rests on public aggregates and five declared assumptions, so
what is needed here is *rows at a scale*, not anybody's real data.

The rows go in through ``evidenta_app`` with RLS active, deliberately. Inserting
as owner or superuser would be faster and would measure a database we do not run:
the ``WITH CHECK`` on ``audit_event`` calls ``rls.has_tenant_access`` for every
row, and that cost is part of the answer to whether the write path holds.

One consequence, and it is the policy working as designed: a session can only
write rows for its own tenant and its own actor. Spreading volume across tenants
means switching context per tenant, which is what ``spread_across_tenants`` does.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from django.db import connection

from evidenta.platform.rls.context import TenantContext, tenant_context


@dataclass(frozen=True)
class Generated:
    rows: int
    seconds: float

    @property
    def rows_per_second(self) -> float:
        return self.rows / self.seconds if self.seconds else float("inf")


def audit_events(
    count: int,
    *,
    company_id: uuid.UUID | None = None,
    days: int = 365,
) -> Generated:
    """Insert ``count`` audit events into the current tenant context.

    One statement over ``generate_series`` rather than a loop: the goal is a table
    of a given size, and a round trip per row would measure psycopg rather than
    PostgreSQL. The policy is still evaluated per row.

    ``occurred_at`` is spread backwards over ``days`` so that the partition column
    has a realistic distribution -- a benchmark where every row shares a timestamp
    would make any time-based index look perfect.

    The interval is built by multiplication rather than by concatenating a string:
    ``random() * 365 || ' days'`` renders small values in scientific notation, and
    ``interval`` refuses ``9.2e-05 days``. It only fails once enough rows have been
    drawn for one of them to be that small -- so it passes at two thousand rows and
    fails at a million, which is the wrong way round for a bug to behave.
    """
    started = time.perf_counter()
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO audit_event (
                tenant_id, company_id, occurred_at, actor_user_id, actor_firm_id,
                request_id, action, entity_type, entity_id, old_value, new_value,
                ip_address, source
            )
            SELECT app.current_tenant_id(),
                   %s,
                   now() - (random() * %s) * interval '1 day',
                   app.current_user_id(),
                   NULL,
                   'volume-' || i,
                   (ARRAY['create', 'update', 'post', 'revoke'])[1 + (i %% 4)],
                   (ARRAY['document', 'engagement', 'company_access'])[1 + (i %% 3)],
                   gen_random_uuid(),
                   NULL,
                   NULL,
                   NULL,
                   'task'
              FROM generate_series(1, %s) AS i
            """,
            [company_id, days, count],
        )
    return Generated(rows=count, seconds=time.perf_counter() - started)


def spread_across_tenants(
    tenants: list[tuple[uuid.UUID, uuid.UUID]],
    *,
    rows_each: int,
    days: int = 365,
) -> Generated:
    """Fill several tenants, each in its own context.

    ``tenants`` is a list of ``(tenant_id, user_id)`` -- the user must be an active
    member, or the policy refuses the write, which is the correct behaviour and
    not something to work around here.
    """
    started = time.perf_counter()
    total = 0
    for tenant_id, user_id in tenants:
        with tenant_context(
            TenantContext(tenant_id=tenant_id, user_id=user_id, request_id="volume")
        ):
            total += audit_events(rows_each, days=days).rows
    return Generated(rows=total, seconds=time.perf_counter() - started)
