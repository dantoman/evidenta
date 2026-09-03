"""The support session and the client's key to approve it -- ADR-077 §5-§6.

Two things, together because neither means anything without the other: the column
that binds a session to a support grant (read back by `rls.resolve_session`, which
support/0001 redefines), and the catalogue key `tenant.approve_support_access`
through which a member of the client approves or revokes the grant.

Same insert-only sync as `0003_roles` and `0008_company_keys`; and, as there, no
`role_permission` rows are written here -- `create_system_roles` composes the
administration role from every tenant-scoped key for new spaces, and
`repair_system_roles` brings the existing ones up.
"""

from django.db import migrations, models

from evidenta.platform.identity.permissions import PERMISSIONS

ADDED = ("tenant.approve_support_access",)


def add_keys(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    on_migration = Permission.objects.using(schema_editor.connection.alias)
    for definition in PERMISSIONS:
        if definition.key in ADDED:
            on_migration.update_or_create(key=definition.key, defaults={"scope": definition.scope})


def remove_keys(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    Permission.objects.using(schema_editor.connection.alias).filter(key__in=ADDED).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0010_console_reads"),
    ]

    operations = [
        migrations.AddField(
            model_name="usersession",
            name="support_grant_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.RunPython(add_keys, remove_keys),
    ]
