"""`document.contract_denomination` -- ADR-097, closing `OD-127`.

REVERSIBILITY = "reversible-tested"

Additive (C5): a nullable column and a CHECK. Null on every existing row, which
is right for the ones in the functional currency and honest for any in another
currency opened before the column existed: they carry no denomination, and the
revaluation skips them by name rather than assuming one.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0003_rate_term"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="contract_denomination",
            field=models.TextField(
                blank=True,
                choices=[
                    ("foreign_currency", "Foreign Currency"),
                    ("conventional_units", "Conventional Units"),
                ],
                null=True,
            ),
        ),
        migrations.AddConstraint(
            model_name="document",
            constraint=models.CheckConstraint(
                condition=models.Q(("contract_denomination__isnull", True))
                | models.Q(
                    ("contract_denomination__in", ["foreign_currency", "conventional_units"])
                ),
                name="document_contract_denomination_valid",
            ),
        ),
    ]
