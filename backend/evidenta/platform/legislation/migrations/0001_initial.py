"""Normative acts and their publications -- OD-65, ADR-049.

Three global tables in one migration with their policies (C30): readable by the
application role, written only under `evidenta_refdata`. The role exists from
`infra/bootstrap/0004_refdata_role.sql`.
"""


import django.db.models.deletion
import uuid
from django.db import migrations, models

from evidenta.platform.rls.sql import run_sql_file


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='NormativeAct',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('act_type', models.TextField()),
                ('act_number', models.TextField()),
                ('act_date', models.DateField()),
                ('title', models.TextField()),
                ('effective_from', models.DateField(blank=True, null=True)),
                ('url', models.TextField(blank=True, null=True)),
                ('notes', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'normative_act',
                'constraints': [models.UniqueConstraint(fields=('act_type', 'act_number', 'act_date'), name='normative_act_identity_unique')],
            },
        ),
        migrations.CreateModel(
            name='OfficialPublication',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('gazette_year', models.IntegerField()),
                ('gazette_number', models.TextField()),
                ('article', models.TextField()),
                ('published_at', models.DateField(blank=True, null=True)),
                ('url', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'official_publication',
                'constraints': [models.UniqueConstraint(fields=('gazette_year', 'gazette_number', 'article'), name='official_publication_position_unique')],
            },
        ),
        migrations.CreateModel(
            name='NormativeActPublication',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('role', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('act', models.ForeignKey(db_column='act_id', on_delete=django.db.models.deletion.PROTECT, related_name='publications', to='legislation.normativeact')),
                ('publication', models.ForeignKey(db_column='publication_id', on_delete=django.db.models.deletion.PROTECT, related_name='acts', to='legislation.officialpublication')),
            ],
            options={
                'db_table': 'normative_act_publication',
                'constraints': [models.UniqueConstraint(fields=('act', 'publication'), name='normative_act_publication_unique')],
            },
        ),
        run_sql_file(
            "0059_legislation",
            up_sha256="063862302775dec5ba55a226eb6da750f6c19eb99692538449cdb29f20a45123",
            down_sha256="b4cbcd57508e1eee1828cd58a288ec024e44958ec33bf23b0f412016b32671a8",
        ),
    ]
