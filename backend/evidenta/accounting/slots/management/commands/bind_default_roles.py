"""Bind every catalogue role for the companies of a workspace, and declare the slots the roles need.

    manage.py bind_default_roles --subdomain alpha [--company "Alpha SRL"]

For companies whose chart was set up before a role existed -- the five payroll
roles of ADR-065 section 7 arrived after the first companies did, and a company
bound before them meets `slots.role_not_bound` at its first payroll run. The
installer is idempotent: a role already bound is left alone, a slot already
declared is left alone, and the new bindings are dated from the day the books
start, as chart setup dates them.

Operator command, like `seed_documents`: the tenant and an active member are read
on the installation connection, then everything runs under that member's context
so RLS and the audit trail see a person, not a shell.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from evidenta.accounting.slots.services.binding import install_default_bindings
from evidenta.platform.rls.context import TenantContext, tenant_context
from evidenta.platform.tenancy.services.companies import accounting_start_date


def _tenant_and_user(subdomain: str) -> tuple[uuid.UUID, uuid.UUID]:
    """Read on the installation connection -- `membership` answers nothing without a context."""
    if "admin" not in connections.databases:
        raise CommandError("conexiunea de instalare nu este configurată (DB_ADMIN_USER)")
    with connections["admin"].cursor() as cursor:
        cursor.execute(
            """
            SELECT t.id, m.user_id
              FROM tenant t
              JOIN membership m ON m.tenant_id = t.id AND m.status = 'active'
             WHERE t.subdomain = %s
             ORDER BY m.created_at
             LIMIT 1
            """,
            [subdomain],
        )
        row = cursor.fetchone()
    if row is None:
        raise CommandError(f"nu există tenantul {subdomain!r} cu un membru activ")
    return uuid.UUID(str(row[0])), uuid.UUID(str(row[1]))


def _companies(tenant_id: uuid.UUID, only: str | None) -> list[tuple[uuid.UUID, str]]:
    with connections["admin"].cursor() as cursor:
        cursor.execute(
            "SELECT id, legal_name FROM company WHERE tenant_id = %s"
            + (" AND legal_name = %s" if only else "")
            + " ORDER BY legal_name",
            [tenant_id, only] if only else [tenant_id],
        )
        rows = cursor.fetchall()
    if not rows:
        raise CommandError("nicio companie în acest spațiu de lucru")
    return [(uuid.UUID(str(r[0])), str(r[1])) for r in rows]


class Command(BaseCommand):
    help = "Leagă rolurile de cont lipsă și declară sloturile lor, pentru companiile unui spațiu."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--subdomain", required=True)
        parser.add_argument("--company", default=None, help="Implicit: toate companiile.")

    def handle(self, *args: Any, **options: Any) -> None:
        tenant_id, user_id = _tenant_and_user(options["subdomain"].strip().lower())
        context = TenantContext(
            tenant_id=tenant_id, user_id=user_id, request_id="bind_default_roles"
        )
        with tenant_context(context):
            for company_id, name in _companies(tenant_id, options["company"]):
                made = install_default_bindings(
                    tenant_id=tenant_id,
                    company_id=company_id,
                    on_date=accounting_start_date(company_id),
                )
                self.stdout.write(f"{name}: {len(made)} legări noi")
