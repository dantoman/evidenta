"""Refuse, loudly, any query that reaches the database without tenant context.

The database already refuses: every policy calls ``app.current_tenant_id()``,
which raises when the context is missing. So why a second barrier in the
application?

Because of *where* the two fire. The database refuses at the moment a policy is
evaluated -- which happens on business tables, and only on business tables. A
management command that reads a table before RLS applies, a shell session, a view
that queries before its transaction opens: each of these is a path the middleware
does not cover, and each fails at the database only if it happens to touch a
protected table. This wrapper fails on the first query, whatever it touches, and
says which path did it.

It is deliberately not a security control. A compromised process can remove it.
It is a development-time guarantee that the application has no accidental path to
data without context -- the class of bug that RLS exists to catch, caught earlier
and with a legible message.
"""

from __future__ import annotations

from typing import Any

from django.db import DEFAULT_DB_ALIAS
from django.db.backends.signals import connection_created

from evidenta.platform.rls.context import (
    MissingTenantContextError,
    has_context,
    is_unguarded,
)

# Statements Django issues to manage the connection and the transaction itself.
# They carry no tenant data, and refusing them would break the very mechanism
# that establishes context.
_INFRASTRUCTURE_PREFIXES = (
    "set ",
    "select set_config",
    "show ",
    "begin",
    "commit",
    "rollback",
    "savepoint",
    "release savepoint",
    "rollback to savepoint",
)


def _is_infrastructure(sql: str) -> bool:
    return sql.lstrip().lower().startswith(_INFRASTRUCTURE_PREFIXES)


def guard_execute(execute: Any, sql: str, params: Any, many: bool, context: dict[str, Any]) -> Any:
    connection = context["connection"]

    # The migration connection runs as the owner and never serves a request.
    # Guarding it would only break `migrate`.
    if connection.alias != DEFAULT_DB_ALIAS:
        return execute(sql, params, many, context)

    # A platform context (ADR-076) counts as context: the console's queries
    # carry a user and a request, and the database itself refuses the tenant
    # tables under it -- see `PlatformContext`.
    if _is_infrastructure(sql) or is_unguarded() or has_context():
        return execute(sql, params, many, context)

    raise MissingTenantContextError(
        "Query attempted with no tenant context on the application connection.\n"
        f"  SQL: {sql.strip()[:200]}\n"
        "Every request must run inside tenant_context(); every Celery task must "
        "receive tenant_id explicitly and set the context before querying (R6). "
        "Schema bootstrap and migrations use unguarded('<reason>')."
    )


def _install(sender: Any, connection: Any, **kwargs: Any) -> None:
    if guard_execute not in connection.execute_wrappers:
        connection.execute_wrappers.append(guard_execute)


def install() -> None:
    """Attach the guard to every connection, present and future."""
    connection_created.connect(_install, dispatch_uid="evidenta.rls.guard")
