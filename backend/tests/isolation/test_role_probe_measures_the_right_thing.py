"""The role probe, validated from the other side -- `T2`.

`tests/schema_guard/test_backfill_helper.py` proves the probe reports blindness
where blindness exists. That half alone is satisfied by a probe that always says
"blind", which would be a verification that cannot fail on the case it guards --
the shape this project has now been caught by often enough to test for it.

So this asserts the discriminating half: on the same table, in the same database,
**the owner is blind and the application role is not**. If the probe cannot tell
those two apart, its answer in a migration means nothing.

`fiscal_parameter` is the right table for it, and not by convenience: it is where
the silent failure actually happened. Its policies name `evidenta_app` for reads
and `evidenta_refdata` for writes, and name the owner nowhere -- while `FORCE ROW
LEVEL SECURITY` applies to owners too.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

import pytest
from django.db import connections

from evidenta.platform.rls.context import unguarded

pytestmark = pytest.mark.django_db(databases=["default", "migration", "refdata"])

TABLE = "fiscal_parameter"


def _count(alias: str) -> int:
    # `unguarded` because the question here is what the *role* sees, not what a
    # tenant sees: this table is global and has no tenant predicate. The context
    # guard would otherwise refuse the read on the application connection before
    # RLS ever got a say -- which would measure the guard, not the role.
    with (
        unguarded("T2: measuring what a database role can see"),
        connections[alias].cursor() as cursor,
    ):
        cursor.execute(f"SELECT count(*) FROM {TABLE}")
        row = cursor.fetchone()
        return int(row[0])


@pytest.fixture
def seeded(seed: Callable[..., None]) -> int:
    """One row, written the way this suite writes reference data.

    Through `seed()`, which uses the privileged committing connection: rows
    written inside another connection's test transaction are invisible to the
    application connection, so a cross-role comparison needs a committed row.
    That is not a detail of this test -- it is why the comparison is meaningful
    at all. And it needs no `FORCE` toggling: the privileged path is the one the
    policies name.
    """
    source_id = uuid.uuid4()
    seed(
        "INSERT INTO fiscal_parameter_source (id, act_type, act_number, act_date,"
        " effective_from, created_at) VALUES (%s, 'test', 'T2-PROBE',"
        " DATE '2020-01-01', DATE '2020-01-01', now())",
        [source_id],
    )
    seed(
        f"INSERT INTO {TABLE} (id, parameter_key, scope, value_type, value, valid_from,"
        " margin_basis, margin_reference, source_id, status, source_confidence,"
        " provisional_reason, created_at, updated_at)"
        " VALUES (%s, 'probe.role', 'global', 'integer', '1'::jsonb,"
        " DATE '2020-01-01', 'platform_convention', 'T2 — sondă de rol', %s, 'draft',"
        " 'provisional', 'probe', now(), now())",
        [uuid.uuid4(), source_id],
    )
    return _count("refdata")


def test_the_owner_is_blind_and_the_application_role_is_not(seeded: int) -> None:
    """The discriminating assertion: same table, same rows, two different answers.

    The owner sees nothing because no policy names it. The application role sees
    the rows because `fiscal_parameter_read` does. A probe that returned the same
    number for both would be measuring the table rather than the role.
    """
    assert seeded > 0, "nothing to be blind about; this test would pass vacuously"

    as_owner = _count("migration")
    as_application = _count("default")

    assert as_owner == 0, (
        f"the owner saw {as_owner} rows; this table's policies name evidenta_app and "
        "evidenta_refdata, and FORCE applies to owners too -- if this ever passes with a "
        "non-zero count, a policy was added and the migration helper's premise changed"
    )
    assert as_application == seeded, (
        f"the application role saw {as_application} of {seeded} rows through "
        "`fiscal_parameter_read`; a read policy that stopped returning rows would break "
        "every fiscal calculation silently"
    )


def test_the_application_role_still_cannot_write_what_it_may_read(seeded: int) -> None:
    """Reading is not writing, and `IZ-78` is the rule this backs from the test side.

    The default privileges in `0001_roles.sql` grant the application writes on
    every owner-created table; a global table is read-only only because somebody
    remembered the REVOKE.
    """
    from django.db import InternalError, ProgrammingError

    with (
        pytest.raises((ProgrammingError, InternalError)),
        unguarded("T2: the write must be refused by privilege, not by the context guard"),
        connections["default"].cursor() as cursor,
    ):
        cursor.execute(f"UPDATE {TABLE} SET provisional_reason = 'rewritten by the app'")
