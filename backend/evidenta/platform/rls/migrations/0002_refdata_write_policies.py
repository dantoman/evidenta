"""Reference-data writes move under `evidenta_refdata` -- ADR-049, closes OD-67.

Hosted here for the same reason as `0001`: the change is about who may write
which global table, which is a property of the RLS contract and not of any one
module. Depends on the last migration of every app that owns a reference table,
so the policies are created after the tables and after `0044` (whose owner
policy this one retracts).

The role itself is created by `infra/bootstrap/0004_refdata_role.sql`, outside
the migration cycle (C31); `make migrate` applies the bootstrap first. On a
database where it was not, this migration fails on the first `CREATE POLICY ...
TO evidenta_refdata` with "role does not exist" -- loudly, which is the right
outcome for a half-applied change.
"""

from django.db import migrations

from evidenta.platform.rls.sql import run_sql_file


class Migration(migrations.Migration):
    dependencies = [
        ("rls", "0001_function_privileges"),
        ("fiscal_parameters", "0006_source_act"),
        ("fiscal_registry", "0001_initial"),
        ("currency", "0001_initial"),
        ("counterparties", "0001_initial"),
        ("coa", "0004_template_act"),
        ("legislation", "0001_initial"),
        ("audit", "0003_privileged_access_log"),
    ]

    operations = [
        run_sql_file(
            "0060_refdata_write_policies",
            up_sha256="1b8740ade2048269165231c51a4a0803f8fc723e6a8f49ecb81ca9f3f3a95fe7",
            down_sha256="e30781c3bfe2988d95ef99f3ce44dca6e2c20dd1fdf5ab34c9e2c246afe63204",
        ),
    ]
