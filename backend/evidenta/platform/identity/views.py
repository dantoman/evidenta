"""Authentication endpoints.

Plain Django views rather than DRF, deliberately. DRF is a dependency but is not
installed, and the API conventions -- serializers, error envelope, pagination,
versioned negotiation -- are F0.10.1. Writing these three endpoints against
conventions that do not exist yet would settle them by accident, in the module
least suited to arguing about them. What they do follow is the part already
decided: the version is in the path (C7) and every error carries a stable code,
not a message (C10).

``login`` is the one path in the product served with no tenant context. That is
not an exemption from isolation, it is where isolation begins: the view resolves
the tenant from the host like everything else, and the only database access it
can perform is through the privileged authentication path -- the query guard
refuses anything else, because there is no context.

**Not here, and known:** rate limiting and lockout after repeated failures. There
is no counter, so this endpoint answers a password attempt as fast as it can, for
ever. That belongs with the API conventions in F0.10.1; naming it here is cheaper
than discovering the omission from a log.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from evidenta.platform.identity import cookie
from evidenta.platform.identity.services import sessions
from evidenta.platform.identity.services.authentication import (
    AuthenticationError,
    MfaRequiredError,
    authenticate,
)
from evidenta.platform.rls.middleware import REFUSAL_STATUS, TenantResolutionError
from evidenta.platform.tenancy.middleware import subdomain_resolver


def _refusal(error: TenantResolutionError) -> JsonResponse:
    return JsonResponse({"code": error.code}, status=REFUSAL_STATUS.get(error.code or "", 500))


def _body(request: HttpRequest) -> dict[str, Any] | None:
    try:
        parsed = json.loads(request.body or b"{}")
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _optional_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    return uuid.UUID(str(value))


@require_POST
def login(request: HttpRequest) -> HttpResponse:
    """Password plus second factor, in exchange for a session cookie.

    The tenant is never read from the body. It comes from the host the request
    arrived on, like every other request in the product (C8) -- so a session is
    issued for the tenant the user is actually visiting, and a body claiming
    otherwise changes nothing.
    """
    try:
        tenant = subdomain_resolver().host_tenant(request)
    except TenantResolutionError as refusal:
        return _refusal(refusal)

    payload = _body(request)
    if payload is None:
        return JsonResponse({"code": "request.invalid_body"}, status=400)

    email = str(payload.get("email") or "")
    password = str(payload.get("password") or "")
    if not email or not password:
        # Shape, not credentials: a malformed request is not a failed attempt,
        # and answering it as one would make an empty form look like a wrong
        # password.
        return JsonResponse({"code": "request.invalid_body"}, status=400)

    try:
        actor_firm_id = _optional_uuid(payload.get("actor_firm_id"))
    except ValueError:
        return JsonResponse({"code": "request.invalid_body"}, status=400)

    try:
        issued = authenticate(
            email,
            password,
            tenant.tenant_id,
            request_id=str(getattr(request, "request_id", "login")),
            totp_code=payload.get("totp_code") or None,
            backup_code=payload.get("backup_code") or None,
            actor_firm_id=actor_firm_id,
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.headers.get("User-Agent"),
        )
    except MfaRequiredError as error:
        # 403, not 401: the credentials were accepted. What is missing is an
        # enrolled second factor, and retrying the password will never supply it.
        return JsonResponse({"code": error.code}, status=403)
    except AuthenticationError as error:
        return JsonResponse({"code": error.code}, status=401)

    response = JsonResponse({"expires_at": issued.expires_at.isoformat()})
    cookie.attach(response, issued.token, issued.expires_at)
    return response


@require_POST
def logout(request: HttpRequest) -> HttpResponse:
    """End the caller's own session.

    Not exempt from the tenant context, unlike login: ending a session requires
    holding one, and inside a context the ordinary ``user_session_self`` policy
    is what permits the write. The cookie is cleared either way -- a session that
    was already dead should not leave a browser holding a token for it.
    """
    session_id = getattr(request, "session_id", None)
    if session_id is not None:
        sessions.revoke(uuid.UUID(str(session_id)), reason="logout")

    # A 204 carries no body, and that is framing, not tidiness: RFC 9112 ends the
    # message at the header section for 204 regardless of what follows, so a JSON
    # body sent after it is read as the beginning of the *next* response on the
    # connection. Measured, because it was not theory: the two bytes `{}` make
    # node's HTTP parser -- what the development proxy runs on -- fail the
    # response with `HPE_INVALID_CONSTANT`, so the browser saw the sign-out fail
    # on a session this view had already revoked. The button appeared dead and
    # only a reload reached the login screen.
    response: HttpResponse = (
        HttpResponse(status=204) if session_id is not None else JsonResponse({}, status=200)
    )
    cookie.clear(response)
    return response


@require_GET
def whoami(request: HttpRequest) -> HttpResponse:
    """Who the context says this request is.

    Answers entirely from what the middlewares established, with no query at all.
    That is what makes it the honest end-to-end check of the chain: reaching it
    means the cookie resolved, the host resolved, the two agreed, and the context
    was set -- and none of those steps could have been faked by the response.
    """
    return JsonResponse(
        {
            "user_id": str(request.authenticated_user_id),  # type: ignore[attr-defined]
            "tenant_id": str(request.authenticated_tenant_id),  # type: ignore[attr-defined]
            "actor_firm_id": (
                str(request.authenticated_actor_firm_id)  # type: ignore[attr-defined]
                if getattr(request, "authenticated_actor_firm_id", None)
                else None
            ),
            "request_id": str(getattr(request, "request_id", "")),
        }
    )
