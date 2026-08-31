"""The two facts a purchase cannot post without -- ADR-073 §2 and §4.

`cost_destination` selects which expense role the handler asks for;
`partner_resident` selects which payable. Both are **carried, never derived**:
`Partner` has no residence column, and no document says by itself whether a
service was administrative or went into production. A default on either would
answer a question nobody asked, in the direction that looks harmless -- costs on
administrative services, debts on the domestic account -- and the result balances,
passes `R11`, and is wrong in the profit and loss account and the balance sheet.

**Measured 2026-08-31 before writing this: `purchase_document` holds zero rows**
(development database; the table has had no API and no screen since it was
created, so no row can exist elsewhere either). The one-off defaults below exist
only to satisfy `AddField` on a NOT NULL column and label nothing --
``preserve_default=False`` takes them straight back out of the model state. The
CHECK added in the same migration is what keeps the vocabulary closed afterwards.

Written by hand rather than generated: `makemigrations` asks for those defaults at
an interactive prompt, and a prompt answered in a terminal leaves no record of
what was answered or why.

No paired SQL. Nothing here needs a collation (both are internal vocabularies, not
business codes), no policy changes, no grant: `purchase_document` has had its
policy since `0001`.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("purchases", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchasedocument",
            name="cost_destination",
            field=models.TextField(
                choices=[
                    ("administrative", "Administrative"),
                    ("commercial", "Commercial"),
                    ("production_direct", "Production Direct"),
                    ("production_indirect", "Production Indirect"),
                ],
                default="administrative",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="purchasedocument",
            name="partner_resident",
            field=models.BooleanField(default=True),
            preserve_default=False,
        ),
        migrations.AddConstraint(
            model_name="purchasedocument",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "cost_destination__in",
                        [
                            "administrative",
                            "commercial",
                            "production_direct",
                            "production_indirect",
                        ],
                    )
                ),
                name="purchase_document_cost_destination_valid",
            ),
        ),
    ]
