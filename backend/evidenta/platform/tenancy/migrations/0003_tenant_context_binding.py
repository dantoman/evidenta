"""Bind the tenant policy to the request context.

The policy shipped in 0001 answered "who may see this row" but not "is this row
inside the requested tenant". ADR-003 notes that the shape for `tenant` was
extrapolated rather than decided; the extrapolation lost the context binding.

Tightening, not loosening -- so it is safe to ship while OD-44 confirms the
consequence for the tenant switcher.
"""

from django.db import migrations

from evidenta.platform.rls.sql import run_sql_file


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0002_tenant_primary_contact"),
        ("identity", "0001_initial"),
    ]

    operations = [
        run_sql_file(
            "0012_tenant_context_binding",
            up_sha256="abbbaff4e80fed6412254d557aaedb7344b13e05ff8380d893eff6955a80f38e",
            down_sha256="6fc16c7e8f37e354b6daf8e3fa93ffccd1186063623fdb1dad04faab122d421d",
        ),
    ]
