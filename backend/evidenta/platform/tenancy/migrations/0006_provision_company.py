"""`P-9` -- the privileged path that creates a company (ADR-040).

The application role cannot create the first company by any sequence of
statements: the policy on `company` requires `has_company_access(id)`, which
requires an access row, which requires the company. Not a service restriction --
an impossibility of the policy, which is why ADR-040 puts it on its own path.
"""

from django.db import migrations

from evidenta.platform.rls.sql import run_sql_file


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0005_resolver_grant"),
        ("engagement", "0003_company_access_provisioning"),
    ]

    operations = [
        run_sql_file(
            "0045_provision_company",
            up_sha256="3d5182baaeabca07b1458e8b14729ee84e21989c8929a0777d7445f7874ba75a",
            down_sha256="ee4794f27583fd8a539baefe7b83fb223af5a9af536a14af17d4785cf224e9a4",
        ),
    ]
