"""The privileged path that resolves a subdomain to a tenant.

No model changes: this migration exists only to carry the SQL. Resolving the
subdomain is what happens *before* a tenant context exists, so it cannot go
through a policy that requires one.
"""

from django.db import migrations

from evidenta.platform.rls.sql import run_sql_file


class Migration(migrations.Migration):
    dependencies = [("tenancy", "0003_tenant_context_binding")]

    operations = [
        run_sql_file(
            "0016_subdomain_resolver",
            up_sha256="db2f076742fa3160bbe834b68858a224a74205ae8a9d611a1b594f4060fdf477",
            down_sha256="98d8294e6267233b2897aebafa5b145acfd2db821dfea6f9863b403d7d9f8007",
        ),
    ]
