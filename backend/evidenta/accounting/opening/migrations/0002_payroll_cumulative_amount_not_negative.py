"""A payroll cumulative is a magnitude, never a movement -- ADR-061 closes `OD-04`.

The set has carried `amount` as `numeric(20,4)` with no sign constraint since
F1, deliberately: which way a contribution is signed was part of what `OD-04`
had to decide. ADR-061 decided it -- **all values positive, the meaning carried
by `code`** -- and that half of the decision belongs in the schema rather than in
a convention, because it is the half nothing else would catch.

Unconstrained, one tenant could load "exemptions granted to date" positive and
the next negative. Both loads succeed, the set holds two conventions, every test
passes, and the first wrong income tax appears a month later in a figure nobody
traces back to a sign. Same family as the four-decimal amount in ADR-059:
a property assumed upstream, unenforced in the schema, with a downstream
consumer that breaks quietly.

**Measured before writing** (superuser, past `FORCE ROW LEVEL SECURITY`, because
the owner and the app role both read 0 here whatever the table holds):
`opening_balance_payroll_cumulative` has **0 rows, 0 of them negative** on the
development database at 2026-08-30. There is nothing for this CHECK to validate
and nothing it can refuse retroactively -- which is exactly why it lands now and
not with `F2.B6`. A constraint that waits for the task that touches the table is
a constraint that may not get there, and the window in which two sign
conventions can coexist opens without anyone watching.

**Reversibility:** Django's own `RemoveConstraint`. No SQL file, no trigger, no
data touched; the migration adds a `CHECK` and takes it away again. It is not in
the round-trip list of `tests/schema_guard/test_reverse_sql.py` because that list
covers the hand-written SQL pairs, and this migration has none.

**Zero stays legal, and that is a statement.** An employee with an exemption
category but nothing granted yet carries `0`, which is a different fact from
carrying no row at all -- so the bound is `>= 0`, not `> 0`.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("opening", "0001_initial"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="openingbalancepayrollcumulative",
            constraint=models.CheckConstraint(
                condition=models.Q(amount__gte=0),
                name="opening_balance_payroll_amount_not_negative",
            ),
        ),
    ]
