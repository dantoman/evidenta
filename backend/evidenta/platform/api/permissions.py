"""Who may knock on a console door -- the check ADR-076 §4.1 asserted in prose.

`OD-113` records the gap this closes for the doors that exist: "operator runs P-4"
was a sentence in an ADR and nothing in code refused a `support` the call. These
classes are that refusal. They read the caller's live row in `platform_staff`,
inside the request's own context and through the table's self-row policy, so the
answer is the database's and not a cached claim.

A caller with no row at all cannot reach here in practice -- the console login
issues no session to them -- but the class does not rely on that: a session that
outlived a revocation is exactly the case a per-request check exists for.

Denied is 403 `api.forbidden` through the error handler (C10). Not 404: the route
exists, and the person is signed in; what they lack is the role.
"""

from __future__ import annotations

from typing import Any

from rest_framework.permissions import BasePermission

from evidenta.platform.api.authentication import StaffPrincipal
from evidenta.platform.identity.services.staff import staff_role_in_context


class PlatformStaffPermission(BasePermission):
    """Base: the caller is a live platform employee holding one of ``roles``.

    Subclasses name the roles. An empty set would admit nobody, which is the
    right default for a class somebody forgot to configure.
    """

    roles: frozenset[str] = frozenset()

    def has_permission(self, request: Any, view: Any) -> bool:
        principal = getattr(request, "user", None)
        if not isinstance(principal, StaffPrincipal):
            return False
        membership = staff_role_in_context(principal.user_id)
        if membership is None or membership.staff_role not in self.roles:
            return False
        # For the view and for the log row: who acted, as which role.
        request.platform_staff = membership
        return True


class IsPlatformStaff(PlatformStaffPermission):
    """Any live employee: the console's read side."""

    roles = frozenset({"support", "operator", "admin"})


class IsPlatformOperator(PlatformStaffPermission):
    """The reference-data paths -- `P-3`, `P-4`, `P-5`, `P-10` (ADR-076 §4.1)."""

    roles = frozenset({"operator"})


class IsPlatformAdmin(PlatformStaffPermission):
    """Administers `platform_staff` itself, and nothing else (ADR-076 §4.1)."""

    roles = frozenset({"admin"})


class IsPlatformSupport(PlatformStaffPermission):
    """May *request* a support grant (ADR-077 §5) -- and touches nothing else."""

    roles = frozenset({"support"})
