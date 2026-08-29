"""The model guard -- what the live schema must look like, checked against it.

Suite 1 catches today's bug. This one catches the table someone adds in three
years without knowing the rule, which is why it is the more valuable of the two
in the long run.

**It lives in the product, not in the test suite, because it has two callers and
only one of them is a test.** The other is `manage.py check_schema_drift`, which
points it at a *running* database. That distinction is the whole reason it moved:
the suite builds its database from the migrations every time, so by construction
it can only ever confirm that the migrations are right -- never that the database
somebody is actually using still matches them. Two sessions found four tables
with no row security and an application role holding write privileges on fiscal
parameters, days apart, both by tripping over them. `audit()` takes a cursor and
has always been able to answer for any connection; nothing here needed to change
except where it sits.

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

# `backend/evidenta/platform/rls/schema_audit.py` -> repository root. Five levels,
# and it is a constant that breaks silently if the file moves: the contracts
# would simply not be found, and a guard that reads no contract reports nothing
# wrong. `Contract.__init__` raises on a missing file for that reason.
REPO_ROOT = Path(__file__).resolve().parents[4]
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

    def shape_of(self, table: str) -> str | None:
        declaration = self.declaration_for(table)
        return None if declaration is None else str(declaration.get("policy_shape") or "")

    def writer_role_for(self, table: str) -> str | None:
        """The one role allowed to write a global table, or None (ADR-049)."""
        declaration = self.declaration_for(table)
        if declaration is None:
            return None
        role = declaration.get("writer_role")
        return None if role is None else str(role)

    def writer_roles(self) -> set[str]:
        return {
            str(d["writer_role"])
            for d in [*self.tables.values(), *self.patterns]
            if d.get("writer_role")
        }


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
        findings.extend(_audit_writer(cursor, contract, name, policies))

    findings.extend(_audit_exception_list(cursor, contract, {t[0] for t in tables}))
    findings.extend(_audit_append_only(cursor, contract))
    findings.extend(_audit_writer_sweep(cursor, contract))
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


# Shapes whose writes belong to exactly one declared role (ADR-049). The first
# admits the application role to read; the second admits it to nothing.
_WRITER_SHAPES = ("global_read_only", "platform_log")
_WRITE_COMMANDS = ("*", "a", "w", "d")
_WRITE_PRIVILEGES = ("INSERT", "UPDATE", "DELETE")


def _role_privileges(cursor: Any, table: str, role: str) -> set[str]:
    """What `role` may do to `table`, asked of the catalogue.

    `has_table_privilege` answers for the role itself and for what it inherits;
    both matter, and both are what a row actually gets checked against.
    """
    cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [role])
    if cursor.fetchone() is None:
        return set()
    cursor.execute(
        """
        SELECT p.privilege
          FROM unnest(ARRAY['SELECT', 'INSERT', 'UPDATE', 'DELETE']) AS p(privilege)
         WHERE has_table_privilege(%s, quote_ident(%s), p.privilege)
        """,
        [role, table],
    )
    return {row[0] for row in cursor.fetchall()}


def _policy_roles(cursor: Any, table: str) -> list[tuple[str, str, list[str]]]:
    cursor.execute(
        """
        SELECT p.polname, p.polcmd,
               COALESCE(array_agg(r.rolname) FILTER (WHERE r.rolname IS NOT NULL), '{}')
          FROM pg_policy p
          JOIN pg_class c ON c.oid = p.polrelid
          LEFT JOIN pg_roles r ON r.oid = ANY(p.polroles)
         WHERE c.relname = %s
         GROUP BY p.polname, p.polcmd
        """,
        [table],
    )
    return [(name, command, list(roles)) for name, command, roles in cursor.fetchall()]


def _audit_writer(
    cursor: Any, contract: Contract, table: str, policies: list[tuple[str, str, bool]]
) -> list[Finding]:
    """IZ-78 -- a global table is written by its declared role and by nobody else.

    Two things are checked, and the first is the one that was found by hand
    twice before this rule existed: the *privilege*. `0001_roles.sql` grants the
    application role INSERT/UPDATE/DELETE on every table the owner creates, so a
    global table is read-only for the application only if somebody remembered
    the REVOKE (`0047` is the migration that remembered late). The second is the
    *policy*: a write policy for any role other than the declared writer is a
    second door, which is what `OD-67` refused ("două mecanisme ușor diferite").
    """
    shape = contract.shape_of(table)
    if shape not in _WRITER_SHAPES:
        return []
    findings: list[Finding] = []
    writer = contract.writer_role_for(table)

    app = _role_privileges(cursor, table, "evidenta_app")
    forbidden = app & set(_WRITE_PRIVILEGES) if shape == "global_read_only" else app
    if forbidden:
        findings.append(
            Finding(
                "IZ-78",
                table,
                f"evidenta_app holds {sorted(forbidden)} on a {shape} table. The default "
                f"privileges from 0001_roles.sql grant writes on every owner-created "
                f"table; a global table needs the explicit REVOKE (OD-47, ADR-049)",
            )
        )

    for policy_name, command, roles in _policy_roles(cursor, table):
        if command not in _WRITE_COMMANDS:
            continue
        # `polroles = {0}` is PUBLIC, which comes back as no role name at all.
        strangers = [r for r in roles if r != writer] if roles else ["PUBLIC"]
        if strangers:
            findings.append(
                Finding(
                    "IZ-78",
                    table,
                    f"write policy {policy_name!r} admits {strangers}, and the contract "
                    f"names {writer or 'no role'} as the writer. A second door to a "
                    f"reference table is a second mechanism (OD-67); declare it as "
                    f"writer_role or drop it",
                )
            )

    if writer is not None:
        privileges = _role_privileges(cursor, table, writer)
        owns_it = _owns(cursor, table, writer)
        if "INSERT" not in privileges:
            findings.append(
                Finding(
                    "IZ-78",
                    table,
                    f"{writer} is declared as the writer but holds no INSERT privilege: "
                    f"the declaration promises a write path that does not exist",
                )
            )
        # The owner holds every privilege by owning the table; the check is about
        # a *granted* DELETE, which is what a loading role would have to be given.
        if "DELETE" in privileges and not owns_it:
            findings.append(
                Finding(
                    "IZ-78",
                    table,
                    f"{writer} may DELETE from a reference table. Reference data is "
                    f"versioned, never deleted: a parameter a stamp points at (ADR-047) "
                    f"or a template account a company copied cannot disappear",
                )
            )
    return findings


def _owns(cursor: Any, table: str, role: str) -> bool:
    cursor.execute(
        """
        SELECT 1 FROM pg_class c JOIN pg_roles o ON o.oid = c.relowner
         WHERE c.relname = %s AND o.rolname = %s
        """,
        [table, role],
    )
    return cursor.fetchone() is not None


def _audit_writer_sweep(cursor: Any, contract: Contract) -> list[Finding]:
    """IZ-78, the other direction -- the writer role touches nothing undeclared.

    The per-table check proves each reference table has exactly its writer. This
    proves the writer has exactly its reference tables: a privilege on `company`
    or a policy on `journal_entry` for `evidenta_refdata` would turn a narrow
    loading role into a second application role, and nothing on the table side
    would notice, because those tables are not global.

    Only roles that own nothing are swept. `evidenta_owner` may be declared as
    the writer of a catalogue a migration seeds (`permission`), and it holds
    every privilege on every table by owning them -- that is what it is for, and
    the isolation suite (T1) is what keeps it from being used at runtime.
    """
    findings: list[Finding] = []
    for role in sorted(contract.writer_roles()):
        cursor.execute(
            """
            SELECT count(*) FROM pg_class c JOIN pg_roles o ON o.oid = c.relowner
             WHERE o.rolname = %s AND c.relkind IN ('r', 'p')
            """,
            [role],
        )
        row = cursor.fetchone()
        if row is None or row[0] > 0:
            continue
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [role])
        if cursor.fetchone() is None:
            continue
        cursor.execute(
            """
            SELECT c.relname
              FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
               AND (has_table_privilege(%s, c.oid, 'SELECT')
                    OR has_table_privilege(%s, c.oid, 'INSERT')
                    OR has_table_privilege(%s, c.oid, 'UPDATE')
                    OR has_table_privilege(%s, c.oid, 'DELETE'))
            """,
            [role, role, role, role],
        )
        for (table,) in cursor.fetchall():
            if contract.is_system(table) or contract.writer_role_for(table) == role:
                continue
            findings.append(
                Finding(
                    "IZ-78",
                    table,
                    f"{role} holds a privilege here and is not its declared writer. "
                    f"The loading role reaches reference tables and nothing else "
                    f"(ADR-049); a privilege on a tenant table makes it a second "
                    f"application role",
                )
            )
        cursor.execute(
            """
            SELECT c.relname, p.polname
              FROM pg_policy p
              JOIN pg_class c ON c.oid = p.polrelid
              JOIN pg_roles r ON r.oid = ANY(p.polroles)
             WHERE r.rolname = %s
            """,
            [role],
        )
        for table, policy_name in cursor.fetchall():
            if contract.writer_role_for(table) == role:
                continue
            findings.append(
                Finding(
                    "IZ-78",
                    table,
                    f"policy {policy_name!r} names {role}, which is not this table's "
                    f"declared writer (ADR-049)",
                )
            )
    return findings
