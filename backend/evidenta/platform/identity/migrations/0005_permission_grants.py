"""Give the catalogue a grant-level backstop, not only a policy.

Found by ``schema-reviewer``: the GRANT in ``0019`` could not narrow anything,
because the bootstrap's default privileges had already given the application role
full CRUD on every table the owner creates.
"""

from django.db import migrations

from evidenta.platform.rls.sql import run_sql_file


class Migration(migrations.Migration):
    dependencies = [("identity", "0004_roles_hardening")]

    operations = [
        run_sql_file(
            "0021_permission_grants",
            up_sha256="4ffee04db758ab71479960177e3427317536be46bdf1402991477923aa1e47eb",
            down_sha256="5ec6f15c248c36d07449aa12e8940d1a4df9c064ba404395c597f1d3a766cb30",
        ),
    ]
