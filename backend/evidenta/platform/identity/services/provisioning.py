"""Creating a user and attaching them to a tenant.

Exists because `D6` asks for it: creating the first tenant needs both halves --
the tenant, which is `tenancy`, and the person, who is `identity` -- and a
command that reached into this module's models to do it would be the direct
import the rule is about. The rule is not ceremony here: what a membership must
carry to be valid (an acceptance behind every active row, a system role of the
right level) is this module's knowledge, and a caller assembling the row itself
would be re-deriving it.

**Not an invitation flow, and not a sign-up.** Who may create a user through the
product, and how they are invited, is not answered here -- `OD-48` is the reason
enrolment has no request path at all. These two functions are what a privileged
caller needs and nothing more.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from django.contrib.auth.hashers import make_password

from evidenta.platform.identity.models import Membership, MembershipStatus, Role, User


def user_by_email(email: str) -> User | None:
    """The user with this address, or None. Addresses are unique and lowercased."""
    return User.objects.filter(email=email.strip().lower()).first()


def create_user(*, email: str, full_name: str, password: str, locale: str = "ro") -> User:
    """One user, with a hashed password and no second factor yet.

    `mfa_enabled` stays false because enrolment is a separate act with its own
    services: setting the flag here would claim a second factor that does not
    exist, and `authenticate()` would then refuse the sign-in with a message
    about a missing method rather than about a missing enrolment.
    """
    now = datetime.now(UTC)
    return User.objects.create(
        id=uuid.uuid4(),
        email=email.strip().lower(),
        full_name=full_name or email,
        password_hash=make_password(password),
        mfa_enabled=False,
        locale=locale,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def create_membership(*, tenant_id: uuid.UUID, user_id: uuid.UUID, role: Role) -> Membership:
    """Attach a user to a tenant, active from now.

    `accepted_at` is set because an active membership must carry one -- a check
    constraint, not a convention (`membership_active_requires_acceptance`). A
    caller who left it out would get a database error describing a column rather
    than the rule, which is why the rule lives here.
    """
    now = datetime.now(UTC)
    return Membership.objects.create(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        role_id=role.id,
        status=MembershipStatus.ACTIVE,
        invited_at=now,
        accepted_at=now,
        created_at=now,
        updated_at=now,
    )
