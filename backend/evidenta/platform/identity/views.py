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
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from evidenta.platform.identity import cookie
from evidenta.platform.identity.services import sessions
from evidenta.platform.identity.services.authentication import (
    AuthenticationError,
    MfaRequiredError,
    authenticate,
)
from evidenta.platform.identity.services.profile import ProfileMalformedError, update_profile
from evidenta.platform.identity.services.staff import staff_role_in_context
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

    **On the console host there is no tenant to resolve** (ADR-076 §4.2), and
    the session issued is bound to none. The same form, the same password and
    second factor, one more condition: the person is a live employee of the
    platform. Everybody else gets `auth.no_access_to_console` -- after their
    credentials were accepted, because that is what is true.
    """
    resolver = subdomain_resolver()
    tenant_id: uuid.UUID | None
    if resolver.is_console(request):
        tenant_id = None
    else:
        try:
            tenant_id = resolver.host_tenant(request).tenant_id
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
            tenant_id,
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
    # Null on the console host, and the client branches on it: a session with no
    # tenant is a console session, by construction (ADR-076 §4.2).
    tenant_id = getattr(request, "authenticated_tenant_id", None)
    return JsonResponse(
        {
            "user_id": str(request.authenticated_user_id),  # type: ignore[attr-defined]
            "tenant_id": str(tenant_id) if tenant_id is not None else None,
            "actor_firm_id": (
                str(request.authenticated_actor_firm_id)  # type: ignore[attr-defined]
                if getattr(request, "authenticated_actor_firm_id", None)
                else None
            ),
            "request_id": str(getattr(request, "request_id", "")),
        }
    )


@require_http_methods(["PATCH"])
def profile(request: HttpRequest) -> HttpResponse:
    """Correct your own display name.

    No identifier in the path or the payload: it edits the signed-in user and
    nobody else. That is not politeness -- the policy on `user` is self-row, so a
    request naming somebody else would update nothing, and an endpoint that
    accepted the name would be inviting a question it cannot answer.
    """
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"code": "api.invalid"}, status=400)

    try:
        answer = update_profile(
            request.authenticated_user_id,  # type: ignore[attr-defined]
            full_name=str(payload.get("full_name", "")),
        )
    except ProfileMalformedError as refusal:
        return JsonResponse({"code": refusal.code, "message": str(refusal)}, status=refusal.status)

    return JsonResponse(answer)


@require_GET
def staff_me(request: HttpRequest) -> HttpResponse:
    """Who the console's caller is: their name, and which staff role they hold.

    Served only on the console host -- the tenant resolver never opens a
    platform context anywhere else -- and answered through two self-row
    policies: the caller's own `user` row and their own `platform_staff` row. A
    person with a console session and no live staff row (revoked since they
    signed in) gets 403, and the client shows them the door.
    """
    user_id = uuid.UUID(str(request.authenticated_user_id))  # type: ignore[attr-defined]
    membership = staff_role_in_context(user_id)
    if membership is None:
        return JsonResponse({"code": "auth.no_access_to_console"}, status=403)
    me = _me(user_id)
    return JsonResponse(
        {
            "user_id": str(user_id),
            "email": me.get("email", ""),
            "full_name": me.get("full_name", ""),
            "staff_role": membership.staff_role,
            "granted_at": membership.granted_at.isoformat(),
        }
    )


def _me(user_id: uuid.UUID) -> dict[str, str]:
    """The caller's own name and address, through the `user_self` policy.

    Lazy import of the model module's *public* shape via the ORM is what the
    self-row policy is for: the row returned is the caller's or nothing.
    """
    from evidenta.platform.identity.models import User

    row = User.objects.filter(pk=user_id).values("email", "full_name").first()
    return {k: str(v) for k, v in (row or {}).items()}
