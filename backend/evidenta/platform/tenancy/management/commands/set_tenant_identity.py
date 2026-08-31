"""Record the account holder's own fiscal identity -- IDNO and legal form.

**Why a command.** Who may register a tenant *through the product* is `DN-26`,
still open, so ``create_tenant`` is the registration path and this is its
companion: the same operator act, for a tenant that already exists. Editing the
holder's identity from inside the product needs a permission key nobody has
decided on -- ``tenant.manage_roles`` is about roles and stretching it here would
be inventing a right, which is exactly what the catalogue exists to prevent
(ADR-020).

It runs under the installation role, like the other two operator commands, and
for the same measured reason: the policy on ``tenant`` is written
``TO evidenta_app``, so the owner has no applicable policy and is refused.

**It does not create the holder's company.** ADR-075: proposed, never imposed. A
company carries an accounting start date and a functional currency, both of them
decisions with consequences on the first posting, and a default chosen here would
be a wrong start date nobody noticed choosing.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from evidenta.platform.rls.context import unguarded
from evidenta.platform.rls.installation import (
    InstallationRoleError,
    bind_default_to_installation_role,
)
from evidenta.platform.tenancy.models import Tenant

IDNO_DIGITS = 13


class Command(BaseCommand):
    help = "Record a tenant's IDNO and legal form. Operator command."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--subdomain", required=True)
        parser.add_argument("--idno", required=True)
        parser.add_argument(
            "--legal-form",
            default=None,
            help='Free text -- "SRL", "ÎI", "SA". No enumeration is checked: the '
            "classifier of legal forms is not in this repository.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        idno = options["idno"].strip()
        # Shape only, thirteen digits -- the same check the company endpoint
        # makes, and for the same reason: the checksum rule is not in a text this
        # repository has, and a made-up one would refuse real firms.
        if not (idno.isdigit() and len(idno) == IDNO_DIGITS):
            raise CommandError(f"IDNO are {IDNO_DIGITS} cifre")

        try:
            bind_default_to_installation_role()
        except InstallationRoleError as unavailable:
            raise CommandError(str(unavailable)) from unavailable

        subdomain = options["subdomain"].strip().lower()
        with unguarded("set_tenant_identity: the account holder precedes every context"):
            updated = Tenant.objects.filter(subdomain=subdomain).update(
                idno=idno, legal_form=options["legal_form"]
            )
            if not updated:
                raise CommandError(f"nu există tenantul {subdomain!r}")

        self.stdout.write(f"{subdomain}: IDNO {idno}, formă {options['legal_form'] or '—'}")
