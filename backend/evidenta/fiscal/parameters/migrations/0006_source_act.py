"""The act behind a fiscal source, as a row in the shared registry -- ADR-049 (OD-65).

Additive (C5): nullable, filled by the loader; the two gazette columns stay.
"""


import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fiscal_parameters', '0005_confidence_event_privileges'),
        ('legislation', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='fiscalparametersource',
            name='act',
            field=models.ForeignKey(blank=True, db_column='act_id', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='fiscal_sources', to='legislation.normativeact'),
        ),
    ]
