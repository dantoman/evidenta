"""The settlement keeps the request's idempotency key -- R19 on the allocation door.

Additive (`C5`): one nullable text column and a partial unique constraint per
company. Before it, every arrival of the same request allocated again and, for a
settlement across currencies, posted the realised difference again (accounting
reviewer, 2026-09-03).
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("settlements", "0002_settlement_currency"),
    ]

    operations = [
        migrations.AddField(
            model_name="settlement",
            name="idempotency_key",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="settlement",
            constraint=models.UniqueConstraint(
                condition=models.Q(("idempotency_key__isnull", False)),
                fields=("company", "idempotency_key"),
                name="settlement_idempotency_key_unique",
            ),
        ),
    ]
