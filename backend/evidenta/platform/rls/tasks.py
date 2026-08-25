"""Tenant context for Celery tasks.

A task is the entry point with no request, no subdomain and no user session. It
gets its tenant from exactly one place: an explicit argument (R6). A task that
derives the tenant from global state, from the last task the worker happened to
run, or from an object loaded earlier is defective -- not because it leaks today,
but because it will the first time two tenants are processed in the same worker.

**Fail-closed is not enough here; the failure must also be loud.**

The tempting shape is a decorator that, when ``tenant_id`` is missing, lets the
query run and relies on RLS to return nothing. It passes every isolation test --
no data crosses a tenant boundary. And it is wrong: a depreciation run over zero
rows reports success and posts nothing. The defect surfaces at month-end close,
not in CI. So the decorator refuses *before* the first query, with an exception
that names what was missing.
"""

from __future__ import annotations

import functools
import inspect
import uuid
from collections.abc import Callable
from typing import Any, TypeVar, cast

from celery import current_task, shared_task

from evidenta.platform.rls.context import TenantContext, tenant_context

F = TypeVar("F", bound=Callable[..., Any])


class MissingTenantArgumentError(RuntimeError):
    """A task was invoked without the arguments that establish its context."""


def _required_uuid(name: str, bound: inspect.BoundArguments, task_name: str) -> uuid.UUID:
    if name not in bound.arguments or bound.arguments[name] is None:
        raise MissingTenantArgumentError(
            f"Task {task_name!r} was called without {name!r}.\n"
            f"Every task receives its tenant explicitly (R6). Deriving it from "
            f"global state, from the previous task, or from a loaded object is "
            f"defective. Refusing before the first query: a task that runs with no "
            f"context returns zero rows and reports success."
        )
    value = bound.arguments[name]
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _optional_uuid(name: str, bound: inspect.BoundArguments) -> uuid.UUID | None:
    value = bound.arguments.get(name)
    if value is None:
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def tenant_task(*decorator_args: Any, **decorator_kwargs: Any) -> Any:
    """Register a Celery task that cannot run without tenant context.

    Usable bare (``@tenant_task``) or with Celery options
    (``@tenant_task(name="...", max_retries=3)``).

    The wrapped function declares ``tenant_id`` and ``user_id`` in its signature;
    ``company_id`` and ``actor_firm_id`` are optional. Arguments are bound through
    the real signature, so passing them positionally is caught too -- a check that
    only looked at ``kwargs`` would be silently bypassed by ``task.delay(tid, uid)``.

    ``user_id`` is not optional for scheduled work either: a task without a human
    caller uses a system user (Spec A section 3.4), so that audit records which
    process acted. There is no anonymous path.
    """

    bare = len(decorator_args) == 1 and callable(decorator_args[0]) and not decorator_kwargs
    celery_args: tuple[Any, ...] = () if bare else decorator_args

    def decorate(fn: F) -> F:
        signature = inspect.signature(fn)

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            task_name = getattr(current_task, "name", None) or fn.__name__
            bound = signature.bind_partial(*args, **kwargs)

            tenant_id = _required_uuid("tenant_id", bound, task_name)
            user_id = _required_uuid("user_id", bound, task_name)

            request_id = getattr(getattr(current_task, "request", None), "id", None)
            context = TenantContext(
                tenant_id=tenant_id,
                user_id=user_id,
                request_id=str(request_id or uuid.uuid4()),
                actor_firm_id=_optional_uuid("actor_firm_id", bound),
                company_id=_optional_uuid("company_id", bound),
            )

            # tenant_context restores the previous scope in a finally block, so
            # the error path and the retry path clear it like the success path.
            # The database side clears itself: SET LOCAL dies with the
            # transaction, whether it commits or rolls back.
            with tenant_context(context):
                return fn(*args, **kwargs)

        return cast(F, shared_task(*celery_args, **decorator_kwargs)(wrapper))

    return decorate(decorator_args[0]) if bare else decorate
