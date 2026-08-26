"""F0.3.7c — session token and the functions that precede tenant context.

Hand-written rather than generated: ``makemigrations`` cannot run under the query
guard (it reads ``django_migrations`` on the application connection before any
context exists), and the DDL belongs in the SQL file anyway -- ``COLLATE "C"``
and a backfill are not expressible as Django operations.

``SeparateDatabaseAndState`` is what keeps the two honest. The database side is
the append-only SQL file, checksum-verified; the state side teaches Django the
column exists, so the next ``makemigrations`` sees no drift.
"""

from django.db import migrations, models

from evidenta.platform.rls.sql import run_sql_file


class Migration(migrations.Migration):
    dependencies = [
        ("identity", "0006_remove_user_mfa_secret_encrypted_mfabackupcode_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                run_sql_file(
                    "0028_auth_request_path",
                    up_sha256="9f68557bf57012b2b61272920b7f9d762c988c008da00b980975b512066e1171",
                    down_sha256="62e0604302f8fa7eaece1164df75c44525c4685433c62a81dffa649ad3000aea",
            down_name="0028_auth_request_path_reverse",
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="usersession",
                    name="token_hash",
                    field=models.TextField(default="", unique=True),
                    preserve_default=False,
                ),
            ],
        ),
    ]
