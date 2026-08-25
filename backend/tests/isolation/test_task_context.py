"""A Celery task cannot run without an explicit tenant, and fails loudly.

The failure mode this file exists to prevent: a decorator that, with no
``tenant_id``, lets the query run and relies on RLS to return nothing. It leaks
no data and passes every isolation test -- and a depreciation run over zero rows
reports success while posting nothing. That defect surfaces at month-end close.

So the assertions are about *when* and *how* the refusal happens, not only that
it happens.

Migrated from tests/isolation/manual_task_probe.py, deleted in the same change.
"""

from __future__ import annotations

import contextlib
import uuid
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
    with pytest.raises(MissingTenantArgumentError):
        read_tenant.apply(kwargs={"user_id": user}).get()


def test_refused_before_any_query_is_issued(user: uuid.UUID) -> None:
    """The check that matters is *when*, not whether.

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
    """No anonymous path, not even for scheduled work (Spec A 3.4)."""
    with pytest.raises(MissingTenantArgumentError):
        read_tenant.apply(kwargs={"tenant_id": tenant}).get()


def test_positional_arguments_are_checked_too() -> None:
    """Arguments are bound through the real signature.

    A check that read only ``kwargs`` would be bypassed in silence by
    ``task.delay(tid, uid)``.
    """
    with pytest.raises(MissingTenantArgumentError):
        read_tenant.apply(args=[]).get()


def test_task_sees_the_tenant_it_was_given(tenant: uuid.UUID, user: uuid.UUID) -> None:
    assert read_tenant.apply(kwargs={"tenant_id": tenant, "user_id": user}).get() == tenant


def test_forgetting_the_decorator_is_refused(tenant: uuid.UUID) -> None:
    with pytest.raises(MissingTenantContextError):
        undecorated(tenant)


def test_no_context_leak_between_consecutive_tasks(user: uuid.UUID) -> None:
    first, second = uuid.uuid4(), uuid.uuid4()
    assert read_tenant.apply(kwargs={"tenant_id": first, "user_id": user}).get() == first
    assert read_tenant.apply(kwargs={"tenant_id": second, "user_id": user}).get() == second


def test_context_does_not_survive_the_task(tenant: uuid.UUID, user: uuid.UUID) -> None:
    read_tenant.apply(kwargs={"tenant_id": tenant, "user_id": user}).get()
    with pytest.raises(MissingTenantContextError), connection.cursor() as cursor:
        cursor.execute("SELECT 1")


def test_failure_path_clears_the_context(tenant: uuid.UUID, user: uuid.UUID) -> None:
    with contextlib.suppress(ValueError):
        always_fails.apply(kwargs={"tenant_id": tenant, "user_id": user}).get()
    with pytest.raises(MissingTenantContextError), connection.cursor() as cursor:
        cursor.execute("SELECT 1")


def test_a_task_after_a_failure_still_gets_its_own_context(user: uuid.UUID) -> None:
    failed, following = uuid.uuid4(), uuid.uuid4()
    with contextlib.suppress(ValueError):
        always_fails.apply(kwargs={"tenant_id": failed, "user_id": user}).get()
    assert read_tenant.apply(kwargs={"tenant_id": following, "user_id": user}).get() == following


def test_retry_path_is_supported_and_carries_context(tenant: uuid.UUID, user: uuid.UUID) -> None:
    """Retry needs ``bind=True``, and retry is what SFS and bank tasks need.

    A decorator that only handled the bare form would be unusable for exactly the
    tasks that carry the most risk.
    """
    ATTEMPTS.clear()
    with contextlib.suppress(Retry, ValueError):
        flaky.apply(kwargs={"tenant_id": tenant, "user_id": user}, throw=True).get()
    assert ATTEMPTS
    assert all(seen == tenant for seen in ATTEMPTS)


def test_retry_path_clears_the_context(tenant: uuid.UUID, user: uuid.UUID) -> None:
    with contextlib.suppress(Retry, ValueError):
        flaky.apply(kwargs={"tenant_id": tenant, "user_id": user}, throw=True).get()
    with pytest.raises(MissingTenantContextError), connection.cursor() as cursor:
        cursor.execute("SELECT 1")
