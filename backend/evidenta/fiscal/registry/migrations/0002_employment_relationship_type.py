"""The three forms of work relationship, as a table -- ADR-071, `C1(b)`.

**What lands here.** A global read-only vocabulary of exactly three codes, the
ones the first indent of point 1.1 of annex 1 to Law 489/1999 distinguishes.
Nothing about a tenant, nothing configurable: a domain that does not correspond
to a real form becomes a foreign key violation rather than an accepted value.

**Why the seeding goes through `backfill()` and not through `RunSQL`.** The one
door (`OD-94`, `P0`): the helper checks the cardinality *before* writing and
**measures** what the running role can see instead of trusting a declaration.
Here the claim is `expected=0` -- the table is created two operations above, so
"it touched nothing" and "there was nothing to touch" have to stay distinguishable
even in the case where they happen to coincide.

**The owner write policy was argued away and then measured back in.** The first
draft of the SQL had none: the seeding goes through the door, the door suspends
FORCE inside this transaction, so a permanent policy looked like the exception
that needs its own reason (`OD-95`). `test_reference_load_policy` disagreed with
a fact rather than an opinion -- under FORCE, a privilege *without a policy* sees
nothing, so `writer_role = "evidenta_owner"` would have declared a write path
that does not exist. `permission` carries the same policy for the same reason.
The declaration and the database now say the same thing.

**The CHECK is in this migration, after the write, deliberately** -- rule (c) of
`OD-94`. Split into a later migration, a seed that wrote the wrong codes would go
green here and fail somewhere with no context. In `fiscal_parameters/0007` the
constraint in the same migration is the only reason anybody discovered the
backfill had written nothing.

**Reversible.** The reverse drops the constraint, unseeds through the same door,
withdraws the policy through `0063_…down.sql`, and drops the table. Nothing here
carries meaning that a reverse would destroy -- unlike a margin, which is why
`fiscal_parameters/0007` is irreversible and this is not.
"""

from django.db import migrations, models

from evidenta.platform.rls.backfill import backfill
from evidenta.platform.rls.sql import run_sql_file

#: The vocabulary, with the anchor each code carries into the table. Written out
#: rather than derived from a Python enum: this is the migration that *defines*
#: the catalogue, and a later edit to an enum must not silently mean the applied
#: rows said something else (`C31`, the same reason SQL files are append-only).
SEED = """
INSERT INTO employment_relationship_type (code, statutory_reference) VALUES
  ('employment_contract',
   'Anexa nr. 1 la Legea nr. 489/1999, pct. 1.1, prima liniuță — „persoane cu contract individual de muncă"'),
  ('service_relationship',
   'Anexa nr. 1 la Legea nr. 489/1999, pct. 1.1, prima liniuță — „raporturi de serviciu în baza actului administrativ"'),
  ('civil_contract',
   'Anexa nr. 1 la Legea nr. 489/1999, pct. 1.1, prima liniuță — „ori prin alte tipuri de contracte civile în vederea executării de lucrări sau prestării de servicii"; art. 19 alin. (7) teza a doua')
"""

UNSEED = "DELETE FROM employment_relationship_type"

REASON = (
    "Seeding the three-value vocabulary defined by ADR-071. The owner has no "
    "policy on this table, so under FORCE ROW LEVEL SECURITY it would see and "
    "write nothing; the suspension lasts for this transaction only."
)


def seed(apps, schema_editor):
    backfill(
        schema_editor,
        "employment_relationship_type",
        expected=0,
        statements=SEED,
        reason=REASON,
    )


def unseed(apps, schema_editor):
    backfill(
        schema_editor,
        "employment_relationship_type",
        expected=3,
        statements=UNSEED,
        reason=REASON,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("fiscal_registry", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="EmploymentRelationshipType",
            fields=[
                (
                    "code",
                    models.TextField(primary_key=True, serialize=False),
                ),
                ("statutory_reference", models.TextField()),
            ],
            options={
                "db_table": "employment_relationship_type",
            },
        ),
        run_sql_file(
            "0063_employment_relationship_type",
            up_sha256="56a75a571797d52ad7dfa005b24b7b8798b1a46f3c71e07a2c17db81bb333091",
            down_sha256="4de8a285c61f0d0a78a14aa23ad564329e20aae46d55d15b8110562f43978c71",
        ),
        migrations.RunPython(seed, unseed),
        migrations.AddConstraint(
            model_name="employmentrelationshiptype",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    code__in=[
                        "employment_contract",
                        "service_relationship",
                        "civil_contract",
                    ]
                ),
                name="employment_relationship_type_vocabulary_closed",
            ),
        ),
    ]
