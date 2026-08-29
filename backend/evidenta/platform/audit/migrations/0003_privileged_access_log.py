"""The privileged-access log -- Spec A section 6.3, built by ADR-049.

Declared in `infra/rls/exceptions.toml` since F0 and created here, with its
policies in the same transaction (C30): written only under `evidenta_refdata`,
read by nobody through the application, append-only by trigger.
"""


from django.db import migrations, models

from evidenta.platform.rls.sql import run_sql_file


class Migration(migrations.Migration):

    dependencies = [
        ('audit', '0002_audit_event_recent_index'),
    ]

    operations = [
        migrations.CreateModel(
            name='PrivilegedAccessLog',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('occurred_at', models.DateTimeField()),
                ('path_code', models.TextField(choices=[('P-1', 'P1 Billing'), ('P-2', 'P2 Sfs Polling'), ('P-3', 'P3 Bnm Rates'), ('P-4', 'P4 Fiscal Rules'), ('P-5', 'P5 Counterparty Registry'), ('P-6', 'P6 Read Models'), ('P-7', 'P7 Support Access'), ('P-8', 'P8 Offboarding Export'), ('P-9', 'P9 Provisioning'), ('P-10', 'P10 Chart Of Accounts')])),
                ('actor_user_id', models.UUIDField(blank=True, null=True)),
                ('actor', models.TextField()),
                ('subject_tenant_id', models.UUIDField(blank=True, null=True)),
                ('tenant_count', models.IntegerField(blank=True, null=True)),
                ('request_id', models.TextField()),
                ('justification', models.TextField(blank=True, null=True)),
                ('payload', models.JSONField(blank=True, null=True)),
            ],
            options={
                'db_table': 'privileged_access_log',
                'indexes': [models.Index(fields=['path_code', '-occurred_at'], name='privileged_log_path_idx'), models.Index(fields=['request_id'], name='privileged_log_request_idx')],
                'constraints': [models.CheckConstraint(condition=models.Q(('path_code__in', ['P-1', 'P-2', 'P-3', 'P-4', 'P-5', 'P-6', 'P-7', 'P-8', 'P-9', 'P-10'])), name='privileged_access_log_path_valid'), models.CheckConstraint(condition=models.Q(models.Q(('path_code', 'P-7'), _negated=True), models.Q(models.Q(('justification__isnull', True), _negated=True), models.Q(('justification', ''), _negated=True)), _connector='OR'), name='privileged_access_log_p7_justified')],
            },
        ),
        run_sql_file(
            "0058_privileged_access_log",
            up_sha256="b274783dbcd4e327efdde5527c0aa7c713a149d0fd81220937fc09a3db35dcc6",
            down_sha256="103454dc3e8efd72e917fcdbe87e2bfb9ee5d00316189ef4b6e045cde0a61703",
        ),
    ]
