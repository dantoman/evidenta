"""Suite 2 -- the model guard.

Suite 1 catches today's bug. This one catches the table someone adds in three
years without knowing the rule, which is why it is the more valuable of the two
in the long run.

It enumerates the schema and compares it against two contracts that live in
exactly one place each:

    infra/rls/exceptions.toml       which tables may lack tenant context, and
                                    what shape their policy has instead
    infra/schema/append_only.toml   which tables carry the partitioning discipline

Reading the contracts rather than hard-coding them is the point. A guard whose
expectations live in its own source is a guard that gets edited to make the suite
pass -- which is the failure mode the contracts exist to prevent.
"""

from __future__ import annotations

import fnmatch
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
RLS_CONTRACT = REPO_ROOT / "infra" / "rls" / "exceptions.toml"
APPEND_ONLY_CONTRACT = REPO_ROOT / "infra" / "schema" / "append_only.toml"

# Columns whose ordering is linguistic, and columns whose ordering must be byte
# order (ADR-015, C34). Matched on name because the guard runs before any model
# metadata exists -- and because the rule is about what the column *means*.
NAME_COLUMN_SUFFIXES = ("name", "name_ro", "denumire", "label", "description", "title")
CODE_COLUMN_SUFFIXES = ("code", "idno", "idnp", "sku", "number", "series", "vat_code")


@dataclass(frozen=True)
class Finding:
    rule: str
    table: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.rule}] {self.table}: {self.detail}"


def _load(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _index(entries: list[dict[str, Any]], contract: str) -> dict[str, dict[str, Any]]:
    """Index declarations by name, refusing a name that appears twice.

    A dict comprehension keeps the last entry and says nothing about the first.
    That is the one failure mode a contract file must not have: two answers for
    one name, one of them silently winning, and a guard reporting compliance
    against a declaration nobody knew was in force.

    Found the way these things are found -- a second set of fiscal tables was
    added to the RLS contract by mistake, and nothing complained.
    """
    indexed: dict[str, dict[str, Any]] = {}
    for entry in entries:
        name = entry["name"]
        if name in indexed:
            raise ValueError(
                f"{contract}: {name!r} is declared twice. A contract with two answers "
                f"for one name has no answer -- delete one of them."
            )
        indexed[name] = entry
    return indexed


class Contract:
    """The declared shape of the schema.

    Loads from the contract files by default, and accepts explicit data instead.
    The second form exists for the guard's own self-tests: each rule is proved by
    building a deliberately non-compliant table, and naming that probe after a
    real contract entry meant the probe collided with the real table the moment
    that table was built. It happened three times -- audit_event, then
    document_event -- before the collision was treated as the bug rather than the
    name.
    """

    def __init__(
        self,
        tables: list[dict[str, Any]] | None = None,
        patterns: list[dict[str, Any]] | None = None,
        append_only: list[dict[str, Any]] | None = None,
    ) -> None:
        if tables is None and patterns is None and append_only is None:
            rls = _load(RLS_CONTRACT)
            tables = rls.get("table", [])
            patterns = rls.get("table_pattern", [])
            append_only = _load(APPEND_ONLY_CONTRACT).get("table", [])

        self.tables = _index(tables or [], "infra/rls/exceptions.toml")
        self.patterns: list[dict[str, Any]] = patterns or []
        self.append_only = _index(append_only or [], "infra/schema/append_only.toml")

    def declaration_for(self, table: str) -> dict[str, Any] | None:
        if table in self.tables:
            return self.tables[table]
        for pattern in self.patterns:
            if fnmatch.fnmatch(table, pattern["pattern"]):
                return pattern
        return None

    def tenant_column_for(self, table: str) -> str | None:
        """The column that carries tenant context, or None if declared exempt.

        ``tenant_column`` accepts three forms, and the third is not a loophole:

            true                 the column is ``tenant_id`` (the default)
            false                the table is exempt, with a stated reason
            "client_tenant_id"   the column exists under another name

        The third exists because ``engagement_company_scope`` carries the *client*
        tenant, and naming it ``tenant_id`` would suggest it belongs to whichever
        tenant is in context -- which is exactly what it does not mean.
        """
        declaration = self.declaration_for(table)
        if declaration is None:
            return "tenant_id"
        declared = declaration.get("tenant_column", True)
        if declared is False:
            return None
        if declared is True:
            return "tenant_id"
        return str(declared)

    def is_system(self, table: str) -> bool:
        declaration = self.declaration_for(table)
        return bool(declaration and declaration.get("policy_shape") == "system")


def audit(cursor: Any, contract: Contract | None = None) -> list[Finding]:
    """Return every way the live schema departs from the contracts."""
    contract = contract or Contract()
    findings: list[Finding] = []

    cursor.execute(
        """
        SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
         ORDER BY c.relname
        """
    )
    tables = cursor.fetchall()

    for name, rls_enabled, rls_forced in tables:
        if contract.is_system(name):
            continue

        # IZ-70 -- tenant context column
        expected_column = contract.tenant_column_for(name)
        if expected_column is not None:
            cursor.execute(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=%s AND column_name=%s",
                [name, expected_column],
            )
            if cursor.fetchone() is None:
                findings.append(
                    Finding(
                        "IZ-70",
                        name,
                        f"no {expected_column} and not declared in "
                        f"infra/rls/exceptions.toml. Adding it to the contract to "
                        f"silence this is the wrong fix: the contract is an ADR, "
                        f"the table is a bug.",
                    )
                )

        # IZ-71 / IZ-72 -- RLS enabled, and enforced against the owner too
        if not rls_enabled:
            findings.append(Finding("IZ-71", name, "row level security is not enabled"))
        if not rls_forced:
            findings.append(
                Finding(
                    "IZ-72",
                    name,
                    "FORCE ROW LEVEL SECURITY is missing -- the table owner bypasses "
                    "every policy, which makes RLS decorative",
                )
            )

        # IZ-73 -- a write path with no WITH CHECK lets a row be written into
        # another tenant and become invisible on commit
        cursor.execute(
            "SELECT polname, polcmd, polwithcheck IS NOT NULL FROM pg_policy p "
            "JOIN pg_class c ON c.oid = p.polrelid WHERE c.relname = %s",
            [name],
        )
        policies = cursor.fetchall()
        if not policies:
            findings.append(Finding("IZ-71", name, "no RLS policy is defined"))
        for policy_name, command, has_check in policies:
            if command in ("*", "a", "w") and not has_check:
                findings.append(
                    Finding(
                        "IZ-73",
                        name,
                        f"policy {policy_name!r} covers writes but has no WITH CHECK: "
                        f"a row can be written with a foreign tenant_id and become "
                        f"invisible the moment it commits",
                    )
                )

        findings.extend(_audit_collation(cursor, name))

    findings.extend(_audit_exception_list(cursor, contract, {t[0] for t in tables}))
    findings.extend(_audit_append_only(cursor, contract))
    return findings


def _audit_collation(cursor: Any, table: str) -> list[Finding]:
    """C34 / ADR-015, in both directions."""
    findings: list[Finding] = []
    cursor.execute(
        """
        SELECT a.attname, coll.collname
          FROM pg_attribute a
          JOIN pg_class c ON c.oid = a.attrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace
          LEFT JOIN pg_collation coll ON coll.oid = a.attcollation
          JOIN pg_type t ON t.oid = a.atttypid
         WHERE n.nspname = 'public' AND c.relname = %s
           AND a.attnum > 0 AND NOT a.attisdropped
           -- Compared by name, not by regtype cast: a cast to a type that is not
           -- installed makes the whole audit crash instead of reporting.
           AND t.typname IN ('text', 'varchar', 'bpchar', 'citext')
        """,
        [table],
    )
    for column, collation in cursor.fetchall():
        lowered = column.lower()
        if lowered.endswith(NAME_COLUMN_SUFFIXES) and collation == "C":
            findings.append(
                Finding(
                    "C34",
                    table,
                    f'{column} holds a name but uses COLLATE "C": byte order sorts '
                    f"'Zaharia' before 'Șerban', so a plain Romanian list comes out "
                    f"alphabetically wrong -- today, with no Russian-speaking client",
                )
            )
        if lowered.endswith(CODE_COLUMN_SUFFIXES) and collation != "C":
            findings.append(
                Finding(
                    "C34",
                    table,
                    f'{column} holds a code but has no explicit COLLATE "C" '
                    f"(inherits {collation or 'the database default'}): codes ordered "
                    f"linguistically produce reports in a strange order whose cause is "
                    f"then looked for in the report",
                )
            )
    return findings


def _audit_exception_list(cursor: Any, contract: Contract, existing: set[str]) -> list[Finding]:
    """IZ-76 -- the contract claims an exception the table does not need."""
    findings: list[Finding] = []
    for name, declaration in contract.tables.items():
        if name not in existing or declaration.get("tenant_column", True):
            continue
        cursor.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=%s AND column_name='tenant_id'",
            [name],
        )
        if cursor.fetchone() is not None:
            findings.append(
                Finding(
                    "IZ-76",
                    name,
                    "declared as having no tenant column, but it has tenant_id. "
                    "A contract that drifted from the schema is worse than no "
                    "contract: it grants an exception nobody needs any more",
                )
            )
    return findings


def _audit_append_only(cursor: Any, contract: Contract) -> list[Finding]:
    """IZ-77 -- R21 and R22."""
    findings: list[Finding] = []
    for name, declaration in contract.append_only.items():
        cursor.execute("SELECT to_regclass(%s)", [f"public.{name}"])
        if cursor.fetchone()[0] is None:
            continue  # not built yet; the phase column says when

        cursor.execute(
            """
            SELECT con.conname, src.relname
              FROM pg_constraint con
              JOIN pg_class tgt ON tgt.oid = con.confrelid
              JOIN pg_class src ON src.oid = con.conrelid
             WHERE con.contype = 'f' AND tgt.relname = %s
            """,
            [name],
        )
        for constraint, source in cursor.fetchall():
            findings.append(
                Finding(
                    "IZ-77",
                    name,
                    f"foreign key {constraint!r} from {source} points at it. Links are "
                    f"made in the opposite direction: a table with ten incoming keys "
                    f"is not repartitioned, it is redesigned",
                )
            )

        column = declaration["partition_column"]
        cursor.execute(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=%s AND column_name=%s",
            [name, column],
        )
        row = cursor.fetchone()
        if row is None:
            findings.append(Finding("IZ-77", name, f"partition column {column!r} is missing"))
        elif row[0] == "YES":
            findings.append(Finding("IZ-77", name, f"partition column {column!r} is nullable"))
    return findings
