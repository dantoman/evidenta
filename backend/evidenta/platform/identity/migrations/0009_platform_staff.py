"""`platform_staff`: who is an employee of the platform -- ADR-076 §4.1.

Global, at the level of `user`, with no `tenant_id` and no way to have one: an
employee of the platform belongs to no tenant. Declared in
infra/rls/exceptions.toml with the `self_row` shape and `evidenta_refdata` as its
writer; the paired SQL (`0075`) applies the policy, retracts the application
role's default write privileges and grants the writer INSERT and UPDATE -- no
DELETE, because a revocation is a date, not a deletion.

A row here grants nothing. It appears in no access predicate and opens no
policy; it is read by the console's doors and by the login on the `admin.` host.
"""

from django.db import migrations, models
import django.db.models.deletion

from evidenta.platform.rls.sql import run_sql_file


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0008_company_keys"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlatformStaff",
            fields=[
                (
                    "user",
                    models.OneToOneField(
                        db_column="user_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        primary_key=True,
                        serialize=False,
                        to="identity.user",
                    ),
                ),
                (
                    "staff_role",
                    models.TextField(
                        choices=[
                            ("support", "Support"),
                            ("operator", "Operator"),
                            ("admin", "Admin"),
                        ]
                    ),
                ),
                ("granted_at", models.DateTimeField()),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "granted_by",
                    models.ForeignKey(
                        db_column="granted_by_user_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="platform_staff_granted",
                        to="identity.user",
                    ),
                ),
            ],
            options={
                "db_table": "platform_staff",
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("staff_role__in", ["support", "operator", "admin"])),
                        name="platform_staff_role_valid",
                    )
                ],
            },
        ),
        run_sql_file(
            "0075_platform_staff",
            up_sha256="405a6f3cac4e4672cc59d74896091c4ffbdac0350c21d181a8ec6bb96e799bf3",
            down_sha256="f9ade5f8c462158fbb640262e80c370e87db0405ff5f215a02b1f38fb561d26d",
        ),
    ]
