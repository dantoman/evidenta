"""`currency` joins the source vocabulary -- ADR-097, `A10`.

The fourth addition, on the pattern of `periods`, `production` and `treasury`: a
value names **the source of the fact**. The revaluation of monetary items in
foreign currency is the currency module's own act -- nobody typed it (`manual`),
and it is not the closing of a period (`periods`) even when the closing asks for
it: its source document is the revaluation row.

Additive: the CHECK is dropped and recreated with one more value, and no existing
row changes meaning.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounting_events", "0005_tax_status_snapshot"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="accountingevent",
            name="accounting_event_source_module_valid",
        ),
        migrations.AlterField(
            model_name="accountingevent",
            name="source_module",
            field=models.TextField(
                choices=[
                    ("sales", "Sales"),
                    ("purchases", "Purchases"),
                    ("payroll", "Payroll"),
                    ("banking", "Banking"),
                    ("assets", "Assets"),
                    ("migration", "Migration"),
                    ("manual", "Manual"),
                    ("periods", "Periods"),
                    ("treasury", "Treasury"),
                    ("production", "Production"),
                    ("currency", "Currency"),
                ]
            ),
        ),
        migrations.AddConstraint(
            model_name="accountingevent",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "source_module__in",
                        [
                            "sales",
                            "purchases",
                            "payroll",
                            "banking",
                            "assets",
                            "migration",
                            "manual",
                            "periods",
                            "treasury",
                            "production",
                            "currency",
                        ],
                    )
                ),
                name="accounting_event_source_module_valid",
            ),
        ),
    ]
