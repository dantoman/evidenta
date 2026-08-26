"""The other half of the cascade: access derived from an engagement is extended.

``0014`` gave the revocation side -- when the relationship ends, the access it
produced ends with it. Nothing gave the opposite: a company created after the
engagement was accepted stayed invisible to the firm serving that client, even
with ``covers_all_companies`` set, because the column was read by nothing.
"""

from django.db import migrations

from evidenta.platform.rls.sql import run_sql_file


class Migration(migrations.Migration):
    dependencies = [
        ("engagement", "0002_module_scope_rules"),
        # company_access and the revocation function this mirrors.
        ("identity", "0002_companyaccess"),
    ]

    operations = [
        run_sql_file(
            "0032_engagement_provisioning",
            up_sha256="54e653ce153e169a687c289c63b7dd95b939402cb1339457ba71c2eb34cf4bcd",
            down_sha256="a3b7ed6bab1ae20a14e6a46bc891fadf2f36272d486b8c212de41c896ade78d4",
            down_name="0032_engagement_provisioning_reverse",
        ),
    ]
