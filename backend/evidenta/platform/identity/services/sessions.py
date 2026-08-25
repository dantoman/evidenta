"""Session lifecycle -- the half of revocation that RLS does not cover.

Revoking an engagement cuts access at the database immediately: every policy
re-evaluates on every query, so the firm's next request returns nothing whatever
its session says. This module exists for what that leaves behind -- an interface
still open, still polling, failing one request at a time instead of ending.

So this is a usability guarantee sitting on top of a security one, and it is
worth being precise about which is which: if this module were deleted, nothing
would leak. If RLS were deleted, everything would.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime

from django.db import transaction

from evidenta.platform.identity import privileged
from evidenta.platform.identity.models import UserSession
from evidenta.platform.identity.privileged import ResolvedSession


def invalidate_sessions_for_engagement(
    client_tenant_id: uuid.UUID, firm_id: uuid.UUID, reason: str
) -> int:
    """End every live session of a firm acting for one tenant.

    Matched on the pair, not on the user: the same person may hold sessions for
    several clients of the same firm, and revoking one client must not log them
    out of the others.
    """
    with transaction.atomic():
        return UserSession.objects.filter(
            tenant_id=client_tenant_id,
            actor_firm_id=firm_id,
            revoked_at__isnull=True,
        ).update(revoked_at=datetime.now(UTC), revocation_reason=reason)


def invalidate_sessions_for_user(user_id: uuid.UUID, reason: str) -> int:
    """End every live session of one user, everywhere.

    For deactivation and for password or MFA changes -- the cases where the
    account itself, rather than one relationship, is what changed.
    """
    with transaction.atomic():
        return UserSession.objects.filter(user_id=user_id, revoked_at__isnull=True).update(
            revoked_at=datetime.now(UTC), revocation_reason=reason
        )


def is_live(session: UserSession, *, now: datetime | None = None) -> bool:
    """A session is live only while it is neither revoked nor expired."""
    moment = now or datetime.now(UTC)
    return session.revoked_at is None and session.expires_at > moment


#: Bytes of entropy in a session token. 32 raw bytes -- 256 bits -- because the
#: token is the whole credential for the life of the session: there is no second
#: factor on a request, only this.
TOKEN_BYTES = 32


def new_token() -> str:
    """A session token. Returned to the browser once and never stored in clear."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def fingerprint(token: str) -> str:
    """What is stored and what is looked up.

    Plain SHA-256, deliberately unsalted, unlike a password hash. A password is
    low-entropy and must resist a dictionary; a 256-bit random token has no
    dictionary to resist, and a per-row salt would make lookup by token
    impossible -- turning every request into a scan of every session.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def resolve(token: str) -> ResolvedSession | None:
    """The live session behind a token from the request, or None.

    Runs before any tenant context exists, so it goes through the privileged
    path -- see :mod:`evidenta.platform.identity.privileged`.
    """
    return privileged.resolve_session(fingerprint(token))


def revoke(session_id: uuid.UUID, reason: str) -> bool:
    """End one session -- the caller's own.

    Through the ORM rather than a privileged path, and that is the whole point:
    logout happens *inside* an established context, where ``user_session_self``
    already permits a user to write their own row. False means there was nothing
    live to end, which is what a second logout looks like.
    """
    return (
        UserSession.objects.filter(pk=session_id, revoked_at__isnull=True).update(
            revoked_at=datetime.now(UTC), revocation_reason=reason
        )
        > 0
    )
