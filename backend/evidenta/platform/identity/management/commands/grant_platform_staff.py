"""Make a user an employee of the platform -- the first `admin`, and the ones
after until the console has a screen for it (OD-133). Operator command.

**Why a command, and why this connection.** ADR-076 §4.1 says `admin`
administers `platform_staff`; it does not say how the first `admin` comes to
exist, and nothing can: the console issues sessions only to staff, so the first
grant precedes every console session. It is the same act as creating the first
tenant (`create_tenant`) and is spelled the same way -- under the installation
role, because every policy on the table is written `TO evidenta_app` or
`TO evidenta_refdata` and the owner has none.

**What it does not do.** It does not create users: a person is granted after
they exist and can sign in (`create_tenant`, or the product's own paths). It
writes no `privileged_access_log` row, because it is not a `P-*` path -- it is
the shell, and the shell's own history is its audit, exactly as for the
migrations. The path through which an `admin` grants from the console, with a log
row, is `OD-133`.

`--granted-by` names who is making the grant. Absent, the grant records itself
-- the bootstrap case, where nobody else exists yet.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from evidenta.platform.identity.models import StaffRole
from evidenta.platform.identity.services.provisioning import user_by_email
from evidenta.platform.identity.services.staff import StaffGrantError, grant_staff, revoke_staff
from evidenta.platform.rls.context import unguarded
from evidenta.platform.rls.installation import (
    InstallationRoleError,
    bind_default_to_installation_role,
)


class Command(BaseCommand):
    help = "Grant (or revoke) a platform staff role to an existing user. Operator command."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--email", required=True)
        parser.add_argument("--role", choices=StaffRole.values, default=None)
        parser.add_argument("--granted-by", default=None, help="e-mail of who grants")
        parser.add_argument("--revoke", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        if not options["revoke"] and not options["role"]:
            raise CommandError("--role is required unless --revoke is given")
        try:
            bind_default_to_installation_role()
        except InstallationRoleError as error:
            raise CommandError(str(error)) from error

        with (
            unguarded("operator command: a staff grant precedes any console session"),
            transaction.atomic(),
        ):
            user = user_by_email(options["email"])
            if user is None:
                raise CommandError(f"no user with e-mail {options['email']!r}")
            if options["revoke"]:
                if not revoke_staff(user=user):
                    raise CommandError(f"{user.email} holds no live staff role")
                self.stdout.write(f"{user.email}: rol de platformă retras")
                return
            granter = user_by_email(options["granted_by"]) if options["granted_by"] else user
            if granter is None:
                raise CommandError(f"no user with e-mail {options['granted_by']!r}")
            try:
                row = grant_staff(user=user, staff_role=options["role"], granted_by=granter)
            except StaffGrantError as error:
                raise CommandError(str(error)) from error

        self.stdout.write(
            f"{user.email}: {row.staff_role} al platformei, acordat de {granter.email}"
        )
