"""The precision of a quantity is the unit's: required, and frozen once used -- ADR-055.

Two things, one decision. `decimal_places` loses its Django default (the column
was NOT NULL in the database from F0.7; only the model answered "0" for anyone
who did not ask), and a trigger refuses to change it on a unit that already
carries quantities on a document or journal line. The trigger reads the ledger
tables by name, which is why this file declares its reversibility: the reverse
drops the trigger and the function under the role that owns it, and the round
trip is in the schema guard's list.
"""

REVERSIBILITY = "reversible-tested"

from django.db import migrations, models

from evidenta.platform.rls.sql import run_sql_file


class Migration(migrations.Migration):
    dependencies = [
        ("uom", "0001_initial"),
        # The tables the freeze looks at have to exist before the function does.
        ("documents", "0002_document_layer"),
        ("ledger", "0003_journal_formula"),
        ("opening", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="unitofmeasure",
            name="decimal_places",
            field=models.SmallIntegerField(),
        ),
        run_sql_file(
            "0061_unit_precision_frozen",
            up_sha256="1f3a8a77103bb0a8293c54f0ab5543eb714ea7ccbf9d17b7ce2cca433d1eaddc",
            down_sha256="87860daae13fee824b905d74aadfbbffb05f18de60e93beccd30b4166de6582e",
        ),
    ]
