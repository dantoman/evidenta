"""Issue `rls.provision_company`'s privileges as the role that owns it.

`0006` issued them after `RESET ROLE`, so they came from `evidenta_owner`, which
does not own the function -- a REVOKE from anyone but the owner is a warning, and
the migration passed having revoked nothing. The schema guard measured the
result: the function was executable by PUBLIC. ADR-043, same shape as the eight
inverses it was written for.
"""

from django.db import migrations

from evidenta.platform.rls.sql import run_sql_file


class Migration(migrations.Migration):
    dependencies = [("tenancy", "0006_provision_company")]

    operations = [
        run_sql_file(
            "0046_provision_company_privileges",
            up_sha256="0d4c53e1a6cbbd4429e08179b183a52031ce55ddb4352496a29fb8914aac6467",
            down_sha256="56d227b4472a755a9ce9e9a4884e1b5d351d8bbd2f8debd0b0a53eb2192fbf78",
        ),
    ]
