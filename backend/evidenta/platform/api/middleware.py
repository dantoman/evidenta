"""Turning an `ApiError` into a response, whatever kind of view raised it.

DRF's exception handler runs only inside DRF views. The authentication endpoints
are plain Django (F0.3.7c, because API conventions were still open and had no
business being settled there by accident), and business endpoints will be DRF. So
a guarantee that lives only in the DRF handler would hold for some of the API and
not the rest -- and C10 is a guarantee about the API, not about a framework.

Placed **inside** the tenant context middleware so the transaction is still open
when the error is rendered: an `ApiError` raised by a service must roll the
transaction back, and a middleware that caught it outside the context would turn
a partial write into a tidy 400.
"""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse, JsonResponse

from evidenta.platform.api.errors import ApiError


class ApiErrorMiddleware:
    """Render `ApiError` as `{"code": ..., "message": ...}`.

    Only `ApiError`. Anything else passes through to Django and becomes a 500 --
    an unexpected failure should be loud and reach the error tracker, not be
    dressed as handled.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        return self.get_response(request)

    def process_exception(self, request: HttpRequest, exception: Exception) -> HttpResponse | None:
        """The hook that actually sees a view's exception.

        Not a `try/except` around `get_response`, which is the obvious shape and
        the wrong one: Django wraps each middleware layer so an exception from a
        view is turned into a response *before* it reaches an outer layer's
        except clause. The obvious version passes its tests only if the tests use
        DRF views, and then fails silently on the plain Django ones -- which is
        the half of the API this middleware exists for.
        """
        if not isinstance(exception, ApiError):
            return None
        body: dict[str, object] = {"code": exception.code, "message": str(exception)}
        if exception.context:
            body["context"] = exception.context
        return JsonResponse(body, status=exception.status)
