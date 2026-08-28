"""The reference-load policy is read by somebody, and that is not obvious.

`0044` gave `evidenta_owner` `FOR ALL ... USING (true) WITH CHECK (true)` on the
two global chart tables, for one stated reason: `FORCE ROW LEVEL SECURITY`
applies to the table owner too, so the loader -- running as the owner, exactly as
intended -- could not write.

**The read half came along by accident, and something now depends on it.**
`manage.py load_coa_template` is idempotent because it first reads the accounts
that already exist and updates instead of inserting. That read passes through the
same policy. Narrow it to `FOR INSERT`/`FOR UPDATE` -- which is what prudent
tightening looks like at review, and would pass one -- and the loader stops
seeing anything: it attempts 476 inserts, the unique constraint refuses them, and
the failure reads as a data problem rather than as a narrowed policy.

Measured on the live database while writing this, on a table whose policy *is*
`TO evidenta_app`: the same `count(*)` answers **3** as superuser and **0** as
owner, in the same instant. Both true; one useful.

So the dependency is asserted rather than described. A comment saying "somebody
reads this" is exactly the kind of note that survives the change it was meant to
prevent.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from django.db import connections

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

#: The two global tables of the chart, and the role the loader runs as.
REFERENCE_TABLES = ("coa_template", "coa_template_account")
LOADER_ROLE = "evidenta_owner"

#: `pg_policy.polcmd`: `*` is ALL, and ALL is what includes SELECT. `r`, `a`, `w`
#: and `d` are SELECT, INSERT, UPDATE and DELETE taken separately.
ALL_COMMANDS = "*"


@pytest.fixture
def cursor() -> Iterator[object]:
    with connections["migration"].cursor() as handle:
        yield handle


def owner_policies(cursor: object, table: str) -> list[tuple[str, str]]:
    cursor.execute(  # type: ignore[attr-defined]
        """
        SELECT p.polname, p.polcmd
          FROM pg_policy p
          JOIN pg_class c ON c.oid = p.polrelid
         WHERE c.relname = %s
           AND EXISTS (
               SELECT 1 FROM pg_roles r
                WHERE r.oid = ANY(p.polroles) AND r.rolname = %s
           )
        """,
        [table, LOADER_ROLE],
    )
    return list(cursor.fetchall())  # type: ignore[attr-defined]


@pytest.mark.parametrize("table", REFERENCE_TABLES)
def test_the_owner_may_still_read_what_it_writes(cursor: object, table: str) -> None:
    """Narrowing the loader's policy to writes breaks its idempotency, silently
    until the first re-run.
    """
    policies = owner_policies(cursor, table)
    assert policies, (
        f"{table} nu are nicio politică pentru {LOADER_ROLE}. Sub FORCE ROW LEVEL "
        f"SECURITY asta înseamnă că încărcătorul de plan de conturi nu mai poate "
        f"nici scrie, nici citi — vezi infra/migrations/0044_coa_reference_load.up.sql."
    )
    assert any(command == ALL_COMMANDS for _, command in policies), (
        f"politica lui {LOADER_ROLE} pe {table} a fost îngustată la "
        f"{[command for _, command in policies]}. `load_coa_template` își citește "
        f"rândurile existente prin ea ca să fie idempotent: fără SELECT, a doua "
        f"rulare încearcă să insereze tot și cade pe unicitate, iar eroarea arată "
        f"ca o problemă de date, nu ca o politică restrânsă."
    )
