"""Stable error codes -- C10.

    "Erorile au cod stabil, nu doar mesaj."

The reason is the frontend. ADR-014 keeps Russian as a presentation layer and
C32 puts every interface string in a resource file, so a client that branched on
`response.detail` would break the day a message is reworded -- and reworded
messages are the cheapest thing in the product. The code is the contract; the
message is for the human reading the log.

**Nothing escapes as an untyped failure.** The handler maps Django's and DRF's
own exceptions to codes too, because an endpoint that answers `{"code": ...}`
nine times out of ten and a bare 500 the tenth time has no contract at all -- the
tenth is exactly where a client needs to branch.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from rest_framework import exceptions as drf
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class ApiError(Exception):
    """An error with a stable code.

    Subclasses set `code` and `status`. The message is free text and may change
    at any time; the code may not, and changing one is a breaking API change in
    the same sense as removing a field.
    """

    code = "error.unknown"
    status = 400

    def __init__(self, message: str = "", **context: Any) -> None:
        self.context = context
        super().__init__(message or self.code)


class IdempotencyKeyRequiredError(ApiError):
    code = "api.idempotency_key_required"
    status = 400


class IdempotencyKeyInvalidError(ApiError):
    code = "api.idempotency_key_invalid"
    status = 400


class TenantContextMissingError(ApiError):
    code = "api.tenant_context_missing"
    status = 403


#: Django's and DRF's own failures, given codes. Kept as an explicit table rather
#: than derived from the class name: a rename upstream would silently change a
#: code that clients branch on.
BUILTIN_CODES: dict[type[Exception], tuple[str, int]] = {
    Http404: ("api.not_found", 404),
    PermissionDenied: ("api.forbidden", 403),
    ValidationError: ("api.invalid", 400),
    drf.NotFound: ("api.not_found", 404),
    drf.PermissionDenied: ("api.forbidden", 403),
    drf.NotAuthenticated: ("api.not_authenticated", 401),
    drf.AuthenticationFailed: ("api.not_authenticated", 401),
    drf.MethodNotAllowed: ("api.method_not_allowed", 405),
    drf.ValidationError: ("api.invalid", 400),
    drf.Throttled: ("api.throttled", 429),
    drf.ParseError: ("api.malformed", 400),
    drf.UnsupportedMediaType: ("api.unsupported_media_type", 415),
}


def code_for(exc: Exception) -> tuple[str, int] | None:
    for kind, pair in BUILTIN_CODES.items():
        if isinstance(exc, kind):
            return pair
    return None


def exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """Wired through `REST_FRAMEWORK["EXCEPTION_HANDLER"]`.

    Returning `None` hands the exception back to Django, which turns it into a
    500. That is deliberate for anything not in the table: an unexpected failure
    should be loud and should reach the error tracker, not be flattened into a
    tidy JSON body that looks handled.
    """
    if isinstance(exc, ApiError):
        body: dict[str, Any] = {"code": exc.code, "message": str(exc)}
        if exc.context:
            body["context"] = exc.context
        return Response(body, status=exc.status)

    known = code_for(exc)
    if known is None:
        return None

    code, status = known
    response = drf_exception_handler(exc, context)
    detail = response.data if response is not None else str(exc)
    return Response({"code": code, "message": _flatten(detail)}, status=status)


def _flatten(detail: Any) -> str:
    if isinstance(detail, dict):
        return "; ".join(f"{key}: {_flatten(value)}" for key, value in detail.items())
    if isinstance(detail, list):
        return "; ".join(_flatten(item) for item in detail)
    return str(detail)
