"""The model guard, and proof that it can fail.

A guard that only ever reports "no findings" is indistinguishable from a guard
that checks nothing. The live schema currently has no business tables, so
``test_live_schema_is_clean`` passes trivially -- and would keep passing if the
audit were broken.

So every rule gets a companion test that builds a deliberately non-compliant
table and asserts the rule fires. Those are the tests that keep this file honest
until there are real tables to check.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from django.db import connections

from evidenta.platform.rls.schema_audit import Contract, Finding, audit

pytestmark = pytest.mark.django_db(databases=["default", "migration"])


@pytest.fixture
def owner_cursor() -> Iterator[object]:
    """DDL runs as the owner; the surrounding test transaction rolls it back."""
    with connections["migration"].cursor() as cursor:
        yield cursor


#: A contract that exists only for the append-only probes below. Declaring the
#: probe here rather than in infra/schema/append_only.toml keeps the guard's
#: self-tests independent of what the product happens to have built.
#: The IZ-76 probe. Declared here rather than pointing at a real contract entry:
#: the test used to build a table named `fiscal_parameter`, which worked for as
#: long as no such table existed. F0.8 created it, and the probe's CREATE TABLE
#: started failing with "already exists" -- a guard self-test broken by the
#: arrival of the very schema it guards. Third time this shape appeared
#: (`audit_event`, `document_event`), and the fix is the same each time: a probe
#: names a probe.
DRIFT_PROBE = Contract(
    tables=[
        {
            "name": "probe_drift",
            "tenant_column": False,
            "policy_shape": "global_read_only",
            "reason": "Probe for IZ-76.",
            "source": "tests/schema_guard",
        }
    ],
    patterns=[],
    append_only=[],
)

APPEND_ONLY_PROBE = Contract(
    tables=[],
    patterns=[],
    append_only=[{"name": "probe_append_only", "partition_column": "occurred_at"}],
)


def rules(findings: list[Finding], table: str) -> set[str]:
    return {finding.rule for finding in findings if finding.table == table}


def compliant_table(cursor: object, name: str, extra_columns: str = "") -> None:
    """A table that satisfies every rule, as the baseline for one-change tests."""
    cursor.execute(  # type: ignore[attr-defined]
        f"""
        CREATE TABLE {name} (
            id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL
            {extra_columns}
        );
        ALTER TABLE {name} ENABLE ROW LEVEL SECURITY;
        ALTER TABLE {name} FORCE  ROW LEVEL SECURITY;
        CREATE POLICY {name}_access ON {name} FOR ALL TO evidenta_app
            USING (true) WITH CHECK (true);
        """
    )


def test_refuses_a_table_declared_twice() -> None:
    """The RLS contract may not carry two declarations for one table.

    This is the shape the guard is least able to survive: two entries, the last
    one silently in force, and the audit reporting compliance against a
    declaration nobody knew had won. It reached the real file once, as a second
    set of fiscal tables, and nothing said so.
    """
    with pytest.raises(ValueError, match="declared twice"):
        Contract(
            tables=[
                {"name": "fiscal_parameter", "tenant_column": False, "policy_shape": "system"},
                {
                    "name": "fiscal_parameter",
                    "tenant_column": False,
                    "policy_shape": "global_read_only",
                },
            ],
            patterns=[],
            append_only=[],
        )


def test_live_schema_is_clean(owner_cursor: object) -> None:
    assert audit(owner_cursor) == []


def test_detects_missing_tenant_column(owner_cursor: object) -> None:
    owner_cursor.execute(  # type: ignore[attr-defined]
        """
        CREATE TABLE probe_no_tenant (id uuid PRIMARY KEY);
        ALTER TABLE probe_no_tenant ENABLE ROW LEVEL SECURITY;
        ALTER TABLE probe_no_tenant FORCE  ROW LEVEL SECURITY;
        CREATE POLICY p ON probe_no_tenant FOR ALL TO evidenta_app
            USING (true) WITH CHECK (true);
        """
    )
    assert "IZ-70" in rules(audit(owner_cursor), "probe_no_tenant")


def test_detects_rls_not_enabled(owner_cursor: object) -> None:
    owner_cursor.execute(  # type: ignore[attr-defined]
        "CREATE TABLE probe_no_rls (id uuid PRIMARY KEY, tenant_id uuid NOT NULL)"
    )
    assert "IZ-71" in rules(audit(owner_cursor), "probe_no_rls")


def test_detects_missing_force_row_level_security(owner_cursor: object) -> None:
    """Without FORCE, the owner bypasses every policy and RLS is decorative."""
    owner_cursor.execute(  # type: ignore[attr-defined]
        """
        CREATE TABLE probe_no_force (id uuid PRIMARY KEY, tenant_id uuid NOT NULL);
        ALTER TABLE probe_no_force ENABLE ROW LEVEL SECURITY;
        CREATE POLICY p ON probe_no_force FOR ALL TO evidenta_app
            USING (true) WITH CHECK (true);
        """
    )
    assert "IZ-72" in rules(audit(owner_cursor), "probe_no_force")


def test_detects_write_policy_without_with_check(owner_cursor: object) -> None:
    """A write path with no WITH CHECK writes rows that vanish on commit."""
    owner_cursor.execute(  # type: ignore[attr-defined]
        """
        CREATE TABLE probe_no_check (id uuid PRIMARY KEY, tenant_id uuid NOT NULL);
        ALTER TABLE probe_no_check ENABLE ROW LEVEL SECURITY;
        ALTER TABLE probe_no_check FORCE  ROW LEVEL SECURITY;
        CREATE POLICY p ON probe_no_check FOR ALL TO evidenta_app USING (true);
        """
    )
    assert "IZ-73" in rules(audit(owner_cursor), "probe_no_check")


def test_detects_name_column_forced_to_byte_order(owner_cursor: object) -> None:
    compliant_table(owner_cursor, "probe_bad_name", ', name text COLLATE "C"')
    assert "C34" in rules(audit(owner_cursor), "probe_bad_name")


def test_detects_code_column_left_on_linguistic_collation(owner_cursor: object) -> None:
    compliant_table(owner_cursor, "probe_bad_code", ", account_code text")
    assert "C34" in rules(audit(owner_cursor), "probe_bad_code")


def test_accepts_correct_collation_on_both(owner_cursor: object) -> None:
    compliant_table(
        owner_cursor, "probe_good_collation", ', name text, account_code text COLLATE "C"'
    )
    assert rules(audit(owner_cursor), "probe_good_collation") == set()


def test_detects_incoming_foreign_key_on_append_only_table(owner_cursor: object) -> None:
    """R21. The rule that decides whether partitioning stays a maintenance task.

    The probe runs against a synthetic contract, so its name cannot collide with
    a table the product actually builds. Naming probes after real contract
    entries broke this test twice as those tables became real.
    """
    owner_cursor.execute(  # type: ignore[attr-defined]
        """
        CREATE TABLE probe_append_only (
            id bigint PRIMARY KEY,
            tenant_id uuid NOT NULL,
            occurred_at timestamptz NOT NULL
        );
        ALTER TABLE probe_append_only ENABLE ROW LEVEL SECURITY;
        ALTER TABLE probe_append_only FORCE  ROW LEVEL SECURITY;
        CREATE POLICY p ON audit_event FOR ALL TO evidenta_app
            USING (true) WITH CHECK (true);

        CREATE TABLE probe_referrer (
            id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL,
            probe_id bigint REFERENCES probe_append_only(id)
        );
        ALTER TABLE probe_referrer ENABLE ROW LEVEL SECURITY;
        ALTER TABLE probe_referrer FORCE  ROW LEVEL SECURITY;
        CREATE POLICY p2 ON probe_referrer FOR ALL TO evidenta_app
            USING (true) WITH CHECK (true);
        """
    )
    assert "IZ-77" in rules(audit(owner_cursor, APPEND_ONLY_PROBE), "probe_append_only")


def test_detects_nullable_partition_column(owner_cursor: object) -> None:
    owner_cursor.execute(  # type: ignore[attr-defined]
        """
        CREATE TABLE probe_append_only (
            id bigint PRIMARY KEY,
            tenant_id uuid NOT NULL,
            occurred_at timestamptz
        );
        ALTER TABLE probe_append_only ENABLE ROW LEVEL SECURITY;
        ALTER TABLE probe_append_only FORCE  ROW LEVEL SECURITY;
        CREATE POLICY p ON audit_event FOR ALL TO evidenta_app
            USING (true) WITH CHECK (true);
        """
    )
    assert "IZ-77" in rules(audit(owner_cursor, APPEND_ONLY_PROBE), "probe_append_only")


def test_detects_contract_drifting_from_the_schema(owner_cursor: object) -> None:
    """IZ-76. An exception nobody needs any more is worse than no contract.

    The table is declared as having no tenant column and it has one. That is
    drift in the direction that matters: the contract is the thing R1 and R2 are
    checked against, so an entry that stopped being true silently widens what the
    guard accepts.
    """
    owner_cursor.execute(  # type: ignore[attr-defined]
        """
        CREATE TABLE probe_drift (
            id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL
        );
        ALTER TABLE probe_drift ENABLE ROW LEVEL SECURITY;
        ALTER TABLE probe_drift FORCE  ROW LEVEL SECURITY;
        CREATE POLICY p ON probe_drift FOR ALL TO evidenta_app
            USING (true) WITH CHECK (true);
        """
    )
    assert "IZ-76" in rules(audit(owner_cursor, DRIFT_PROBE), "probe_drift")


# --- IZ-78: a global table is written by its declared role and nobody else ------
#
# Three probes, each a real shape that has occurred: the application role left
# holding INSERT on a global table (0047 found that one late), a write policy for
# an undeclared role (0044's owner policy was exactly that, retracted by 0060),
# and a writer declared with nothing behind it.

WRITER_PROBE = Contract(
    tables=[
        {
            "name": "probe_global",
            "tenant_column": False,
            "policy_shape": "global_read_only",
            "writer_role": "evidenta_refdata",
            "reason": "Probe for IZ-78.",
            "source": "tests/schema_guard",
        },
        {
            "name": "probe_nobody_writes",
            "tenant_column": False,
            "policy_shape": "global_read_only",
            "reason": "Probe for IZ-78, no writer declared.",
            "source": "tests/schema_guard",
        },
    ],
    patterns=[],
    append_only=[],
)


def global_table(cursor: object, name: str, writer_policy: str = "") -> None:
    cursor.execute(  # type: ignore[attr-defined]
        f"""
        CREATE TABLE {name} (id uuid PRIMARY KEY);
        ALTER TABLE {name} ENABLE ROW LEVEL SECURITY;
        ALTER TABLE {name} FORCE  ROW LEVEL SECURITY;
        CREATE POLICY {name}_read ON {name} FOR SELECT TO evidenta_app USING (true);
        REVOKE INSERT, UPDATE, DELETE ON {name} FROM evidenta_app;
        {writer_policy}
        """
    )


def test_iz78_passes_a_global_table_with_exactly_its_writer(owner_cursor: object) -> None:
    global_table(
        owner_cursor,
        "probe_global",
        """
        CREATE POLICY probe_global_w ON probe_global FOR ALL TO evidenta_refdata
            USING (true) WITH CHECK (true);
        GRANT SELECT, INSERT, UPDATE ON probe_global TO evidenta_refdata;
        """,
    )
    findings = [f for f in audit(owner_cursor, WRITER_PROBE) if f.table == "probe_global"]
    assert "IZ-78" not in {f.rule for f in findings}, findings


def test_iz78_catches_the_application_role_holding_a_write_privilege(owner_cursor: object) -> None:
    """The default privileges from 0001 grant it; only an explicit REVOKE removes it."""
    owner_cursor.execute(  # type: ignore[attr-defined]
        """
        CREATE TABLE probe_nobody_writes (id uuid PRIMARY KEY);
        ALTER TABLE probe_nobody_writes ENABLE ROW LEVEL SECURITY;
        ALTER TABLE probe_nobody_writes FORCE  ROW LEVEL SECURITY;
        CREATE POLICY p ON probe_nobody_writes FOR SELECT TO evidenta_app USING (true);
        """
    )
    findings = audit(owner_cursor, WRITER_PROBE)
    assert "IZ-78" in rules(findings, "probe_nobody_writes")
    assert any(
        "evidenta_app holds" in f.detail for f in findings if f.table == "probe_nobody_writes"
    )


def test_iz78_catches_a_write_policy_for_an_undeclared_role(owner_cursor: object) -> None:
    """0044's owner policy, in miniature."""
    global_table(
        owner_cursor,
        "probe_nobody_writes",
        "CREATE POLICY p_owner ON probe_nobody_writes FOR ALL TO evidenta_owner "
        "USING (true) WITH CHECK (true);",
    )
    findings = audit(owner_cursor, WRITER_PROBE)
    assert any(
        f.rule == "IZ-78" and f.table == "probe_nobody_writes" and "second door" in f.detail
        for f in findings
    ), findings


def test_iz78_catches_a_declared_writer_that_cannot_write(owner_cursor: object) -> None:
    global_table(owner_cursor, "probe_global")  # declared writer, no policy, no grant
    findings = audit(owner_cursor, WRITER_PROBE)
    assert any(
        f.rule == "IZ-78" and f.table == "probe_global" and "no INSERT privilege" in f.detail
        for f in findings
    ), findings


def test_iz78_catches_the_writer_reaching_an_undeclared_table(owner_cursor: object) -> None:
    """The sweep: a privilege on a tenant table turns the loading role into a
    second application role, and nothing on the table's own side would say so."""
    compliant_table(owner_cursor, "probe_tenant_scoped")
    owner_cursor.execute("GRANT SELECT ON probe_tenant_scoped TO evidenta_refdata")  # type: ignore[attr-defined]
    findings = audit(owner_cursor, WRITER_PROBE)
    assert any(
        f.rule == "IZ-78"
        and f.table == "probe_tenant_scoped"
        and "not its declared writer" in f.detail
        for f in findings
    ), findings
