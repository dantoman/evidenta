"""Revoke the application role's write privileges on the confidence history.

Found by `manage.py check_schema_drift` on its first run against a live database.
Not a breach -- measured: the application's `INSERT` is refused by RLS, and
`UPDATE`/`DELETE` have no policy and an append-only trigger besides. It is a
declaration that did not match the database, and a defence that rested on the
absence of a policy rather than on the absence of a privilege.
"""

from django.db import migrations

from evidenta.platform.rls.sql import run_sql_file


class Migration(migrations.Migration):
    dependencies = [("fiscal_parameters", "0004_confidence_history")]

    operations = [
        run_sql_file(
            "0047_confidence_event_privileges",
            up_sha256="668224ed7a7609d05cee278dff8acdf3396750aa62c4b0976de1a32fa484b9e6",
            down_sha256="18f222d3679d78fa906faf76876762feccd62bc46f7a03a82319fe8a5041189b",
        ),
    ]
