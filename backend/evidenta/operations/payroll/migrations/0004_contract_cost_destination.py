"""The contract says where its cost goes -- ADR-065 section 7.1.

Additive (`C5`): one nullable column and the CHECK that keeps it in the four-word
vocabulary. Nullable because the rows that exist were written before the column
did, and a backfill to any one value would be the silent default the ADR refuses;
a run whose contract has none is refused at posting, by name, until somebody
states it.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payroll", "0003_payroll_run"),
    ]

    operations = [
        migrations.AddField(
            model_name="employmentcontract",
            name="cost_destination",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="employmentcontract",
            constraint=models.CheckConstraint(
                condition=models.Q(("cost_destination__isnull", True))
                | models.Q(
                    (
                        "cost_destination__in",
                        ["administrative", "commercial", "production_direct", "production_indirect"],
                    )
                ),
                name="employment_contract_cost_destination_valid",
            ),
        ),
    ]
