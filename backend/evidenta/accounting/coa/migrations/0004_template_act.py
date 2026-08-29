"""The act behind a chart version, as a row in the shared registry -- ADR-049 (OD-65).

Additive (C5): nullable, filled by `load_coa_template`; the free-text citation stays.
"""


import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('coa', '0003_dimension_slots'),
        ('legislation', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='coatemplate',
            name='act',
            field=models.ForeignKey(blank=True, db_column='act_id', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='chart_templates', to='legislation.normativeact'),
        ),
    ]
