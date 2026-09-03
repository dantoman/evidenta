"""The revaluation of monetary items in foreign currency -- A10, ADR-097.

REVERSIBILITY = "reversible-tested"

Two tables, both the accounting module's own: the source document of
`accounting.revaluation_calculated` and the balances it restated. Additive (C5):
nothing existing changes.

`INSERT` and `SELECT` only, like `settlement`: a revaluation that must not stand
is reversed through its entry (R14), never edited or deleted.
"""

import uuid

import django.db.models.deletion
from django.db import migrations, models

from evidenta.platform.rls.sql import run_sql_file


class Migration(migrations.Migration):

    dependencies = [
        ("currency", "0001_initial"),
        ("documents", "0003_rate_term"),
        ("accounting_events", "0001_initial"),
        ("ledger", "0001_initial"),
        ("tenancy", "0011_provision_company_role"),
    ]

    operations = [
        migrations.CreateModel(
            name="Revaluation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("as_of", models.DateField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("accounting_event", models.ForeignKey(db_column="accounting_event_id", on_delete=django.db.models.deletion.PROTECT, related_name="+", to="accounting_events.accountingevent")),
                ("company", models.ForeignKey(db_column="company_id", on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.company")),
                ("journal_entry", models.ForeignKey(blank=True, db_column="journal_entry_id", null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="ledger.journalentry")),
                ("tenant", models.ForeignKey(db_column="tenant_id", on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.tenant")),
            ],
            options={
                "db_table": "revaluation",
                "indexes": [models.Index(fields=["tenant", "company", "as_of"], name="revaluation_idx")],
                "constraints": [models.UniqueConstraint(fields=("company", "as_of"), name="revaluation_company_date_unique")],
            },
        ),
        migrations.CreateModel(
            name="RevaluationItem",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("side", models.TextField()),
                ("partner_id", models.UUIDField()),
                ("currency", models.CharField(max_length=3)),
                ("amount_currency", models.DecimalField(decimal_places=4, max_digits=20)),
                ("rate_before", models.DecimalField(decimal_places=8, max_digits=18)),
                ("rate_after", models.DecimalField(decimal_places=8, max_digits=18)),
                ("difference", models.DecimalField(decimal_places=4, max_digits=20)),
                ("company", models.ForeignKey(db_column="company_id", on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.company")),
                ("document", models.ForeignKey(db_column="document_id", on_delete=django.db.models.deletion.PROTECT, related_name="+", to="documents.document")),
                ("revaluation", models.ForeignKey(db_column="revaluation_id", on_delete=django.db.models.deletion.PROTECT, related_name="items", to="currency.revaluation")),
                ("tenant", models.ForeignKey(db_column="tenant_id", on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.tenant")),
            ],
            options={
                "db_table": "revaluation_item",
                "indexes": [models.Index(fields=["tenant", "company", "document"], name="revaluation_item_document_idx")],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("side__in", ("receivable", "payable"))), name="revaluation_item_side_valid"),
                    models.CheckConstraint(condition=models.Q(("amount_currency__gt", 0)), name="revaluation_item_amount_positive"),
                    models.CheckConstraint(condition=models.Q(("rate_before__gt", 0), ("rate_after__gt", 0)), name="revaluation_item_rates_positive"),
                    models.UniqueConstraint(fields=("revaluation", "document"), name="revaluation_item_document_unique"),
                ],
            },
        ),
        run_sql_file(
            "0079_revaluation",
            up_sha256="b2b26600cde8cce74a260efe69229d83ef559fc1949fabf6b61be2c19fe486c0",
            down_sha256="52212f9d6fc42ad3f58733d59f5c5121debec85ef622b8b9f8a2559e9d66a728",
        ),
    ]
