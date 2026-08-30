"""What the pre-door migrations were supposed to produce, asserted permanently.

`OD-98`. Two migrations wrote data before `platform/rls/backfill.py` existed, so
neither declared its cardinality and neither measured what its role could see.
**Nothing applied and committed gets rewritten to look consistent.** Rewriting a
migration is verified once, on the day somebody rewrites it, and never again;
the state it produced is verified on every run, and the state is the fact that
matters. The migration is the means.

So each pre-door migration gets one permanent assertion here, and the list in
`tests/architecture/test_migrations_write_through_one_door.py` points at it.

**The category is named by its deficit, not by its history** -- *unproven state*,
not "migrations that predate the rule". The difference is what happens to it: a
list defined by history grows with every migration and invites a retrofit; a list
defined by deficit **shrinks as assertions are added** and asks for nothing else.
"""

from __future__ import annotations

import pytest
from django.db import connections

from evidenta.platform.identity.permissions import PERMISSIONS

pytestmark = pytest.mark.django_db(databases=["default", "migration"])


def _scalar(sql: str) -> int:
    with connections["migration"].cursor() as cursor:
        cursor.execute(sql)
        row = cursor.fetchone()
        return int(row[0])


def test_identity_0003_seeded_the_whole_permission_catalogue() -> None:
    """`identity/0003_roles` syncs `PERMISSIONS` into the table, and nothing counted.

    The catalogue is code (ADR-020); the table is its image. If the sync ever
    wrote a subset -- the failure the helper's cardinality check exists to catch --
    every role composed afterwards would be missing permissions that the code
    believes exist, and nothing would say so.
    """
    expected = {definition.key for definition in PERMISSIONS}
    assert expected, "the catalogue itself is empty; this assertion would pass vacuously"

    with connections["migration"].cursor() as cursor:
        cursor.execute("SELECT key, scope FROM permission")
        rows = dict(cursor.fetchall())

    assert set(rows) == expected, (
        "the permission table and the catalogue in code have diverged; "
        f"missing {sorted(expected - set(rows))}, extra {sorted(set(rows) - expected)}"
    )
    assert all(rows[d.key] == d.scope for d in PERMISSIONS), "a permission changed scope"


def test_fiscal_parameters_0007_left_every_margin_either_sourced_or_absent() -> None:
    """`fiscal_parameters/0007` moved asserted dates out of `valid_from`.

    Its backfill ran as the owner under FORCE with the row filter suspended, and
    counted nothing. What it was supposed to leave behind: no row with a margin
    it cannot source, and no row without a margin and without a reason. The
    CHECKs enforce that going forward; this asserts the migration actually
    achieved it on the rows that were already there.
    """
    unsourced = _scalar(
        "SELECT count(*) FROM fiscal_parameter WHERE valid_from IS NOT NULL "
        "AND (margin_basis IS NULL OR margin_reference IS NULL OR margin_reference = '')"
    )
    assert unsourced == 0, f"{unsourced} rows carry a margin with nothing establishing it"

    unexplained = _scalar(
        "SELECT count(*) FROM fiscal_parameter WHERE valid_from IS NULL "
        "AND (provisional_reason IS NULL OR provisional_reason = '')"
    )
    assert unexplained == 0, f"{unexplained} rows have no margin and no reason"


def test_fiscal_parameters_0007_kept_the_observation_it_promised_to_keep() -> None:
    """The dates were moved, not deleted -- which is the migration's own claim.

    A backfill that silently dropped them would look identical from the outside:
    the CHECKs would pass, the rows would be consistent, and the knowledge of
    where each value was read would simply be gone.
    """
    moved = _scalar("SELECT count(*) FROM fiscal_parameter WHERE observed_in IS NOT NULL")
    without_margin = _scalar("SELECT count(*) FROM fiscal_parameter WHERE valid_from IS NULL")
    assert moved == without_margin, (
        f"{without_margin} rows lost their margin but only {moved} kept an observation; "
        "the migration promised to move the dates rather than discard them"
    )
