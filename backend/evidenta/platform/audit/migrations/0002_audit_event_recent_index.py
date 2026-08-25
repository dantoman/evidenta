"""The index the volume model found, on the table it warned about.

`audit_event` was already named as the first real candidate for partitioning --
highest write volume, value decaying with age. What the F0.11 measurements found
first was cheaper and more urgent: the enumeration of Spec A 9.3, "what happened
in this tenant, most recent first", read a million rows to return fifty.

The cause is index shape, not absence. `audit_event_scope_idx` leads with
(tenant_id, company_id, occurred_at), so within a tenant the rows are ordered by
company before time; ordering by occurred_at alone cannot be served from it.
Measured under the application role with RLS active: 6.7 seconds for LIMIT 50.

A fourth index on the highest-write table is a real cost, and it is measured in
docs/_bootstrap/11-volume-model.md rather than assumed.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("audit", "0001_initial")]

    operations = [
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(
                fields=["tenant_id", "-occurred_at"],
                name="audit_event_recent_idx",
            ),
        ),
    ]
