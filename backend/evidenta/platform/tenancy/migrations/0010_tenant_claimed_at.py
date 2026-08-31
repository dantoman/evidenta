"""Whether anybody has taken this account over -- ADR-081 section 3.1.

A dated fact, not a status. Null is the normal, permanent, paid state: a firm may
keep a client's books for years without the client ever signing in, and the
account is ``active`` throughout. The two axes are orthogonal, and ADR-079 --
replaced hours after it was accepted -- confused them by proposing a
``tenant.status = 'unclaimed'`` that would have frozen accounts which work.

Not derived from "has no live membership", however elegant: ``membership`` is
policed as self_row, so nobody can count anybody else's members (`OD-37`).

No paired SQL. There is nothing here Django cannot express: no collation (this is
a timestamp, not a code), no policy change (``tenant`` keeps the
``tenant_predicate`` shape it has), no grant.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0009_tenant_identity"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="claimed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
