"""Subdomain-derived tenant context -- the resolver behind RLS_CONTEXT_RESOLVER.

Replaces the fail-closed placeholder from F0.1.4. What it adds is the tenant; what
it still cannot add is the user, because authentication is F0.3.7. Until then the
resolver refuses rather than inventing an identity -- a resolver that defaulted to
some user would work in development and be a hole in production.
"""

from __future__ import annotations

import uuid

from django.http import HttpRequest

from evidenta.platform.rls.context import TenantContext
from evidenta.platform.rls.middleware import TenantResolutionError
from evidenta.platform.tenancy.subdomain import resolve_tenant, subdomain_of

#: Statuses under which a request is served at all. `suspended` and `offboarding`
#: keep read access per Spec A 9.4, but the read-only regime is not built yet, so
#: they are refused rather than served with full rights. Refusing too much is
#: recoverable; serving a suspended tenant with write access is not.
SERVEABLE_STATUSES = frozenset({"active"})

#: Places a client might try to state a tenant. Any of them disagreeing with the
#: host is a refusal, not a preference (C8, IZ-36).
CLIENT_TENANT_KEYS = ("tenant_id", "tenant")


class SubdomainTenantResolver:
    """Callable resolver configured through ``RLS_CONTEXT_RESOLVER``."""

    def __init__(self, base_domain: str) -> None:
        self.base_domain = base_domain

    def __call__(self, request: HttpRequest) -> TenantContext:
        label = subdomain_of(request.get_host(), self.base_domain)
        if label is None:
            raise TenantResolutionError("no tenant in host")

        resolved = resolve_tenant(label)
        if resolved is None or resolved.status not in SERVEABLE_STATUSES:
            # One message for "no such tenant" and for "not serveable". The
            # difference is real and must not reach the caller: it would make the
            # login page a directory of who exists.
            raise TenantResolutionError("no tenant in host")

        self._refuse_client_supplied_tenant(request, resolved.tenant_id)

        user_id = getattr(request, "authenticated_user_id", None)
        if user_id is None:
            raise TenantResolutionError("no authenticated user; authentication is F0.3.7")

        return TenantContext(
            tenant_id=resolved.tenant_id,
            user_id=uuid.UUID(str(user_id)),
            request_id=getattr(request, "request_id", "unknown"),
        )

    @staticmethod
    def _refuse_client_supplied_tenant(request: HttpRequest, resolved_id: uuid.UUID) -> None:
        """IZ-36. A tenant stated by the client is ignored, and if it disagrees
        with the host the request is refused.

        Ignoring silently would be enough for isolation -- the context comes from
        the host either way. It is not enough for *detection*: a client sending a
        foreign tenant_id is either broken or probing, and both are worth seeing.
        """
        candidates = [request.GET.get(key) for key in CLIENT_TENANT_KEYS if key in request.GET]
        header = request.headers.get("X-Tenant-Id")
        if header:
            candidates.append(header)

        for value in candidates:
            if value and str(value).strip().lower() != str(resolved_id):
                raise TenantResolutionError("request states a tenant that disagrees with its host")
