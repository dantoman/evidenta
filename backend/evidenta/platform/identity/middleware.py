"""Session authentication -- Spec A section 3.2, step 2.

Turns a cookie into ``request.authenticated_user_id``. That attribute is what the
subdomain resolver has been waiting for since F0.3.5: it refuses without one
rather than inventing an identity.

**This middleware never refuses.** It attaches what it can prove and returns.
Every refusal belongs to the resolver, so there is exactly one place that decides
whether a request may proceed -- two would eventually disagree, and the
disagreement would be resolved in favour of whichever ran first.

It runs before ``TenantContextMiddleware`` and therefore outside the request
transaction. That is correct rather than incidental: the session lookup precedes
the context, so it cannot be inside the transaction the context establishes.
"""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from evidenta.platform.identity import cookie
from evidenta.platform.identity.services import sessions


class SessionAuthenticationMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        token = cookie.token_from(request)
        if token:
            resolved = sessions.resolve(token)
            if resolved is not None:
                # Distinct names from anything Django owns. `request.user` would
                # invite the habits of django.contrib.auth, which this project
                # deliberately does not install -- and a lazily-evaluated user
                # object is exactly the shape that produces a query with no
                # context, three layers deep in a template.
                request.session_id = resolved.session_id  # type: ignore[attr-defined]
                request.authenticated_user_id = resolved.user_id  # type: ignore[attr-defined]
                request.authenticated_tenant_id = resolved.tenant_id  # type: ignore[attr-defined]
                request.authenticated_actor_firm_id = resolved.actor_firm_id  # type: ignore[attr-defined]
                request.authenticated_support_grant_id = resolved.support_grant_id  # type: ignore[attr-defined]
        return self.get_response(request)
