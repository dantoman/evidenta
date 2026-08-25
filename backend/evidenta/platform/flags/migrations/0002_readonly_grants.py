"""Withdraw write privileges from the global flag tables.

They were never meant to be writable by a tenant, and the policy already refused
-- but only because no INSERT policy existed. The default privileges in
0001_roles.sql had granted the writes anyway, so the intent held at one layer
instead of two.
"""

from django.db import migrations

from evidenta.platform.rls.sql import run_sql_file


class Migration(migrations.Migration):
    dependencies = [("flags", "0001_initial")]

    operations = [
        run_sql_file(
            "0026_readonly_grants",
            up_sha256="aef6fc78ca49573a611f83607db5672f28224b58b685bf6d40858d7d61ef1330",
            down_sha256="51e3b81bd32a19a3618d06660adf01dca39c57aaf2b161e99b4f906cd0e120ab",
        ),
    ]
