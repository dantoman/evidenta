"""The client's half of a support grant -- approval and revocation (ADR-077 §2, §5, §6).

Everything here runs under the client's own context, through the ordinary policy
on `support_grant`: a member with `tenant.approve_support_access` approves or
revokes, and the database holds the rules that must not depend on this file --
the approval carries its expiry, the window is at most 72 hours, nobody approves
their own request. What this module adds is the default window, the permission
check, and the notifications.

The **request** is not here. It is `P-7`, written by `rls.request_support_access`
from the console (`services/console.py`); the application role cannot INSERT into
the table at all.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from evidenta.platform.identity.services.roles import require_permission
from evidenta.platform.notifications.services.dispatch import notify_tenant
from evidenta.platform.rls.context import current_context
from evidenta.platform.support.models import SupportGrant

#: ADR-077 §3: "fereastra implicită propusă: 24 de ore; maximul, 72". The maximum
#: is also a CHECK in the database (0077); this is the service's copy, so the
#: refusal reads as a sentence rather than as a constraint name.
DEFAULT_WINDOW = timedelta(hours=24)
MAX_WINDOW = timedelta(hours=72)

APPROVE_KEY = "tenant.approve_support_access"


class SupportGrantError(RuntimeError):
    code = "support.invalid"
    status = 400


class GrantNotFoundError(SupportGrantError):
    code = "support.grant_not_found"
    status = 404


class GrantNotPendingError(SupportGrantError):
    code = "support.not_pending"
    status = 409


class GrantNotLiveError(SupportGrantError):
    code = "support.not_live"
    status = 409


class WindowInvalidError(SupportGrantError):
    code = "support.window_invalid"


class SelfApprovalError(SupportGrantError):
    code = "support.self_approval"
    status = 409


class NoContextError(SupportGrantError):
    code = "api.tenant_context_missing"
    status = 403


def _context() -> tuple[uuid.UUID, uuid.UUID]:
    context = current_context()
    if context is None:
        raise NoContextError("support grants are the tenant's; there is no tenant in context")
    return context.tenant_id, context.user_id


def list_grants() -> list[SupportGrant]:
    """Every grant of the space in context -- pending, live, expired, revoked."""
    tenant_id, _ = _context()
    # No `select_related` through the user keys: `user` is self-row, so an INNER
    # JOIN to it would drop every grant requested by somebody else -- which is
    # every grant. Measured: the list came back empty for the space's own owner.
    # The ids are all the serialiser needs.
    return list(SupportGrant.objects.filter(tenant_id=tenant_id).order_by("-requested_at"))


def session_grant() -> SupportGrant | None:
    """The grant the current session runs on, if it is a support session."""
    context = current_context()
    if context is None or context.support_grant_id is None:
        return None
    return SupportGrant.objects.filter(pk=context.support_grant_id).first()


def approve(grant_id: uuid.UUID, *, hours: int | None = None) -> SupportGrant:
    """Consent, by a member of the client, for a bounded window.

    The permission check is the ordinary one -- roles as data (ADR-020) -- and
    the write goes through the ordinary policy. The database refuses the cases
    the decision names (self-approval, a window over 72 hours, an approval
    without a term); the checks below say the same things in words, first.
    """
    tenant_id, user_id = _context()
    require_permission(user_id, tenant_id, APPROVE_KEY)
    window = DEFAULT_WINDOW if hours is None else timedelta(hours=hours)
    if window <= timedelta(0) or window > MAX_WINDOW:
        raise WindowInvalidError(
            f"the support window is between 1 and {int(MAX_WINDOW.total_seconds() // 3600)} "
            f"hours; {hours} was asked"
        )
    grant = SupportGrant.objects.filter(pk=grant_id, tenant_id=tenant_id).first()
    if grant is None:
        raise GrantNotFoundError(f"no support request {grant_id} in this space")
    if grant.revoked_at is not None or grant.approved_at is not None:
        raise GrantNotPendingError("only a pending request is approved")
    if grant.requested_by_id == user_id:
        raise SelfApprovalError("nobody approves their own request")
    now = datetime.now(tz=UTC)
    grant.approved_by_id = user_id
    grant.approved_at = now
    grant.expires_at = now + window
    grant.save(update_fields=["approved_by", "approved_at", "expires_at"])
    notify_tenant(
        tenant_id=tenant_id,
        type_key="support.approved",
        params={"request_ref": grant.request_ref, "expires_at": grant.expires_at.isoformat()},
        company_id=grant.company_id,
    )
    return grant


def revoke(grant_id: uuid.UUID) -> SupportGrant:
    """The client cuts the access -- any time, no reason required (ADR-077 §6).

    Sessions running on the grant end with it: `rls.resolve_session` refuses a
    session whose grant is revoked, so the next request of the support session is
    a 401, not a screen failing row by row. No second write is needed here.
    """
    tenant_id, user_id = _context()
    require_permission(user_id, tenant_id, APPROVE_KEY)
    grant = SupportGrant.objects.filter(pk=grant_id, tenant_id=tenant_id).first()
    if grant is None:
        raise GrantNotFoundError(f"no support request {grant_id} in this space")
    if grant.revoked_at is not None:
        raise GrantNotLiveError("the request is already revoked")
    if grant.expires_at is not None and grant.expires_at <= datetime.now(tz=UTC):
        raise GrantNotLiveError("the grant has already expired")
    grant.revoked_at = datetime.now(tz=UTC)
    grant.revoked_by_id = user_id
    grant.save(update_fields=["revoked_at", "revoked_by"])
    notify_tenant(
        tenant_id=tenant_id,
        type_key="support.revoked",
        params={"request_ref": grant.request_ref},
        company_id=grant.company_id,
    )
    return grant


def status_of(grant: SupportGrant, *, now: datetime | None = None) -> str:
    """pending | active | expired | revoked -- derived, never stored."""
    moment = now or datetime.now(tz=UTC)
    if grant.revoked_at is not None:
        return "revoked"
    if grant.approved_at is None:
        return "pending"
    if grant.expires_at is not None and grant.expires_at <= moment:
        return "expired"
    return "active"
