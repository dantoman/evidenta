"""The session cookie: one place that knows its name and its attributes.

Two properties are load-bearing and easy to lose by writing them twice.

**Host-only.** No ``Domain`` attribute, ever. A cookie set for ``.evidenta.md``
would be sent to every tenant's subdomain, so one tenant's session would arrive
on another tenant's host -- attached to a request the resolver then has to refuse
on the strength of a comparison. Leaving ``Domain`` unset makes the browser
refuse first: the cookie is simply not sent. The tenant boundary and the cookie
boundary become the same line.

**``SameSite=Lax``.** There is no CSRF middleware in the chain yet (API
conventions are F0.10.1), so this attribute is currently the whole of the
cross-site protection: a browser does not attach a Lax cookie to a cross-site
POST, which is every state-changing request the product has. Written here rather
than at each call site, because a single ``set_cookie`` that forgot it would open
the hole quietly.
"""

from __future__ import annotations

from datetime import datetime

from django.conf import settings
from django.http import HttpRequest, HttpResponse


def name() -> str:
    return str(getattr(settings, "AUTH_COOKIE_NAME", "evidenta_session"))


def token_from(request: HttpRequest) -> str | None:
    return request.COOKIES.get(name())


def attach(response: HttpResponse, token: str, expires_at: datetime) -> None:
    """Put a freshly issued session on the response."""
    response.set_cookie(
        name(),
        token,
        expires=expires_at,
        # Not readable by script: the token is a bearer credential, and no part
        # of the frontend has a reason to see it.
        httponly=True,
        # False only where there is no TLS to require -- local development. The
        # per-environment settings decide; there is no default that quietly
        # ships a cookie over plaintext in production.
        secure=bool(getattr(settings, "AUTH_COOKIE_SECURE", True)),
        samesite="Lax",
        path="/",
        # domain deliberately omitted -- see the module docstring.
    )


def clear(response: HttpResponse) -> None:
    """Remove the cookie. Attributes must match those used to set it, or the
    browser keeps the old one alongside the deletion."""
    response.delete_cookie(
        name(),
        path="/",
        samesite="Lax",
    )
