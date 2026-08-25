"""Resolving the tenant from the subdomain -- Spec A sections 1.1 and 3.2.

The tenant comes from the subdomain and from nowhere else (C8). Not from the
payload, not from a query parameter, not from a header the client controls. The
reason is not tidiness: any of those is a value the caller chooses, and a caller
who chooses their own tenant is not isolated by anything.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from django.db import connection

from evidenta.platform.rls.context import unguarded

#: Subdomains that never belong to a tenant. Reserved so that a tenant cannot
#: take a name the platform itself answers on -- a tenant called ``api`` would
#: shadow the API host, and the mistake is unrecoverable once links exist.
RESERVED_SUBDOMAINS = frozenset(
    {
        "www",
        "api",
        "admin",
        "app",
        "static",
        "assets",
        "mail",
        "status",
        "docs",
        "help",
        "support",
        "billing",
        "firm",
        "partner",
    }
)

#: Same shape as the CHECK on tenant.subdomain, deliberately duplicated: the
#: database refuses a bad value, this refuses a bad *request* before it becomes a
#: query. If they ever disagree, the database wins and this is the bug.
SUBDOMAIN_PATTERN = re.compile(r"^[a-z][a-z0-9-]{2,29}$")


class SubdomainError(RuntimeError):
    """The request cannot be attributed to a tenant from its host."""


@dataclass(frozen=True)
class ResolvedTenant:
    tenant_id: uuid.UUID
    status: str


def subdomain_of(host: str, base_domain: str) -> str | None:
    """Extract the tenant label from a Host header.

    Returns None when the host carries no tenant label, is reserved, or is
    malformed -- three different reasons that must produce the same answer to the
    caller. Distinguishing them in the response would turn the login page into a
    tenant directory.
    """
    host = host.split(":", 1)[0].strip().lower().rstrip(".")
    if not host or not host.endswith("." + base_domain):
        return None

    label = host[: -(len(base_domain) + 1)]
    if "." in label:  # deeper nesting is not a tenant name
        return None
    if label in RESERVED_SUBDOMAINS or not SUBDOMAIN_PATTERN.match(label):
        return None
    return label


def resolve_tenant(subdomain: str) -> ResolvedTenant | None:
    """Look the tenant up through the privileged path.

    Uses ``rls.resolve_tenant_by_subdomain``: at this point no tenant context
    exists, so the ordinary policy on ``tenant`` cannot answer -- it requires the
    very thing being resolved.

    This is the one query in the request path that legitimately runs before a
    context, so it is the one place that names ``unguarded``. The query guard
    found it on its own, which is the behaviour that justifies the guard: the
    exception had to be stated rather than assumed.
    """
    with (
        unguarded("subdomain resolution: runs before any tenant context exists"),
        connection.cursor() as cursor,
    ):
        cursor.execute(
            "SELECT tenant_id, status FROM rls.resolve_tenant_by_subdomain(%s)",
            [subdomain],
        )
        row = cursor.fetchone()

    if row is None:
        return None
    return ResolvedTenant(tenant_id=row[0], status=row[1])
