"""The permission catalogue -- ADR-020.

The client composes **roles**, never permissions. This list is what makes that
safe: a role may hold only keys the product knows and checks somewhere, so no
combination of roles produces a right nobody anticipated. The client can be wrong
about *who* gets a right -- that is their business -- but cannot invent one.

Two rules keep the list honest:

1. **A key appears here only when something enforces it.** A permission with no
   enforcement point is a promise the product does not keep, and it is worse than
   a missing one: it reads as protection in an administration screen while
   granting nothing and blocking nothing.
2. **No labels here.** The catalogue carries keys and scope. What a permission is
   called in the interface lives in the frontend resource files (C32), in
   Romanian, next to every other string -- not in a database column that would
   have to be translated by a migration.

Adding a key is a migration, deliberately: the table is fed from this list, and a
row written freely into it would be a right with no code behind it.
"""

from __future__ import annotations

from typing import Final, NamedTuple


class PermissionScope:
    """Where a permission applies. A role holds keys of its own scope only."""

    TENANT: Final = "tenant"
    COMPANY: Final = "company"

    values: Final = (TENANT, COMPANY)


class PermissionDef(NamedTuple):
    key: str
    scope: str
    #: The code path that refuses without this permission. Not documentation --
    #: it is the evidence for rule 1 above, and the first thing to check when a
    #: key is proposed.
    enforced_in: str


PERMISSIONS: Final[tuple[PermissionDef, ...]] = (
    # The permission from which every other one can be derived: whoever holds it
    # can write roles. Granting it is mandatory audit (ADR-020).
    PermissionDef("tenant.manage_roles", PermissionScope.TENANT, "identity.services.roles"),
    # The engagement state machine -- Spec A section 4.2. One key per transition
    # the matrix allows, because they are not interchangeable: suspending is
    # reversible and revoking is not.
    PermissionDef("engagement.invite", PermissionScope.TENANT, "engagement.services.lifecycle"),
    PermissionDef("engagement.accept", PermissionScope.TENANT, "engagement.services.lifecycle"),
    PermissionDef("engagement.suspend", PermissionScope.TENANT, "engagement.services.lifecycle"),
    PermissionDef("engagement.resume", PermissionScope.TENANT, "engagement.services.lifecycle"),
    PermissionDef("engagement.transfer", PermissionScope.TENANT, "engagement.services.lifecycle"),
    PermissionDef("engagement.revoke", PermissionScope.TENANT, "engagement.services.revocation"),
    # Company-scoped access, granted and withdrawn per company.
    PermissionDef(
        "company.revoke_access", PermissionScope.COMPANY, "engagement.services.revocation"
    ),
    # ADR-083. Two keys rather than one: closing is irreversible in practice and
    # has no business travelling with the correction of an address. Company
    # scope, so a holding can put somebody in charge of one company without
    # handing them the others.
    PermissionDef("company.edit", PermissionScope.COMPANY, "tenancy.services.companies"),
    PermissionDef("company.close", PermissionScope.COMPANY, "tenancy.services.companies"),
    # ADR-077 §5. The client's half of a support grant: approving and revoking the
    # platform's read-only access to their own data. Tenant scope, because the
    # grant is the space's -- held implicitly by the administration role created
    # with the space.
    PermissionDef(
        "tenant.approve_support_access", PermissionScope.TENANT, "support.services.grants"
    ),
)

PERMISSION_KEYS: Final[tuple[str, ...]] = tuple(p.key for p in PERMISSIONS)

#: The key that guards the catalogue itself. Named rather than repeated as a
#: literal: it is checked in more than one place, and a typo in a permission
#: string fails open in exactly the way permissions exist to prevent.
MANAGE_ROLES: Final = "tenant.manage_roles"


def permissions_for_scope(scope: str) -> tuple[str, ...]:
    """Keys valid at one scope. Used when composing the system roles."""
    return tuple(p.key for p in PERMISSIONS if p.scope == scope)
