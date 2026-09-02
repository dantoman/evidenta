"""Handing DRF the identity the session middleware already established.

The session is resolved by ``SessionAuthenticationMiddleware``, which runs before
the tenant context and attaches ``request.authenticated_user_id``. DRF knows
nothing about that, and its default is to treat every request as anonymous -- so
without this class every business endpoint would answer 401 while the plain
Django endpoints answered normally, for the same cookie.

**This class authenticates nothing.** It adopts a decision already made, one
layer out. Putting the session lookup here as well would give the product two
places that decide who the caller is, and two such places eventually disagree --
the disagreement being resolved in favour of whichever ran first, which is not a
property anyone chose.

``django.contrib.auth`` is deliberately not installed, so there is no ``User``
model to hand back. ``Principal`` is the minimum DRF's permission classes need: a
truthy object that answers ``is_authenticated``. It is intentionally not a model
-- a lazily-evaluated user object is exactly the shape that produces a query with
no tenant context, three layers deep in something that looks like presentation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from rest_framework.authentication import BaseAuthentication


@dataclass(frozen=True, slots=True)
class Principal:
    """Who the caller is, as far as an endpoint needs to know.

    Carries the tenant and the acting firm because both are already established
    and re-deriving either inside a view would mean a second answer to a question
    the middleware answered.
    """

    user_id: UUID
    tenant_id: UUID
    actor_firm_id: UUID | None = None

    @property
    def is_authenticated(self) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class StaffPrincipal:
    """The caller on the console host -- a person and **no tenant** (ADR-076).

    A separate class rather than a `Principal` with a null tenant, so that a
    business view reading ``request.user.tenant_id`` keeps its type and its
    guarantee: on the console there is no such attribute to read. Which staff
    role the person holds is not carried here -- it is a row, asked for inside
    the request's context by the permission class that needs it.
    """

    user_id: UUID

    @property
    def is_authenticated(self) -> bool:
        return True


class SessionIdentityAuthentication(BaseAuthentication):
    """Adopt ``request.authenticated_user_id``, or stay anonymous.

    Returning ``None`` rather than raising is the contract DRF expects from an
    authenticator that simply does not apply: raising here would turn "no cookie"
    into an error before the permission class ever got to say 401 with a stable
    code (C10).
    """

    def authenticate(self, request: Any) -> tuple[Principal | StaffPrincipal, None] | None:
        user_id = getattr(request, "authenticated_user_id", None)
        if user_id is None:
            return None
        tenant_id = getattr(request, "authenticated_tenant_id", None)
        if tenant_id is None:
            # A session with no tenant is a console session, and it reaches a
            # DRF view only on the console host: the tenant resolver refuses it
            # everywhere else before any view runs. So adopting it here does not
            # widen what a business endpoint can see -- there is no path from
            # this branch to one.
            return (StaffPrincipal(user_id=user_id), None)
        return (
            Principal(
                user_id=user_id,
                tenant_id=tenant_id,
                actor_firm_id=getattr(request, "authenticated_actor_firm_id", None),
            ),
            None,
        )
