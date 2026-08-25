"""Fetching one row by identifier -- IZ-04.

    "UA cere prin API o resursă a lui B, după `id` -> 404, nu 403 --
     existența nu se dezvăluie."

**404, never 403, and the distinction is not politeness.** A 403 says "this
exists and is not yours". Over a sequence of identifiers that is an enumeration
oracle: a competitor with a client list can learn which of them keep their books
here, and a tenant can measure another tenant's volume by probing ranges. A 404
says nothing at all.

The convenient part is that RLS produces the right answer without being asked.
A row of another tenant is not visible, so the query returns nothing and the
lookup raises `DoesNotExist` -- the same exception as an identifier that was
never issued. There is no branch where the code learns the row exists and then
decides what to say, which is the branch that eventually gets written wrong.

So this module is small on purpose: it is a named place to state the rule and a
function that makes the easy path the correct one, not a mechanism.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Model, QuerySet

from evidenta.platform.api.errors import ApiError


class NotFoundError(ApiError):
    """The row is not there, or is not visible. Deliberately the same answer."""

    code = "api.not_found"
    status = 404


def get_or_404[M: Model](rows: QuerySet[M], **lookup: Any) -> M:
    """One row, or a 404 that does not distinguish absence from invisibility.

    Takes a queryset rather than a model class so the caller cannot accidentally
    reach past a narrowing already applied -- and so the tenant context is
    whatever the surrounding transaction set, never something this function
    guesses.
    """
    try:
        return rows.get(**lookup)
    except ObjectDoesNotExist:
        raise NotFoundError("resource not found") from None
