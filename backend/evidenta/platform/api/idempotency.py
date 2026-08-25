"""`Idempotency-Key` on endpoints with a financial effect -- C9, R19.

**What this does and, more importantly, what it deliberately does not.**

R19 puts the idempotency key on the **accounting event**, not on the endpoint:
`UNIQUE (company_id, idempotency_key)` on `accounting_event` (Spec B 1.1, 10.1).
That table arrives with the posting engine, in F1.2. So replay -- returning the
first execution's result for a repeated key -- is not implemented here, and
building an endpoint-level replay cache now would be building precisely the thing
R19 says is insufficient, then tearing it out when the real one lands.

What F0 fixes is the half that has to be true before the first business endpoint
exists: **an operation with a financial effect refuses a request that carries no
key.** Refusing is safe in a way that guessing is not -- a client that retries
without a key is a client that will double-post the day the network hiccups, and
the refusal tells them at integration time rather than at month end.

DNB-10 -- whether an API key may be reused after a window, or is permanent --
stays open, and nothing here assumes an answer. The 24-hour window is the
industry convention and would be a plausible thing to write; in an accounting
system it is also the thing that decides whether a client who generates keys
badly blocks legitimate operations forever.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from functools import wraps
from typing import Any

from django.http import HttpRequest, HttpResponse

from evidenta.platform.api.errors import (
    IdempotencyKeyInvalidError,
    IdempotencyKeyRequiredError,
)

HEADER = "Idempotency-Key"

#: Bounded and printable. Not a format anyone has to follow -- a UUID, a ULID and
#: a source-system reference all pass -- but a key is stored, indexed and compared,
#: so an unbounded one is a way to make a unique index expensive from outside.
KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,255}$")

#: Methods that can produce an effect. GET and HEAD are excluded because a key on
#: a read means nothing; DELETE is included because deleting twice is exactly the
#: retry this protects against.
EFFECTFUL_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def read_key(request: HttpRequest) -> str:
    """The validated key, or a refusal with a stable code."""
    raw = request.headers.get(HEADER)
    if not raw:
        raise IdempotencyKeyRequiredError(
            f"{HEADER} is required on an operation with a financial effect. A "
            f"retry without one double-posts."
        )
    if not KEY_PATTERN.match(raw):
        raise IdempotencyKeyInvalidError(
            f"{HEADER} must be 8-255 characters of A-Z a-z 0-9 . _ : -"
        )
    return raw


def financial_effect(view: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
    """Mark a view as producing a financial effect, and enforce C9 on it.

    A decorator rather than middleware applied to a path prefix, deliberately.
    Which operations have a financial effect is a property of the operation, and
    a prefix rule would either cover reads it should not or miss an endpoint
    somebody adds under a different path -- and missing one fails open.
    """

    @wraps(view)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if request.method in EFFECTFUL_METHODS:
            request.idempotency_key = read_key(request)  # type: ignore[attr-defined]
        return view(request, *args, **kwargs)

    wrapper.has_financial_effect = True  # type: ignore[attr-defined]
    return wrapper
