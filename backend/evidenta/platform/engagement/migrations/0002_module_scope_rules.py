"""ADR-018 and ADR-019 applied to the module scope.

Hand-written rather than generated: ``makemigrations`` stops to ask for a default
for the new non-nullable column, and the honest answer is "there are no rows" --
this table has never held data outside a throwaway test database.

Two rules arrive together because neither works alone. ADR-019 gives modules
names; ADR-018 says at most one live engagement per tenant may claim a name. A
non-overlap rule over a free-text column would be a rule over nothing.
"""

import uuid

import django.db.models.deletion
from django.db import migrations, models

from evidenta.platform.rls.sql import run_sql_file


class Migration(migrations.Migration):
    dependencies = [
        ("engagement", "0001_initial"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="engagementmodulescope",
            name="client_tenant",
            field=models.ForeignKey(
                db_column="client_tenant_id",
                on_delete=django.db.models.deletion.PROTECT,
                to="tenancy.tenant",
                default=uuid.UUID(int=0),
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="engagementmodulescope",
            name="is_live",
            field=models.BooleanField(default=True),
        ),
        migrations.AddConstraint(
            model_name="engagementmodulescope",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    module_key__in=[
                        "masterdata",
                        "accounting",
                        "tax",
                        "payroll",
                        "sales",
                        "purchases",
                        "receivables",
                        "payables",
                        "banking",
                        "cash",
                        "assets",
                        "statutory",
                        "efactura",
                        "inventory",
                    ]
                ),
                name="engagement_module_scope_key_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="engagementmodulescope",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_live=True),
                fields=("client_tenant", "module_key"),
                name="engagement_module_scope_no_overlap",
            ),
        ),
        run_sql_file(
            "0015_module_scope_sync",
            up_sha256="3ddedc34040f8b1a00efcd1e09a032f31864b67f7b0e6871770d61e501565fb0",
            down_sha256="e61a658d5691da5e29f58b728fe53e2a80d7d761ae12b1e511fee748796c399c",
            down_name="0015_module_scope_sync_reverse",
        ),
    ]
