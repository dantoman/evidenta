"""On whose word an engagement was accepted -- ADR-081 section 3.3.

Three columns and three checks, all additive (C5). ``acceptance_basis`` is NOT
NULL once ``accepted_at`` is; ``mandate_ref`` is the contract the firm points at;
``claim_contact_email`` is mandatory on a declared mandate and verified by
nobody, which section 3.5 names as the honest weak link rather than hiding it.

**What this migration does not do is the point of it.** The access predicate is
untouched: an engagement resting on a declared mandate is ``active`` like any
other and travels the existing second path of ``rls.has_tenant_access``. No
branch, no new state, no cost on the hot path -- and
``engagement_active_requires_acceptance`` keeps holding, now saying on each row
which of the two bases sits underneath it.

Order inside the migration: columns, then the paired SQL that gives two of them
their types, then the constraints -- rule (c) of `OD-94`, constraints after the
write rather than before it.

**Measured 2026-08-31, rather than assumed:** ``engagement`` holds zero rows in
the development database, so there is nothing to backfill and no backfill is
written. Should some database reach this migration holding an accepted
engagement, ``engagement_acceptance_states_its_basis`` refuses it loudly, and the
repair is a backfill writing ``'client'`` -- true of every row accepted before
today, because the other basis did not exist to be chosen.
"""

from django.db import migrations, models

from evidenta.platform.rls.sql import run_sql_file


class Migration(migrations.Migration):

    dependencies = [
        ("engagement", "0003_company_access_provisioning"),
        ("identity", "0007_session_token"),
        ("tenancy", "0010_tenant_claimed_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="engagement",
            name="acceptance_basis",
            field=models.TextField(
                blank=True,
                choices=[("client", "Client"), ("declared_mandate", "Declared Mandate")],
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="engagement",
            name="claim_contact_email",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="engagement",
            name="mandate_ref",
            field=models.TextField(blank=True, null=True),
        ),
        run_sql_file(
            "0071_declared_mandate",
            up_sha256="af2c078ac5512a1dba932db13553ad0f3a74c9c019ddf7a8952dfcf752070d02",
            down_sha256="27ccac9ce9a696b99b29223092cac395d70d183411931316c7671c6d4184778d",
        ),
        migrations.AddConstraint(
            model_name="engagement",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("accepted_at__isnull", True),
                    ("acceptance_basis__isnull", False),
                    _connector="OR",
                ),
                name="engagement_acceptance_states_its_basis",
            ),
        ),
        migrations.AddConstraint(
            model_name="engagement",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("acceptance_basis__isnull", True),
                    ("acceptance_basis__in", ["client", "declared_mandate"]),
                    _connector="OR",
                ),
                name="engagement_acceptance_basis_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="engagement",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("acceptance_basis", "declared_mandate"), _negated=True),
                    ("claim_contact_email__isnull", False),
                    _connector="OR",
                ),
                name="engagement_declared_mandate_has_claim_contact",
            ),
        ),
    ]
