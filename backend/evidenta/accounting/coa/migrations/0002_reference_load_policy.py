"""Let the schema owner write the chart-of-accounts reference tables.

`FORCE ROW LEVEL SECURITY` applies to the table owner too, and the two global
tables carried no write policy at all -- so the loader, running as
`evidenta_owner` exactly as intended, was refused by its own database. No new
role is created: `OD-56` asks whether reference loading deserves one, and this
does not answer it. It removes a contradiction, nothing more.
"""

from django.db import migrations

from evidenta.platform.rls.sql import run_sql_file


class Migration(migrations.Migration):
    dependencies = [("coa", "0001_initial")]

    operations = [
        run_sql_file(
            "0044_coa_reference_load",
            up_sha256="b01558f69fab10842fd520cf92962bb618b535a3a416f3ceb3e78c4aae8db681",
            down_sha256="569e41e5d5ce5df1f4b3dfe284a049746e1c7f64d5bd9c8f2de68bb8c224f3d8",
        ),
    ]
