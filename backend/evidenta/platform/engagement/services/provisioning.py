"""Extending engagement-derived company access to a company created later.

The counterpart of ``revocation``. Both go through a narrow SECURITY DEFINER
function rather than the ORM, and for the same reason: the policy on
``company_access`` is ``user_id = app.current_user_id()``, so a session sees only
its own rows. Writing another user's access through the ORM is not restricted --
it is invisible, which is worse, because the ORM would report success over rows
it never saw.

What this does not do is decide who serves a client. Provisioning follows the
grants that already exist: whoever holds engagement-derived access to this
tenant's companies gets the new one too. Who gets the first grant is ``OD-42``,
and it is open -- so this function cannot be used to answer it by accident.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from django.db import connection


@dataclass(frozen=True)
class Provisioned:
    company_id: uuid.UUID
    access_granted: int


def provision_company_access(company_id: uuid.UUID) -> Provisioned:
    """Extend live engagement-derived access to ``company_id``.

    Call it from whatever creates a company, in the same transaction. Today
    nothing does: there is no production path that creates a company at all
    (``OD-53``). The function exists first because the rule it enforces belongs
    to the engagement, not to the screen that will eventually call it.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rls.provision_engagement_company_access(%s)",
            [str(company_id)],
        )
        row = cursor.fetchone()

    return Provisioned(company_id=company_id, access_granted=int(row[0]))
