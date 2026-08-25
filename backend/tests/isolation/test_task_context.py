"""A Celery task cannot run without an explicit tenant, and fails loudly.

The failure mode this file exists to prevent: a decorator that, with no
``tenant_id``, lets the query run and relies on RLS to return nothing. It leaks
no data and passes every isolation test -- and a depreciation run over zero rows
reports success while posting nothing. That defect surfaces at month-end close.

So the assertions are about *when* and *how* the refusal happens, not only that
it happens.

Covers IZ-40 through IZ-45 (Spec A section 8.5). The first four are about the
mechanism and are made with invented UUIDs on purpose -- no row needs to exist
for a refusal to be a refusal. IZ-41 and IZ-45 are the two that need real
memberships, because there the question is what the database answers, and they
are grouped at the end.

Migrated from tests/isolation/manual_task_probe.py, deleted in the same change.
"""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from celery.exceptions import Retry
from django.db import connection

from evidenta.platform.rls.context import MissingTenantContextError
from evidenta.platform.rls.tasks import MissingTenantArgumentError, tenant_task

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

ATTEMPTS: list[uuid.UUID] = []


@tenant_task
def read_tenant(*, tenant_id: uuid.UUID, user_id: uuid.UUID) -> uuid.UUID:
    with connection.cursor() as cursor:
        cursor.execute("SELECT app.current_tenant_id()")
        return cursor.fetchone()[0]  # type: ignore[no-any-return]


@tenant_task
def always_fails(*, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    raise ValueError("deliberate failure")


@tenant_task(bind=True, max_retries=2)
def flaky(self: Any, *, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT app.current_tenant_id()")
        ATTEMPTS.append(cursor.fetchone()[0])
    raise self.retry(countdown=0, exc=ValueError("boom"))


@tenant_task
def visible_tenant_ids(*, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[uuid.UUID]:
    """Reads rows, not the context variable.

    Every task above asks the session what tenant it was given, which proves the
    decorator set it and cleared it. It does not prove the database agrees: a
    context set for a tenant the user cannot reach must still return nothing, and
    only a query against real rows can show that.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM tenant ORDER BY id")
        return [row[0] for row in cursor.fetchall()]


def undecorated(tenant_id: uuid.UUID) -> None:
    """What a task looks like when someone forgets the decorator."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")


@pytest.fixture
def tenant() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def user() -> uuid.UUID:
    return uuid.uuid4()


def test_missing_tenant_id_is_refused(user: uuid.UUID) -> None:
    """IZ-40."""
    with pytest.raises(MissingTenantArgumentError):
        read_tenant.apply(kwargs={"user_id": user}).get()


def test_refused_before_any_query_is_issued(user: uuid.UUID) -> None:
    """IZ-40, and IZ-42 from the other side. The check that matters is *when*.

    A decorator that refused after touching the database would satisfy "it
    refuses" and miss the point entirely.
    """
    queries: list[str] = []

    def count(execute: Any, sql: str, params: Any, many: bool, ctx: Any) -> Any:
        queries.append(sql)
        return execute(sql, params, many, ctx)

    with connection.execute_wrapper(count), pytest.raises(MissingTenantArgumentError):
        read_tenant.apply(kwargs={"user_id": user}).get()

    assert queries == []


def test_missing_user_id_is_refused(tenant: uuid.UUID) -> None:
    """IZ-40. No anonymous path, not even for scheduled work (Spec A 3.4)."""
    with pytest.raises(MissingTenantArgumentError):
        read_tenant.apply(kwargs={"tenant_id": tenant}).get()


def test_positional_arguments_are_checked_too() -> None:
    """IZ-40. Arguments are bound through the real signature.

    A check that read only ``kwargs`` would be bypassed in silence by
    ``task.delay(tid, uid)``.
    """
    with pytest.raises(MissingTenantArgumentError):
        read_tenant.apply(args=[]).get()


def test_task_sees_the_tenant_it_was_given(tenant: uuid.UUID, user: uuid.UUID) -> None:
    assert read_tenant.apply(kwargs={"tenant_id": tenant, "user_id": user}).get() == tenant


def test_forgetting_the_decorator_is_refused(tenant: uuid.UUID) -> None:
    """IZ-42."""
    with pytest.raises(MissingTenantContextError):
        undecorated(tenant)


def test_no_context_leak_between_consecutive_tasks(user: uuid.UUID) -> None:
    """IZ-43."""
    first, second = uuid.uuid4(), uuid.uuid4()
    assert read_tenant.apply(kwargs={"tenant_id": first, "user_id": user}).get() == first
    assert read_tenant.apply(kwargs={"tenant_id": second, "user_id": user}).get() == second


def test_context_does_not_survive_the_task(tenant: uuid.UUID, user: uuid.UUID) -> None:
    """IZ-42, after the fact: the next query has no context to inherit."""
    read_tenant.apply(kwargs={"tenant_id": tenant, "user_id": user}).get()
    with pytest.raises(MissingTenantContextError), connection.cursor() as cursor:
        cursor.execute("SELECT 1")


def test_failure_path_clears_the_context(tenant: uuid.UUID, user: uuid.UUID) -> None:
    """IZ-44, the error path."""
    with contextlib.suppress(ValueError):
        always_fails.apply(kwargs={"tenant_id": tenant, "user_id": user}).get()
    with pytest.raises(MissingTenantContextError), connection.cursor() as cursor:
        cursor.execute("SELECT 1")


def test_a_task_after_a_failure_still_gets_its_own_context(user: uuid.UUID) -> None:
    """IZ-44, and IZ-43 after a failure rather than after a success."""
    failed, following = uuid.uuid4(), uuid.uuid4()
    with contextlib.suppress(ValueError):
        always_fails.apply(kwargs={"tenant_id": failed, "user_id": user}).get()
    assert read_tenant.apply(kwargs={"tenant_id": following, "user_id": user}).get() == following


def test_retry_path_is_supported_and_carries_context(tenant: uuid.UUID, user: uuid.UUID) -> None:
    """IZ-44. Retry needs ``bind=True``, and retry is what SFS and bank tasks need.

    A decorator that only handled the bare form would be unusable for exactly the
    tasks that carry the most risk.
    """
    ATTEMPTS.clear()
    with contextlib.suppress(Retry, ValueError):
        flaky.apply(kwargs={"tenant_id": tenant, "user_id": user}, throw=True).get()
    assert ATTEMPTS
    assert all(seen == tenant for seen in ATTEMPTS)


def test_retry_path_clears_the_context(tenant: uuid.UUID, user: uuid.UUID) -> None:
    """IZ-44, the retry path."""
    with contextlib.suppress(Retry, ValueError):
        flaky.apply(kwargs={"tenant_id": tenant, "user_id": user}, throw=True).get()
    with pytest.raises(MissingTenantContextError), connection.cursor() as cursor:
        cursor.execute("SELECT 1")


# --- against real rows -------------------------------------------------------
#
# IZ-41 and IZ-45 are the two cases that cannot be made with invented UUIDs. Up
# to here the fixtures are `uuid4()`, which is right for the mechanism: no row
# has to exist for a refusal to be a refusal. From here a membership has to be a
# real membership, because what is being tested is the database's answer.


def test_task_reads_only_its_own_tenant(world: dict[str, uuid.UUID]) -> None:
    """IZ-41. The context is set correctly, and the data obeys it."""
    visible = visible_tenant_ids.apply(
        kwargs={"tenant_id": world["tenant_a"], "user_id": world["user_a"]}
    ).get()
    assert visible == [world["tenant_a"]]


def test_task_pointed_at_another_tenant_reads_nothing(world: dict[str, uuid.UUID]) -> None:
    """IZ-41, the other direction.

    A task started with tenant B's id and tenant A's user. The argument is
    honoured -- the context really is B -- and the row still does not appear,
    because the context names a tenant and the policy asks whether this user may
    reach it. Naming a tenant is not being allowed into it.
    """
    visible = visible_tenant_ids.apply(
        kwargs={"tenant_id": world["tenant_b"], "user_id": world["user_a"]}
    ).get()
    assert visible == []


def test_a_user_without_membership_reads_nothing(
    world: dict[str, uuid.UUID], seed: Callable[..., None]
) -> None:
    """IZ-45. Scheduled work runs as somebody, and somebody is not a free pass.

    The system user exists and is active; it simply belongs to no tenant. The
    task starts -- the decorator has both arguments and cannot tell this user
    from any other -- and the normal path yields nothing (Spec A 3.4). The
    refusal comes from the database, which is the only place it can come from
    for work that nobody is watching.
    """
    system_user = uuid.uuid4()
    now = datetime.now(UTC)
    seed(
        'INSERT INTO "user" (id, email, full_name, mfa_enabled, locale,'
        " is_active, created_at, updated_at)"
        " VALUES (%s, %s, %s, false, 'ro', true, %s, %s)",
        [system_user, "scheduler@example.md", "Scheduler", now, now],
    )

    visible = visible_tenant_ids.apply(
        kwargs={"tenant_id": world["tenant_a"], "user_id": system_user}
    ).get()
    assert visible == []
