"""Request-scoped tenant context.

The middleware does two things and refuses everything else: it resolves the
context for the request, and it holds it for the whole response cycle inside one
transaction.

Resolution is pluggable and refuses by default. That is not a placeholder -- it
is the fail-closed position. A middleware that shipped with a permissive default
resolver would work in development and leak in production, and the moment to
notice is now, not then.

A refusal is a response, not a traceback -- but only when it carries a code. The
distinction matters: "this host has no tenant" and "this request has no session"
are ordinary answers a client is entitled to (404, 401), while a resolver that is
missing or broken is a misconfiguration, and turning that into a tidy 404 would
hide it behind a page that looks like normal operation.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.module_loading import import_string

from evidenta.platform.rls.context import TenantContext, tenant_context


class TenantResolutionError(RuntimeError):
    """The request could not be attributed to a tenant.

    ``code`` is what makes the refusal answerable. Without one the refusal
    propagates and the request fails loudly, which is what a misconfigured
    resolver deserves.
    """

    def __init__(self, message: str, *, code: str | None = None) -> None:
        self.code = code
        super().__init__(message)


#: The refusals that are answers rather than faults, and the status each carries.
#:
#: `tenant.not_found` is deliberately the same answer for an unknown subdomain and
#: for a tenant that exists but is not serveable (IZ-37). The difference is real
#: and must not reach the caller: it would make the login page a directory of who
#: exists.
REFUSAL_STATUS: dict[str, int] = {
    "tenant.not_found": 404,
    "auth.required": 401,
    "tenant.mismatch": 400,
    "auth.session_tenant_mismatch": 401,
}


def refuse_all(request: HttpRequest) -> TenantContext:
    """Default resolver: refuse.

    Reached only when ``RLS_CONTEXT_RESOLVER`` is unset. Every environment that
    serves requests names a resolver factory; an environment that does not has no
    request path to tenant data, and says so with a 500 rather than a 404 --
    because it is broken, not empty.
    """
    raise TenantResolutionError(
        "No tenant context resolver is configured. RLS_CONTEXT_RESOLVER must name "
        "a zero-argument factory returning the resolver -- see "
        "evidenta.platform.tenancy.middleware.subdomain_resolver. Until it does, "
        "the application has no request path to tenant data, by design."
    )


class TenantContextMiddleware:
    """Resolves the context, then holds it for the response cycle.

    ``RLS_CONTEXT_RESOLVER`` names a **factory**, not the resolver itself: the
    subdomain resolver needs the base domain to measure hosts against, and a
    dotted path cannot carry a constructor argument. Building it once here, at
    startup, also means a missing ``TENANT_BASE_DOMAIN`` fails when the process
    starts rather than on the first request that happens to arrive.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        dotted: str | None = getattr(settings, "RLS_CONTEXT_RESOLVER", None)
        factory = import_string(dotted) if dotted else None
        self.resolve: Callable[[HttpRequest], TenantContext] = (
            factory() if factory is not None else refuse_all
        )
        # Paths served before authentication -- login, and nothing else by
        # default. They run with no context at all, which is exactly what makes
        # the exemption safe to have: the query guard refuses every context-less
        # query on the application connection, so an exempt view cannot reach
        # business data even by mistake. It can only call the privileged paths
        # that state their reason.
        self.exempt: tuple[str, ...] = tuple(getattr(settings, "TENANT_CONTEXT_EXEMPT_PATHS", ()))

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.request_id = str(uuid.uuid4())  # type: ignore[attr-defined]

        if request.path in self.exempt:
            return self.get_response(request)

        try:
            context = self.resolve(request)
        except TenantResolutionError as refusal:
            status = REFUSAL_STATUS.get(refusal.code or "")
            if status is None:
                raise
            return JsonResponse({"code": refusal.code}, status=status)

        with tenant_context(context):
            response = self.get_response(request)
            # Deliberate: the response is produced inside the transaction. A
            # streaming response that yields rows after this block would run its
            # queries with no context -- and the guard would refuse them, which is
            # the correct outcome, not a limitation to work around.
            return response
