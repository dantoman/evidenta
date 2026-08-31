"""Two keys into the catalogue: `company.edit` and `company.close` -- ADR-083.

The same insert-only sync as `0003_roles`, for the same reason: the catalogue is
versioned in ``identity/permissions.py``, and a key that reached the table any
other way would be a right with no code behind it.

**What this migration deliberately does not do: grant them to anybody.**
``create_system_roles`` composes ``company_admin`` from every company-scoped key,
so tenants created after this get both. Tenants created before it keep the role
they have, and the repair command (``repair_system_roles``) is what brings them
up -- idempotent, and already the tool for exactly this: the same gap was found
once before, on a tenant whose ``owner`` role held zero permissions.

Writing ``role_permission`` rows here instead would mean a data write across every
tenant from a migration, under a role that cannot see their rows -- the failure
`OD-94` exists to make loud.
"""

from django.db import migrations

from evidenta.platform.identity.permissions import PERMISSIONS

#: The keys this migration is about. Named rather than derived from PERMISSIONS,
#: so that a later addition to the catalogue is not silently attributed to this
#: migration when somebody reads the history.
ADDED = ("company.edit", "company.close")


def add_keys(apps, schema_editor):
    Permission = apps.get_model("identity", "Permission")
    on_migration = Permission.objects.using(schema_editor.connection.alias)
    for definition in PERMISSIONS:
        if definition.key in ADDED:
            on_migration.update_or_create(key=definition.key, defaults={"scope": definition.scope})


def remove_keys(apps, schema_editor):
    """Remove them, and only them.

    Safe in the reverse direction only because nothing holds them yet: a role
    that had been granted one would lose it silently, which is why `0003_roles`
    says removing a key is its own migration rather than a data fix.
    """
    Permission = apps.get_model("identity", "Permission")
    Permission.objects.using(schema_editor.connection.alias).filter(key__in=ADDED).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0007_session_token"),
    ]

    operations = [
        migrations.RunPython(add_keys, remove_keys),
    ]
