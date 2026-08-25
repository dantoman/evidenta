"""The measurements behind `OD-01`, run under the application role with RLS on.

F0.11 asks for three quantified scenarios *and* for measurements that run with the
policies active and under ``evidenta_app``. The quantities live in
``docs/_bootstrap/11-volume-model.md``; this file is the second half.

Two scales, on purpose:

* the default one is small (a few thousand rows) and runs in the ordinary suite,
  so the harness cannot rot unnoticed. A benchmark nobody runs measures nothing,
  and one that only runs when someone remembers is the same thing with extra
  steps.
* the real one is opt-in through ``EVIDENTA_VOLUME_ROWS``, because a hundred
  million rows is not a unit test.

What the small scale can still prove, and does, is the part that actually decides
`OD-01`: that the query plan for the scoped read uses the tenant-leading index
rather than a sequential scan. That property is what makes partitioning a
question of size alone rather than of shape -- and it is size-independent, so it
can be asserted honestly here.
"""

from __future__ import annotations

import os
import re
import time
import uuid
from collections.abc import Callable, Sequence
from typing import Any

import pytest
from django.db import connection

from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.volume.generate import audit_events, spread_across_tenants

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

#: Rows per tenant at the default scale. Enough to exercise the write path and
#: the planner, small enough that nobody has to think about it.
DEFAULT_ROWS = 2_000

#: The opt-in scale: EVIDENTA_VOLUME_ROWS=1000000 make test, or run this file.
ROWS = int(os.environ.get("EVIDENTA_VOLUME_ROWS", DEFAULT_ROWS))


def context_of(world: dict[str, uuid.UUID], side: str) -> TenantContext:
    return TenantContext(
        tenant_id=world[f"tenant_{side}"],
        user_id=world[f"user_{side}"],
        request_id="volume",
    )


def timed(query: str, params: Sequence[Any] | None = None) -> tuple[float, list[tuple[Any, ...]]]:
    started = time.perf_counter()
    with connection.cursor() as cursor:
        cursor.execute(query, params or [])
        rows = cursor.fetchall()
    return time.perf_counter() - started, rows


def test_the_write_path_holds_under_its_own_policy(world: dict[str, uuid.UUID]) -> None:
    """Rows go in through evidenta_app, with WITH CHECK evaluated per row.

    Generating as owner would be faster and would measure a database we do not
    run: the policy calls ``rls.has_tenant_access`` for every row inserted, and
    whether that cost is tolerable is half the question.
    """
    with tenant_context(context_of(world, "a")):
        generated = audit_events(ROWS)

    assert generated.rows == ROWS
    print(
        f"\n  write: {generated.rows:,} rows in {generated.seconds:.2f}s "
        f"({generated.rows_per_second:,.0f} rows/s, RLS active)"
    )


def test_the_measurement_really_ran_with_rls_active(world: dict[str, uuid.UUID]) -> None:
    """The control. Without it, every timing below could be a timing of nothing.

    Two tenants are filled; each context must see exactly its own rows. A
    benchmark that silently ran with the policies off would report excellent
    numbers for a system nobody ships.
    """
    spread_across_tenants(
        [
            (world["tenant_a"], world["user_a"]),
            (world["tenant_b"], world["user_b"]),
        ],
        rows_each=DEFAULT_ROWS,
    )

    with tenant_context(context_of(world, "a")):
        _, seen_by_a = timed("SELECT count(*) FROM audit_event")
    with tenant_context(context_of(world, "b")):
        _, seen_by_b = timed("SELECT count(*) FROM audit_event")

    assert seen_by_a[0][0] == DEFAULT_ROWS
    assert seen_by_b[0][0] == DEFAULT_ROWS


def rows_touched(plan: str) -> float:
    """The largest ``actual rows`` any node in the plan reported."""
    return max(
        (float(match) for match in re.findall(r"actual time=[\d.]+\.\.[\d.]+ rows=([\d.]+)", plan)),
        default=0.0,
    )


def test_the_scoped_read_uses_the_recent_index(world: dict[str, uuid.UUID]) -> None:
    """Spec A 9.3's enumeration reaches its rows through the right index.

    The first version of this test asserted ``"Seq Scan" not in plan`` and passed
    while the same query took **6.7 seconds on a million rows**: the plan was an
    index scan, of everything. ``audit_event_scope_idx`` is (tenant_id,
    company_id, occurred_at), so within a tenant the rows are ordered by company
    before time and cannot answer ORDER BY occurred_at without being read whole.
    ``audit_event_recent_idx`` exists because of that measurement.

    What this asserts at the default scale is that the index is *chosen*. What it
    deliberately does not assert is how many rows the plan reads, because at two
    thousand rows PostgreSQL correctly prefers a bitmap scan and a top-N sort over
    a plain index scan -- reading everything is cheaper when everything is small.
    The rows-read assertion lives in the opt-in test below, where it means
    something.

    Worth knowing while reading any plan in this system: the planner cannot
    estimate selectivity through ``app.current_tenant_id()`` and guesses a handful
    of rows regardless of the table. Plan shape therefore changes with real size
    in ways a small fixture will never show.
    """
    with tenant_context(context_of(world, "a")):
        audit_events(DEFAULT_ROWS)
        with connection.cursor() as cursor:
            # A planner that has never seen the table guesses; the volume model is
            # about the steady state, not the first query after loading.
            cursor.execute("ANALYZE audit_event")
            cursor.execute(
                """
                EXPLAIN (ANALYZE, FORMAT TEXT)
                SELECT id, action, occurred_at
                  FROM audit_event
                 WHERE tenant_id = app.current_tenant_id()
                 ORDER BY occurred_at DESC
                 LIMIT 50
                """
            )
            plan = "\n".join(row[0] for row in cursor.fetchall())

    assert "Seq Scan" not in plan, plan
    assert "audit_event_recent_idx" in plan, (
        f"the enumeration is not using the index built for it\n{plan}"
    )


def test_reading_a_period_narrows_the_work(world: dict[str, uuid.UUID]) -> None:
    """The property a time-based partition key would later make structural.

    ``occurred_at`` is the declared partition column for ``audit_event``
    (`infra/schema/append_only.toml`). Before any partitioning exists, the same
    narrowing has to come from the index -- and if it does not come from the index
    now, partitioning later would be repairing the wrong thing.
    """
    with tenant_context(context_of(world, "a")):
        audit_events(ROWS, days=365)

        whole, all_rows = timed(
            "SELECT count(*) FROM audit_event WHERE tenant_id = app.current_tenant_id()"
        )
        window, recent = timed(
            "SELECT count(*) FROM audit_event"
            " WHERE tenant_id = app.current_tenant_id()"
            "   AND occurred_at >= now() - interval '30 days'"
        )

    assert all_rows[0][0] == ROWS
    assert recent[0][0] < all_rows[0][0], "a 30-day window over a year should be a subset"
    print(
        f"\n  read: full {whole * 1000:.1f}ms over {all_rows[0][0]:,} rows, "
        f"30-day window {window * 1000:.1f}ms over {recent[0][0]:,}"
    )


@pytest.mark.skipif(
    ROWS <= DEFAULT_ROWS,
    reason="opt-in: set EVIDENTA_VOLUME_ROWS to something the model actually predicts",
)
def test_growth_does_not_change_the_plan(
    world: dict[str, uuid.UUID], seed: Callable[..., None]
) -> None:
    """At the requested scale, does the scoped read still avoid a scan?

    This is the one that answers `OD-01` for real, and it is opt-in because the
    model's platform figure is ~172 million audit events per year -- not something
    to generate inside an ordinary suite run.
    """
    with tenant_context(context_of(world, "a")):
        generated = audit_events(ROWS)
        with connection.cursor() as cursor:
            cursor.execute("ANALYZE audit_event")
            cursor.execute(
                "EXPLAIN (ANALYZE, FORMAT TEXT)"
                " SELECT id FROM audit_event"
                "  WHERE tenant_id = app.current_tenant_id()"
                "  ORDER BY occurred_at DESC LIMIT 50"
            )
            plan = "\n".join(row[0] for row in cursor.fetchall())

    print(f"\n  {generated.rows:,} rows, {generated.rows_per_second:,.0f} rows/s\n{plan}")
    assert "Seq Scan" not in plan, plan
    assert rows_touched(plan) <= 4 * 50, (
        f"read {rows_touched(plan):,.0f} rows to return 50 -- measured at 6.7s for a "
        f"million before audit_event_recent_idx existed\n{plan}"
    )
