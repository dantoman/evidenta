"""Run the model guard against a **running** database, not a rebuilt one.

The suite builds its database from the migrations on every run, so it can only
ever confirm that the migrations are right. It cannot see a database that has
since drifted away from them -- and drift is not hypothetical here: a `down` that
ran without its `up` coming back left four tables with no row security at all,
and a second one left the application role holding `INSERT, UPDATE, DELETE` on
the fiscal parameter tables. Both were found by tripping over them, days apart,
by two people who were looking for something else. Nothing whispered.

So this command exists to make that noise. It is the same `audit()` the suite
runs, pointed at the connection you name, plus the one check the suite has no
reason to make: **what the application role may actually do to the tables that
are supposed to be read-only for it.** Privileges are not schema, they do not
appear in a policy, and a `GRANT` restricted in a migration revokes nothing that
was granted by default.

Runs as the owner by default (`--database=migration`), because reading
`information_schema.table_privileges` for another role and the catalogue's RLS
flags is not something the application role should be able to do at all.

Exit code is 1 when anything is found, so a `make` target fails on drift rather
than printing it into a scrollback nobody reads.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand
from django.db import connections

from evidenta.platform.rls.schema_audit import RLS_CONTRACT, Contract, audit

#: The role the product runs as. Everything below asks what *it* can do.
APP_ROLE = "evidenta_app"

#: Tables whose declaration says the application only reads them. The write path
#: is a privileged one, and a privilege left behind makes it a convention.
READ_ONLY_SHAPES = frozenset({"global_read_only"})


def _read_only_tables() -> list[str]:
    """The tables declared read-only for the application, from the one registry."""
    contract: dict[str, Any] = tomllib.loads(Path(RLS_CONTRACT).read_text(encoding="utf-8"))
    return [
        table["name"]
        for table in contract.get("table", [])
        if table.get("policy_shape") in READ_ONLY_SHAPES
    ]


class Command(BaseCommand):
    help = "Compare a live database against the RLS and append-only contracts."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--database", default="migration")

    def handle(self, *args: Any, **options: Any) -> None:
        connection = connections[options["database"]]
        problems: list[str] = []

        with connection.cursor() as cursor:
            for finding in audit(cursor, Contract()):
                problems.append(str(finding))

            tables = _read_only_tables()
            if tables:
                cursor.execute(
                    """
                    SELECT table_name, string_agg(privilege_type, ', ' ORDER BY privilege_type)
                      FROM information_schema.table_privileges
                     WHERE grantee = %s
                       AND privilege_type <> 'SELECT'
                       AND table_name = ANY(%s)
                     GROUP BY table_name
                     ORDER BY table_name
                    """,
                    [APP_ROLE, tables],
                )
                for table, privileges in cursor.fetchall():
                    problems.append(
                        f"[PRIV] {table}: {APP_ROLE} holds {privileges} on a table declared "
                        f"read-only for it. A restricted GRANT does not revoke what the role "
                        f"already had -- the REVOKE has to be explicit."
                    )

        database = connection.settings_dict["NAME"]
        if not problems:
            self.stdout.write(f"{database}: fără derivă față de contracte.")
            return

        self.stdout.write(f"{database}: {len(problems)} probleme.")
        for problem in problems:
            self.stdout.write(f"  {problem}")
        # Non-zero, so a pipeline stops. `SystemExit` rather than
        # `CommandError`: this is a report that failed, not a command that was
        # used wrongly, and the traceback would bury the list above.
        sys.exit(1)
