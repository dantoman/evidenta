"""Privileges on the `rls` schema's functions -- ADR-043.

This app owns no tables, and until now owned no migrations either. The migration
lives here rather than being attached to whichever app happened to be convenient
because the change is about `rls` itself: the schema, its owner, and who may call
into it. Hanging it off `flags` or `identity` would put the answer to "who can
execute the access predicates" in a module that has no reason to know.

Depends on every migration that creates a function in `rls`, so the sweep runs
after the last of them rather than before -- a `REVOKE ALL ON ALL FUNCTIONS`
applied too early would leave the ones created afterwards untouched, which is the
same silent half-fix the file exists to correct.
"""

from django.db import migrations

from evidenta.platform.rls.sql import run_sql_file


class Migration(migrations.Migration):
    #: Every app whose migrations create a function in `rls`, found by grepping
    #: `infra/migrations/*.up.sql` for `FUNCTION rls.` rather than from memory:
    #: 0014/0032 engagement, 0015/0028 identity, 0016 tenancy, 0023 flags,
    #: 0030 notifications, 0036 ledger, 0039 opening.
    dependencies = [
        ("engagement", "0003_company_access_provisioning"),
        ("identity", "0007_session_token"),
        ("notifications", "0001_initial"),
        ("flags", "0002_readonly_grants"),
        ("tenancy", "0005_resolver_grant"),
        ("ledger", "0001_initial"),
        ("opening", "0001_initial"),
    ]

    operations = [
        run_sql_file(
            "0041_rls_function_privileges",
            up_sha256="6c2b16a0ac64488ba61d1704e563a5be6f33d0095199bb2c1786e4b93d8236c0",
            down_sha256="962a479b3dcd78afb89544512d1dd1926b41d0e9b8ea57fde5ce862d7168f843",
        ),
    ]
