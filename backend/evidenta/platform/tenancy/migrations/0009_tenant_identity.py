"""The account holder's own fiscal identity: IDNO and legal form -- ADR-075.

Nullable, additive (C5): a tenant created before this column keeps working and
simply has nothing to match on. IDNO is a code, so the paired SQL applies
`COLLATE "C"` (C34) -- Django has no field-level collation, which is why the pair
exists at all.

What it unlocks is one question the product could not answer: **which of these
companies is the account holder?** The workspace endpoint derives it by matching
this IDNO against `company.idno` in the same tenant. Matching by name was never an
option -- "Alpha SRL" and `SRL "Alpha"` are the same firm written differently.
"""

from django.db import migrations, models

from evidenta.platform.rls.sql import run_sql_file


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0008_company_classifier_codes"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="idno",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tenant",
            name="legal_form",
            field=models.TextField(blank=True, null=True),
        ),
        run_sql_file(
            "0070_tenant_identity",
            up_sha256="c7c4e2f94495767201a21fa5e72237d2a9be74c7457a7e3225a5664223b92fe2",
            down_sha256="af714caf01ee0a5ac76aeae32366c9a0e3336fe2800675e9cb8e397d765baf8a",
        ),
    ]
