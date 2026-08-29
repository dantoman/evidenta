"""The loading role reads what it writes, on every reference table -- ADR-049.

The first version of this file guarded one thing on two tables: `0044` gave
`evidenta_owner` `FOR ALL` on the chart tables, and the read half of that policy
was what made `load_coa_template` idempotent -- it finds existing rows before
writing. Narrow the policy to writes, which is what prudent tightening looks like
at review, and the loader inserts everything on every run and fails on
uniqueness, with an error that reads as a data problem.

ADR-049 moved the writes under `evidenta_refdata` and retracted the owner's
policy, so the role changed and the table list grew. The dependency did not: a
loader that cannot see its own rows is not idempotent, and neither is one that
cannot see the `privileged_access_log` rows it wrote. So the assertion now reads
the contract -- every table that declares a `writer_role` -- and checks the
declared writer can both read and insert *through a policy*, not only by
privilege: under FORCE ROW LEVEL SECURITY a privilege without a policy sees
nothing.

Measured on the live database while writing the first version, on a table whose
policy *is* `TO evidenta_app`: the same `count(*)` answers **3** as superuser
and **0** as owner, in the same instant. Both true; one useful.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from django.db import connections

from evidenta.platform.rls.schema_audit import Contract

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

#: `pg_policy.polcmd`: `*` is ALL, `r` SELECT, `a` INSERT, `w` UPDATE, `d` DELETE.
READS = ("*", "r")
INSERTS = ("*", "a")


def declared_writers() -> list[tuple[str, str]]:
    contract = Contract()
    return sorted(
        (name, str(d["writer_role"])) for name, d in contract.tables.items() if d.get("writer_role")
    )


@pytest.fixture
def cursor() -> Iterator[object]:
    with connections["migration"].cursor() as handle:
        yield handle


def policies_for(cursor: object, table: str, role: str) -> list[tuple[str, str]]:
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
        [table, role],
    )
    return list(cursor.fetchall())  # type: ignore[attr-defined]


def test_the_contract_declares_at_least_the_tables_the_loaders_write() -> None:
    """A regression on the list itself: the chart, the fiscal set, the log."""
    tables = {name for name, _ in declared_writers()}
    assert {
        "coa_template",
        "coa_template_account",
        "fiscal_parameter",
        "fiscal_parameter_source",
        "fiscal_parameter_confidence_event",
        "privileged_access_log",
        "normative_act",
    } <= tables


@pytest.mark.parametrize(("table", "role"), declared_writers())
def test_the_writer_may_still_read_what_it_writes(cursor: object, table: str, role: str) -> None:
    """Narrowing the writer's policy to writes breaks idempotency, silently until
    the first re-run.
    """
    cursor.execute("SELECT to_regclass(%s)", [f"public.{table}"])  # type: ignore[attr-defined]
    if cursor.fetchone()[0] is None:  # type: ignore[attr-defined]
        pytest.skip(f"{table} is declared and not built yet")

    policies = policies_for(cursor, table, role)
    assert policies, (
        f"{table} nu are nicio politică pentru {role}. Sub FORCE ROW LEVEL SECURITY "
        f"asta înseamnă că încărcătorul nu mai poate nici scrie, nici citi — vezi "
        f"infra/migrations/0060_refdata_write_policies.up.sql și ADR-049."
    )
    commands = [command for _, command in policies]
    assert any(command in READS for command in commands), (
        f"politica lui {role} pe {table} nu acoperă SELECT ({commands}). Încărcătorul își "
        f"citește rândurile existente prin ea ca să fie idempotent: fără SELECT, a doua "
        f"rulare încearcă să insereze tot și cade pe unicitate, iar eroarea arată ca o "
        f"problemă de date, nu ca o politică restrânsă."
    )
    assert any(command in INSERTS for command in commands), (
        f"politica lui {role} pe {table} nu acoperă INSERT ({commands}): contractul "
        f"declară un scriitor care nu poate scrie."
    )
