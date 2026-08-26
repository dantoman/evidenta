"""Whether a value was read in the act, or inferred around it.

`ParameterStatus` already tracked our workflow -- drafted, approved, live,
replaced. It could not express the thing that actually varies about a fiscal
parameter: how firmly it is attached to its source. The two are independent, and
a value can legitimately be ACTIVE and PROVISIONAL at the same time.

The case that forced it: the 2026 personal exemptions cannot be quoted. The tax
service publishes amounts only in a retrospective annual note, so for 2026 none
exists yet; what exists is the 2025 figure plus two exhaustive change lists that
leave articles 33 to 35 untouched. Strong enough to calculate with, not strong
enough to defend at an inspection -- and those are different claims that a single
`status` column cannot hold apart.

Three things become possible, none of which were before: confirming a value later
is an insert with a changed confidence rather than a hunt through code; the
periods calculated under inferred values can be identified afterwards, because
the windows are versioned; and the interface can warn before a declaration is
filed rather than after.

Defaults to PROVISIONAL on the ORM path deliberately: a forgotten field then
overstates doubt, which shows a warning nobody needed, rather than letting an
inference pass as read-from-the-act.

Measured while writing this: that default does not reach raw SQL. Django applies
`default=` in Python and this migration drops the database default once the
backfill is done, so an INSERT that omits the column fails NOT NULL instead. Left
that way on purpose -- parameters arrive through the privileged SQL paths, and a
hard failure there is better than a quiet default, because it makes whoever loads
a rate state whether it was read in the act.

Additive under `C5`: two columns, one index, two checks; nothing dropped.
"""


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fiscal_parameters', '0002_source_act_identity'),
    ]

    operations = [
        migrations.AddField(
            model_name='fiscalparameter',
            name='provisional_reason',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='fiscalparameter',
            name='source_confidence',
            field=models.TextField(choices=[('confirmed', 'Confirmed'), ('provisional', 'Provisional')], default='provisional'),
        ),
        migrations.AddIndex(
            model_name='fiscalparameter',
            index=models.Index(fields=['source_confidence', 'status'], name='fiscal_parameter_conf_idx'),
        ),
        migrations.AddConstraint(
            model_name='fiscalparameter',
            constraint=models.CheckConstraint(condition=models.Q(('source_confidence__in', ['confirmed', 'provisional'])), name='fiscal_parameter_confidence_valid'),
        ),
        migrations.AddConstraint(
            model_name='fiscalparameter',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('source_confidence', 'provisional'), _negated=True), models.Q(models.Q(('provisional_reason__isnull', True), _negated=True), models.Q(('provisional_reason', ''), _negated=True)), _connector='OR'), name='fiscal_parameter_provisional_has_reason'),
        ),
    ]
