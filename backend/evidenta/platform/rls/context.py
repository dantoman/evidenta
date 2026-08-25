"""Tenant context: what it is, how it is set, and how it is proven present.

The database refuses queries without context (``app.current_tenant_id()`` raises).
This module is the application side of the same guarantee, and it exists because
the database's refusal, while correct, arrives late and speaks Postgres. A request
that reaches the database without context is already a bug; catching it here names
the bug instead of surfacing an ERRCODE.

Two rules shape everything below:

* ``SET LOCAL`` lives only inside a transaction. Setting context outside one is
  not "less safe", it is a no-op -- so it raises instead.
* The variables are set with ``set_config(..., is_local => true)``, never by
  interpolating into ``SET LOCAL``. ``SET`` does not accept parameters, so the
  naive version builds SQL by string concatenation from request-derived values.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID

from django.db import DEFAULT_DB_ALIAS, connections, transaction


class OutsideTransactionError(RuntimeError):
    """Context was set outside a transaction, where SET LOCAL does nothing."""


class MissingTenantContextError(RuntimeError):
    """A query reached the database with no tenant context established."""


@dataclass(frozen=True, slots=True)
class TenantContext:
    """The session variables of Spec A section 3.1.

    ``tenant_id``, ``user_id`` and ``request_id`` are mandatory: their absence is
    a refusal. ``actor_firm_id`` is absent for a member of the tenant, and
    ``company_id`` narrows rather than grants (ADR-004) -- absent means "every
    company this user may access", never "every company".
    """

    tenant_id: UUID
    user_id: UUID
    request_id: str
    actor_firm_id: UUID | None = None
    company_id: UUID | None = None

    def as_settings(self) -> dict[str, str | None]:
        return {
            "app.tenant_id": str(self.tenant_id),
            "app.user_id": str(self.user_id),
            "app.request_id": self.request_id,
            "app.actor_firm_id": str(self.actor_firm_id) if self.actor_firm_id else None,
            "app.company_id": str(self.company_id) if self.company_id else None,
        }


_state = threading.local()


def current_context() -> TenantContext | None:
    """The context of the innermost active scope, or None."""
    return getattr(_state, "context", None)


def is_unguarded() -> bool:
    """True inside an explicitly unguarded scope (migrations, bootstrap)."""
    return getattr(_state, "unguarded", 0) > 0


def _apply(context: TenantContext, using: str) -> None:
    connection = connections[using]
    if not connection.in_atomic_block:
        raise OutsideTransactionError(
            "Tenant context must be set inside a transaction. SET LOCAL is scoped "
            "to the transaction, so setting it outside one silently does nothing "
            "and every later query runs without context."
        )
    with connection.cursor() as cursor:
        for name, value in context.as_settings().items():
            if value is None:
                continue
            cursor.execute("SELECT set_config(%s, %s, true)", [name, value])


@contextmanager
def tenant_context(context: TenantContext, using: str = DEFAULT_DB_ALIAS) -> Iterator[None]:
    """Open a transaction, set the context, and hold it for the block.

    The transaction is opened here rather than assumed: a caller that already has
    one gets a savepoint, and ``SET LOCAL`` applied in the outer transaction stays
    in effect for both.
    """
    previous = getattr(_state, "context", None)
    with transaction.atomic(using=using):
        _apply(context, using)
        _state.context = context
        try:
            yield
        finally:
            _state.context = previous


@contextmanager
def unguarded(reason: str) -> Iterator[None]:
    """Allow queries without tenant context, for a named reason.

    The reason is required and is not decoration: every use of this is a place
    where the guarantee is suspended, and a list of such places with no stated
    reason is how the guarantee erodes. Intended for schema bootstrap and for
    migrations, never for business code.
    """
    if not reason:
        raise ValueError("unguarded() requires a reason")
    _state.unguarded = getattr(_state, "unguarded", 0) + 1
    try:
        yield
    finally:
        _state.unguarded -= 1
