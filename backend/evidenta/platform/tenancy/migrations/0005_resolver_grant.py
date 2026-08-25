"""The grant the resolver needed.

BYPASSRLS is not a table privilege. The resolver bypasses policies and was still
refused at the table -- which is the correct behaviour of two separate mechanisms
that are easy to conflate.
"""

from django.db import migrations

from evidenta.platform.rls.sql import run_sql_file


class Migration(migrations.Migration):
    dependencies = [("tenancy", "0004_subdomain_resolver")]

    operations = [
        run_sql_file(
            "0017_resolver_grant",
            up_sha256="f2df05cf6cc0846e1adeb0ea2463656f1854e8a7b5a5c2dc85ff67ed6eae0b95",
            down_sha256="9939f5a7c8efbe57ffa4d2192497a3ab84c70fc71556a12ec755bad2a7800dcd",
        ),
    ]
