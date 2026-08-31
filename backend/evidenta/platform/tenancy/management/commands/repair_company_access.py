"""Put existing company access on a company-level role -- ADR-084, `OD-124`.

The companion of `repair_system_roles`, and it exists for the same reason that one
does: a defect that was written into rows cannot be fixed by fixing the code that
wrote them. `0072` corrects `rls.provision_company` for every company created from
now on; the rows already there still carry the creator's tenant-level role, and on
those rows no company-scoped key can be held.

**Not a migration.** Rewriting somebody's access from a migration -- under a role
that cannot see the rows it is rewriting -- is the failure `OD-94` exists to make
loud. An operator runs this, sees what moved, and can compare it against what they
expected.

Runs under the **installation role**, like `repair_system_roles`: the policy on
`company_access` is `user_id = app.current_user_id()`, so no ordinary context can
see another person's rows, which is exactly the rows that need repairing.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from evidenta.platform.identity.services.roles import RoleError, realign_company_access
from evidenta.platform.rls.context import unguarded
from evidenta.platform.rls.installation import (
    InstallationRoleError,
    bind_default_to_installation_role,
)
from evidenta.platform.tenancy.models import Tenant


class Command(BaseCommand):
    help = "Move membership-granted company access onto the company-level system role."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--subdomain", default=None)
        parser.add_argument(
            "--all",
            action="store_true",
            help="Every tenant. Idempotent, so a healthy tenant is a no-op.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        subdomain = options["subdomain"]
        if not subdomain and not options["all"]:
            raise CommandError("alegeți --subdomain <nume> sau --all")

        try:
            bind_default_to_installation_role()
        except InstallationRoleError as unavailable:
            raise CommandError(str(unavailable)) from unavailable

        with unguarded("repair_company_access: repairs rows no context can see"):
            tenants = Tenant.objects.all().order_by("subdomain")
            if subdomain:
                tenants = tenants.filter(subdomain=subdomain.strip().lower())
                if not tenants.exists():
                    raise CommandError(f"nu există tenantul {subdomain!r}")

            for tenant in tenants:
                try:
                    result = realign_company_access(tenant.id)
                except RoleError as missing:
                    # Loud and per tenant: one broken tenant does not stop the rest,
                    # and the reason names the command that fixes it.
                    self.stdout.write(f"{tenant.subdomain} — {missing}")
                    continue
                # Both numbers: "moved 0" is the healthy answer and the empty answer,
                # and the count of live rows is what tells them apart.
                self.stdout.write(
                    f"{tenant.subdomain} — accese vii: {result.live}, mutate: {result.moved}"
                )
