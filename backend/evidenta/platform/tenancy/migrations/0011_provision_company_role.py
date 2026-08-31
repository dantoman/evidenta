"""`P-9` writes a company-level role into `company_access` -- ADR-084.

`0007` installed the function that wrote the creator's **membership** role, which
is tenant-level. `role_permission` binds a permission's scope to the role's level,
so no company-scoped key could be held on the rows the product actually creates --
measured at 2026-08-31, all four live rows on the development database carried
`owner`.

The SQL file is a new one, not an edit: `C31` makes an applied file append-only,
and the history has to keep showing what ran. The reverse restores the previous
body verbatim, defect included, because a rollback returns the system to the state
it was in rather than to a better one it never had.

**Existing rows are not touched here.** They are somebody's access, and rewriting
access from a migration -- under a role that cannot see the rows it is rewriting --
is the failure `OD-94` exists to make loud. `repair_company_access` does it as an
operator command, deliberately and with a report, the way `repair_system_roles`
already repairs the roles themselves.
"""

from django.db import migrations

from evidenta.platform.rls.sql import run_sql_file


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0010_tenant_claimed_at"),
        ("identity", "0008_company_keys"),
    ]

    operations = [
        run_sql_file(
            "0072_provision_company_role",
            up_sha256="33a366f65a41f7a9e6d7113fdcad1d8e70b5272dba12e651cd377d97e67b37b1",
            down_sha256="87c401ed1d91ac1c89f63d90a24a193f3940300ab7b49e46cb9692d05ef6a23e",
        ),
    ]
