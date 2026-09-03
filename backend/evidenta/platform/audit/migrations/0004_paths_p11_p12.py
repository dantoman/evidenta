"""Two more privileged paths in the log's CHECK -- ADR-081 (`P-11`) and ADR-092 (`P-12`).

The constraint enumerates the codes a log row may carry, so a path added to Spec
A §6.2 is a migration here, deliberately: a code the database refuses is a path
nobody can run unlogged by mistake. `P-11` (claiming a tenant) has no caller
yet and is listed because the specification lists it; `P-12` is the console's
staff administration, called from `identity/console_views.py`.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0003_privileged_access_log"),
    ]

    operations = [
        migrations.AlterField(
            model_name="privilegedaccesslog",
            name="path_code",
            field=models.TextField(
                choices=[
                    ("P-1", "P1 Billing"),
                    ("P-2", "P2 Sfs Polling"),
                    ("P-3", "P3 Bnm Rates"),
                    ("P-4", "P4 Fiscal Rules"),
                    ("P-5", "P5 Counterparty Registry"),
                    ("P-6", "P6 Read Models"),
                    ("P-7", "P7 Support Access"),
                    ("P-8", "P8 Offboarding Export"),
                    ("P-9", "P9 Provisioning"),
                    ("P-10", "P10 Chart Of Accounts"),
                    ("P-11", "P11 Claim"),
                    ("P-12", "P12 Platform Staff"),
                ]
            ),
        ),
        migrations.RemoveConstraint(
            model_name="privilegedaccesslog",
            name="privileged_access_log_path_valid",
        ),
        migrations.AddConstraint(
            model_name="privilegedaccesslog",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "path_code__in",
                        ["P-1", "P-2", "P-3", "P-4", "P-5", "P-6", "P-7", "P-8", "P-9", "P-10", "P-11", "P-12"],
                    )
                ),
                name="privileged_access_log_path_valid",
            ),
        ),
    ]
