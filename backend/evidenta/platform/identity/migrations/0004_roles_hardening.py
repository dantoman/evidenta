"""Close the UPDATE path around the system-role protection.

Found by ``schema-reviewer``, not by the suite: the tests exercised deletion,
which was the covered path. See ``infra/migrations/0020_roles_hardening.up.sql``
for the two statements that defeated it.

A new file rather than an edit to ``0019``: that one is applied, so it is
append-only (C31).
"""

from django.db import migrations

from evidenta.platform.rls.sql import run_sql_file


class Migration(migrations.Migration):
    dependencies = [("identity", "0003_roles")]

    operations = [
        run_sql_file(
            "0020_roles_hardening",
            up_sha256="cb1381007792cf4e04f92b8c02d93f29e2a8270ca6cbbf5939b90f374e053a94",
            down_sha256="6d97ac0f4604fc781078886d01991b9463563e4660e5c9cbdd2f65775bdadcae",
        ),
    ]
