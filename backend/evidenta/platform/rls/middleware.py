"""Request-scoped tenant context.

The middleware does two things and refuses everything else: it resolves the
context for the request, and it holds it for the whole response cycle inside one
transaction.

Resolution is pluggable and, until F0.3.5, refuses by default. That is not a
placeholder -- it is the fail-closed position. A middleware that shipped with a
permissive default resolver would work in development and leak in production, and
the moment to notice is now, not then.
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

    Replaced at F0.3.5 by subdomain resolution (C8). Until a Tenant table exists
    there is nothing to resolve, and answering anything other than "no" would be
    inventing an answer.
    """
    raise TenantResolutionError(
        "No tenant context resolver is configured. Set RLS_CONTEXT_RESOLVER once "
        "subdomain resolution exists (F0.3.5). Until then the application has no "
        "request path to tenant data, by design."
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


def resolver_for_testing(request: HttpRequest) -> TenantContext:
    """Resolver used by the isolation suites before F0.3.5 exists.

    Reads the context from request headers. Never configured outside tests; if it
    ever appears in a non-test settings module, that is a critical finding.
    """
    tenant = request.headers.get("X-Test-Tenant")
    user = request.headers.get("X-Test-User")
    if not tenant or not user:
        raise TenantResolutionError("X-Test-Tenant and X-Test-User are required")
    firm = request.headers.get("X-Test-Firm")
    return TenantContext(
        tenant_id=uuid.UUID(tenant),
        user_id=uuid.UUID(user),
        request_id=getattr(request, "request_id", "test"),
        actor_firm_id=uuid.UUID(firm) if firm else None,
    )
