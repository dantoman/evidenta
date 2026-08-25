"""Tenant gains its administrative contact, now that User exists.

Split from 0001 rather than folded into it: migrations are additive (C5), and the
column could not exist before the table it references. No SQL accompanies this --
adding a nullable column changes no policy, and ADR-012 asks for a paired SQL file
only where a policy is involved.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0001_initial"),
        ("identity", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="primary_contact",
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                db_column="primary_contact_user_id",
                to="identity.user",
                related_name="primary_contact_for",
            ),
        ),
    ]
