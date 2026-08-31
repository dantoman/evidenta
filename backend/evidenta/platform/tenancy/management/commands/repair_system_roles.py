"""Re-seed a tenant's system roles, so an interrupted creation is not permanent.

**Why this exists, measured.** The development tenant `alpha` carries the role
``owner`` with **zero** permissions and no ``company_admin`` role at all, while
`proba` and `proba2` -- created later, by the same command -- carry seven and one.
Nothing shouted: no test covers a tenant created before the seeding existed, and
every check stayed green, because a role with no permissions is a valid row. The
first symptom would have been a refusal in the one place that matters: the
workspace owner unable to edit their own roles.

``create_system_roles`` is idempotent by design -- ``get_or_create`` on both the
role and each permission -- so this command is a thin operator wrapper around it
rather than a second implementation of the seeding. A second implementation is
exactly how the two would drift.

It runs under the **installation role**, like ``create_tenant`` and for the same
reason: the policies on ``role`` and ``role_permission`` are written
``TO evidenta_app``, so the owner has no applicable policy and is refused.

**It lives in ``tenancy`` although it repairs roles**, and the dependency guard is
what decided that: the command iterates tenants, and a command in ``identity``
would have to import ``tenancy.models`` -- which `D6` refuses. From here it asks
``identity`` through ``create_system_roles``, a public service, which is the
direction the graph allows.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from evidenta.platform.identity.services.roles import create_system_roles, permission_counts
from evidenta.platform.rls.context import unguarded
from evidenta.platform.rls.installation import (
    InstallationRoleError,
    bind_default_to_installation_role,
)
from evidenta.platform.tenancy.models import Tenant


class Command(BaseCommand):
    help = "Repair the system roles of one tenant, or of every tenant. Operator command."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--subdomain", default=None)
        parser.add_argument(
            "--all",
            action="store_true",
            help="Repair every tenant. Idempotent, so a healthy tenant is a no-op.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        subdomain = options["subdomain"]
        if not subdomain and not options["all"]:
            raise CommandError("alegeți --subdomain <nume> sau --all")

        try:
            bind_default_to_installation_role()
        except InstallationRoleError as unavailable:
            raise CommandError(str(unavailable)) from unavailable

        # The repair precedes any context by definition: it fixes the rows a
        # context would be established from.
        with unguarded("repair_system_roles: repairs the rows a context is built from"):
            tenants = Tenant.objects.all().order_by("subdomain")
            if subdomain:
                tenants = tenants.filter(subdomain=subdomain.strip().lower())
                if not tenants.exists():
                    raise CommandError(f"nu există tenantul {subdomain!r}")

            for tenant in tenants:
                create_system_roles(tenant.id)
                # The count, not just the name: "owner exists" was true of the
                # broken tenant too. What was missing was what the role held.
                held = ", ".join(
                    f"{key}: {count}" for key, count in sorted(permission_counts(tenant.id).items())
                )
                self.stdout.write(f"{tenant.subdomain} — {held}")
