"""The history that makes a confirmed value still able to say it was inferred.

Confirming a parameter does not change its value, so it is not a new version with
a new window -- it is an edit of one column, and the edit erases the state a past
calculation relied on. This table keeps every state and from when, append-only,
enforced by a trigger rather than by convention.

Classified with `fiscal_parameter` and `fiscal_parameter_source` in
`infra/rls/exceptions.toml`: global, readable by all, written through P-4. A
per-tenant confidence history would let two tenants give different answers to the
same inspection about the same act.
"""


import django.db.models.deletion
import uuid
from django.db import migrations, models

from evidenta.platform.rls.sql import run_sql_file


class Migration(migrations.Migration):

    dependencies = [
        ('fiscal_parameters', '0003_source_confidence'),
    ]

    operations = [
        migrations.CreateModel(
            name='FiscalParameterConfidenceEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('confidence', models.TextField(choices=[('confirmed', 'Confirmed'), ('provisional', 'Provisional')])),
                ('provisional_reason', models.TextField(blank=True, null=True)),
                ('note', models.TextField()),
                ('effective_at', models.DateTimeField()),
                ('recorded_at', models.DateTimeField(auto_now_add=True)),
                ('recorded_by_user_id', models.UUIDField(blank=True, null=True)),
                ('parameter', models.ForeignKey(db_column='parameter_id', on_delete=django.db.models.deletion.PROTECT, related_name='confidence_events', to='fiscal_parameters.fiscalparameter')),
            ],
            options={
                'db_table': 'fiscal_parameter_confidence_event',
                'indexes': [models.Index(fields=['parameter', '-effective_at'], name='fiscal_conf_event_lookup_idx')],
                'constraints': [models.CheckConstraint(condition=models.Q(('confidence__in', ['confirmed', 'provisional'])), name='fiscal_conf_event_confidence_valid'), models.CheckConstraint(condition=models.Q(('note', ''), _negated=True), name='fiscal_conf_event_has_note'), models.CheckConstraint(condition=models.Q(models.Q(('confidence', 'provisional'), _negated=True), models.Q(models.Q(('provisional_reason__isnull', True), _negated=True), models.Q(('provisional_reason', ''), _negated=True)), _connector='OR'), name='fiscal_conf_event_provisional_has_reason')],
            },
        ),
        run_sql_file(
            "0042_fiscal_confidence",
            up_sha256="b09f5363025f56afd59ff25c64fedb7a82a8e648d0ab7d9c4e21bd3c378d1fe5",
            down_sha256="81669cf06827603b8a97d4ab57588a042f938ce8cc2cae054df725366f410f50",
        ),
    ]
