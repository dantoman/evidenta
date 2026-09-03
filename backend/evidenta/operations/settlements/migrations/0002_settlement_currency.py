"""A settlement across currencies -- ADR-097, closing `OD-127`.

REVERSIBILITY = "reversible-tested"

Additive (C5): three nullable columns and one CHECK that keeps them together.
Existing rows are settlements inside the functional currency and stay null,
which is what null means.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("settlements", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="settlement",
            name="currency",
            field=models.CharField(blank=True, max_length=3, null=True),
        ),
        migrations.AddField(
            model_name="settlement",
            name="amount_currency",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=20, null=True),
        ),
        migrations.AddField(
            model_name="settlement",
            name="settlement_rate",
            field=models.DecimalField(blank=True, decimal_places=8, max_digits=18, null=True),
        ),
        migrations.AddConstraint(
            model_name="settlement",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("currency__isnull", True))
                    & models.Q(("amount_currency__isnull", True))
                    & models.Q(("settlement_rate__isnull", True))
                )
                | (
                    models.Q(("currency__isnull", False))
                    & models.Q(("amount_currency__gt", 0))
                    & models.Q(("settlement_rate__gt", 0))
                ),
                name="settlement_currency_complete",
            ),
        ),
    ]
