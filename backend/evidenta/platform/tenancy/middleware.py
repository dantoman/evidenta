"""Subdomain-derived tenant context -- the resolver behind RLS_CONTEXT_RESOLVER.

Replaces the fail-closed placeholder from F0.1.4. It puts together the two facts
Spec A section 3.2 requires before a transaction opens: the tenant, from the host,
and the user, from the session ``SessionAuthenticationMiddleware`` has already
resolved. Neither is taken from anything the client can choose.

The resolver still refuses rather than inventing an identity. What changed at
F0.3.7c is only that the identity now has a way to arrive.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest

from evidenta.platform.rls.context import Context, PlatformContext, TenantContext
from evidenta.platform.rls.middleware import TenantResolutionError
from evidenta.platform.tenancy.subdomain import (
    ResolvedTenant,
    is_console_host,
    resolve_tenant,
    subdomain_of,
)

#: Statuses under which a request is served at all. `suspended` and `offboarding`
#: keep read access per Spec A 9.4, but the read-only regime is not built yet, so
#: they are refused rather than served with full rights. Refusing too much is
#: recoverable; serving a suspended tenant with write access is not.
SERVEABLE_STATUSES = frozenset({"active"})

#: Places a client might try to state a tenant. Any of them disagreeing with the
#: host is a refusal, not a preference (C8, IZ-36).
CLIENT_TENANT_KEYS = ("tenant_id", "tenant")

#: What the console host serves -- the platform's own routes, and the
#: authentication routes it shares with everyone (ADR-076 §4.3). Prefixes, not
#: exact paths, and deliberately so: this is not an exemption from a guarantee
#: but the *whole* surface of a host, and every route under `/api/v1/platform/`
#: is a console route by construction. Anything else asked for on `admin.` is
#: answered 404: not forbidden -- there is no tenant it could be about.
CONSOLE_PATH_PREFIXES = ("/api/v1/auth/", "/api/v1/platform/")


def subdomain_resolver() -> SubdomainTenantResolver:
    """The factory named by ``RLS_CONTEXT_RESOLVER``.

    A dotted path cannot carry a constructor argument, and the resolver needs the
    base domain to measure hosts against -- ``alpha.evidenta.md`` is a tenant only
    if the deployment answers on ``evidenta.md``. Without knowing the base domain,
    the label to extract is a guess, and a guessed label is a guessed tenant.

    Refuses at startup rather than at the first request: a process that cannot
    resolve anything should not bind a port and look healthy.
    """
    base_domain = getattr(settings, "TENANT_BASE_DOMAIN", None)
    if not base_domain:
        raise ImproperlyConfigured(
            "TENANT_BASE_DOMAIN is not set. The subdomain resolver measures hosts "
            "against it to find the tenant label; without it there is no way to "
            "tell a tenant subdomain from the deployment's own host."
        )
    return SubdomainTenantResolver(str(base_domain))


class SubdomainTenantResolver:
    """Callable resolver built by :func:`subdomain_resolver`."""

    def __init__(self, base_domain: str) -> None:
        self.base_domain = base_domain

    def host_tenant(self, request: HttpRequest) -> ResolvedTenant:
        """Step 1 of spec-a 3.2, on its own.

        Separate from ``__call__`` because login needs it without step 2: the
        tenant is known from the host before anyone is authenticated -- that is
        the point of taking it from the host -- and the login endpoint has to know
        which tenant it is issuing a session for. Sharing the method rather than
        repeating three lines keeps the reserved names, the pattern and the
        indistinguishable refusal in one place.
        """
        label = subdomain_of(request.get_host(), self.base_domain)
        if label is None:
            raise TenantResolutionError("no tenant in host", code="tenant.not_found")

        resolved = resolve_tenant(label)
        if resolved is None or resolved.status not in SERVEABLE_STATUSES:
            # One message for "no such tenant" and for "not serveable". The
            # difference is real and must not reach the caller: it would make the
            # login page a directory of who exists.
            raise TenantResolutionError("no tenant in host", code="tenant.not_found")

        self._refuse_client_supplied_tenant(request, resolved.tenant_id)
        return resolved

    def is_console(self, request: HttpRequest) -> bool:
        """Whether the request is on the platform's console host (ADR-076 §4.2)."""
        return is_console_host(request.get_host(), self.base_domain)

    def console_context(self, request: HttpRequest) -> PlatformContext:
        """The console's context: a person and a request, no tenant.

        Three refusals, in the order that gives away the least. A route the
        console does not serve is 404 before anything is asked about the
        session, so a probe learns nothing from the difference between a
        signed-in and a signed-out request. Then the session must exist, and it
        must have been issued **on this host**: a session bound to a tenant is
        refused here just as a console session is refused on a tenant's host
        (`_refuse_foreign_session`). One person, two sessions, no menu between
        them -- that is the property ADR-076 asks for.
        """
        if not request.path.startswith(CONSOLE_PATH_PREFIXES):
            raise TenantResolutionError(
                "the console serves only the platform's own routes", code="console.not_found"
            )
        user_id = getattr(request, "authenticated_user_id", None)
        if user_id is None:
            raise TenantResolutionError("no authenticated session", code="auth.required")
        if getattr(request, "authenticated_tenant_id", None) is not None:
            raise TenantResolutionError(
                "a tenant session does not authenticate on the console host",
                code="auth.session_tenant_mismatch",
            )
        return PlatformContext(
            user_id=uuid.UUID(str(user_id)),
            request_id=getattr(request, "request_id", "unknown"),
        )

    def __call__(self, request: HttpRequest) -> Context:
        if self.is_console(request):
            return self.console_context(request)

        resolved = self.host_tenant(request)

        user_id = getattr(request, "authenticated_user_id", None)
        if user_id is None:
            raise TenantResolutionError("no authenticated session", code="auth.required")

        self._refuse_foreign_session(request, resolved.tenant_id)

        return TenantContext(
            tenant_id=resolved.tenant_id,
            user_id=uuid.UUID(str(user_id)),
            request_id=getattr(request, "request_id", "unknown"),
            # From the session, where it was validated against the firm at login
            # (spec-a 3.1). Never from the request: a client that could name its
            # own acting firm could name someone else's.
            actor_firm_id=_optional_uuid(getattr(request, "authenticated_actor_firm_id", None)),
            # Likewise the support grant (ADR-077 §6): set when the session was
            # issued, read back by `rls.resolve_session`, which also refuses a
            # session whose grant has since been revoked or has expired.
            support_grant_id=_optional_uuid(
                getattr(request, "authenticated_support_grant_id", None)
            ),
        )

    @staticmethod
    def _refuse_foreign_session(request: HttpRequest, resolved_id: uuid.UUID) -> None:
        """A session issued for one tenant does not authenticate on another's host.

        The cookie is host-only, so a browser will not send it across subdomains
        and this should be unreachable from one. It is not unreachable from a
        client that sets its own headers, and RLS alone would answer that with an
        empty result set rather than a refusal -- correct, but indistinguishable
        from a tenant with no data.
        """
        session_tenant = getattr(request, "authenticated_tenant_id", None)
        if session_tenant is None or uuid.UUID(str(session_tenant)) != resolved_id:
            raise TenantResolutionError(
                "session belongs to a different tenant than the host",
                code="auth.session_tenant_mismatch",
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
                raise TenantResolutionError(
                    "request states a tenant that disagrees with its host",
                    code="tenant.mismatch",
                )


def _optional_uuid(value: object) -> uuid.UUID | None:
    return None if value is None else uuid.UUID(str(value))
