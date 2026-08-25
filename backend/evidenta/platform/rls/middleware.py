"""Request-scoped tenant context.

The middleware does two things and refuses everything else: it resolves the
context for the request, and it holds it for the whole response cycle inside one
transaction.

Resolution is pluggable and refuses by default. That is not a placeholder -- it
is the fail-closed position. A middleware that shipped with a permissive default
resolver would work in development and leak in production, and the moment to
notice is now, not then.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.module_loading import import_string

from evidenta.platform.rls.context import TenantContext, tenant_context


class TenantResolutionError(RuntimeError):
    """The request could not be attributed to a tenant."""


def refuse_all(request: HttpRequest) -> TenantContext:
    """Default resolver: refuse.

    The replacement exists -- ``tenancy.SubdomainTenantResolver``, F0.3.5 -- but
    nothing points ``RLS_CONTEXT_RESOLVER`` at it. Two things are missing: a base
    domain to measure hosts against, and the authenticated user the resolver
    refuses without (F0.3.7). Until both land, refusing is the whole answer.
    """
    raise TenantResolutionError(
        "No tenant context resolver is configured. The subdomain resolver exists "
        "(tenancy.SubdomainTenantResolver) but nothing points RLS_CONTEXT_RESOLVER "
        "at it, and it would refuse anyway until authentication lands (F0.3.7). "
        "The application has no request path to tenant data, by design."
    )


class TenantContextMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        dotted: str | None = getattr(settings, "RLS_CONTEXT_RESOLVER", None)
        self.resolve: Callable[[HttpRequest], TenantContext] = (
            import_string(dotted) if dotted else refuse_all
        )

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.request_id = str(uuid.uuid4())  # type: ignore[attr-defined]
        context = self.resolve(request)
        with tenant_context(context):
            response = self.get_response(request)
            # Deliberate: the response is produced inside the transaction. A
            # streaming response that yields rows after this block would run its
            # queries with no context -- and the guard would refuse them, which is
            # the correct outcome, not a limitation to work around.
            return response
