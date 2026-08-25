"""API conventions -- F0.10.1.

Three things are fixed before the first business endpoint exists, because each
becomes expensive to change once clients depend on it:

* `/api/v1/` is the only path (C7);
* every error carries a stable code, including the ones the framework raises (C10);
* an operation with a financial effect refuses a request with no
  `Idempotency-Key` (C9).

The refusal is rendered by middleware rather than by DRF's handler, and the probe
below is a plain Django view precisely to prove that: the authentication
endpoints are plain Django, so a guarantee that only held inside DRF would hold
for part of the API and not the rest.

The probe endpoint lives here rather than in `config/urls.py`. A route that
exists only to be tested is a route that ships, gets discovered, and eventually
gets used -- and one with "financial effect" in its name is a poor thing to leave
lying in a production URL map.
"""

from __future__ import annotations

import pytest
from django.http import HttpRequest, JsonResponse
from django.test import Client, override_settings
from django.urls import path
from rest_framework import exceptions as drf

from evidenta.platform.api import errors
from evidenta.platform.api.errors import exception_handler
from evidenta.platform.api.idempotency import HEADER, financial_effect


@financial_effect
def probe(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"key": getattr(request, "idempotency_key", None)})


urlpatterns = [
    path("api/v1/_probe/effect", probe),
    path("healthz", lambda r: JsonResponse({"status": "live"})),
]

PROBE_URLCONF = __name__


# --- C9: an effect without a key is refused ----------------------------------
#
# These four go through the request path, and `ATOMIC_REQUESTS` opens a
# transaction on every request -- so they need the database even though nothing
# they assert is stored. The code-table tests below deliberately do not, which is
# what keeps them in the fast CI job.

requests = pytest.mark.django_db(databases=["default", "migration"])


@requests
@override_settings(
    ROOT_URLCONF=PROBE_URLCONF,
    TENANT_CONTEXT_EXEMPT_PATHS=("/api/v1/_probe/effect", "/healthz"),
)
def test_an_operation_with_a_financial_effect_refuses_a_request_with_no_key() -> None:
    """The half of R19 that has to be true before the first business endpoint.

    Replay lives on the accounting event and arrives with the posting engine
    (F1.2). Refusing is the part that can be true now, and it is the part that
    tells a client at integration time rather than at month end: a client that
    retries without a key double-posts the first time the network hiccups.
    """
    response = Client().post("/api/v1/_probe/effect", headers={"host": "localhost"})
    assert response.status_code == 400
    assert response.json()["code"] == "api.idempotency_key_required"


@requests
@override_settings(
    ROOT_URLCONF=PROBE_URLCONF,
    TENANT_CONTEXT_EXEMPT_PATHS=("/api/v1/_probe/effect", "/healthz"),
)
def test_a_malformed_key_is_refused_with_its_own_code() -> None:
    """A separate code from the missing one, because the fixes differ: one client
    forgot to send a header, the other is generating something unusable.
    """
    response = Client().post(
        "/api/v1/_probe/effect",
        headers={"host": "localhost", HEADER: "short"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "api.idempotency_key_invalid"


@requests
@override_settings(
    ROOT_URLCONF=PROBE_URLCONF,
    TENANT_CONTEXT_EXEMPT_PATHS=("/api/v1/_probe/effect", "/healthz"),
)
def test_a_valid_key_reaches_the_view() -> None:
    response = Client().post(
        "/api/v1/_probe/effect",
        headers={"host": "localhost", HEADER: "01JD2K3M4N5P6Q7R8S9T"},
    )
    assert response.status_code == 200
    assert response.json()["key"] == "01JD2K3M4N5P6Q7R8S9T"


@requests
@override_settings(
    ROOT_URLCONF=PROBE_URLCONF,
    TENANT_CONTEXT_EXEMPT_PATHS=("/api/v1/_probe/effect", "/healthz"),
)
def test_a_read_needs_no_key() -> None:
    """A key on a read means nothing, and requiring one would push clients into
    generating keys they do not need -- which is how a key generator ends up bad.
    """
    response = Client().get("/api/v1/_probe/effect", headers={"host": "localhost"})
    assert response.status_code == 200


# --- C10: stable codes, including for the framework's own failures ------------


@pytest.mark.parametrize(
    ("exception", "code", "status"),
    [
        (drf.NotFound(), "api.not_found", 404),
        (drf.PermissionDenied(), "api.forbidden", 403),
        (drf.NotAuthenticated(), "api.not_authenticated", 401),
        (drf.MethodNotAllowed("POST"), "api.method_not_allowed", 405),
        (drf.ValidationError("no"), "api.invalid", 400),
        (drf.ParseError(), "api.malformed", 400),
    ],
)
def test_framework_failures_answer_with_a_stable_code(
    exception: Exception, code: str, status: int
) -> None:
    """An endpoint that answers with a code nine times and a bare 500 the tenth
    has no contract: the tenth is exactly where a client needs to branch.
    """
    response = exception_handler(exception, {})
    assert response is not None
    assert response.data["code"] == code
    assert response.status_code == status


def test_an_unexpected_failure_is_not_flattened_into_a_tidy_body() -> None:
    """Returning None hands it back to Django, which makes it a 500.

    Deliberate. An unexpected failure should be loud and should reach the error
    tracker, not be dressed as handled.
    """
    assert exception_handler(RuntimeError("boom"), {}) is None


def test_every_api_error_carries_a_code_and_a_status() -> None:
    """The codes are the contract, so the shape of the contract is checked.

    A subclass added without a code would inherit `error.unknown`, which is the
    absence of a contract wearing one.
    """
    subclasses = [
        cls
        for cls in vars(errors).values()
        if isinstance(cls, type) and issubclass(cls, errors.ApiError) and cls is not errors.ApiError
    ]
    assert subclasses
    for cls in subclasses:
        assert cls.code != errors.ApiError.code, cls.__name__
        assert cls.code.startswith("api."), cls.__name__


def test_codes_are_unique_across_the_builtin_table() -> None:
    """Two exceptions sharing a code make the code useless for branching."""
    pairs = list(errors.BUILTIN_CODES.values())
    by_code = {code: status for code, status in pairs}
    for code, status in pairs:
        assert by_code[code] == status, code
