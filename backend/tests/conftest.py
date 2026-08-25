"""Test database harness.

The constraint this file exists to solve: ``evidenta_app`` is ``NOCREATEDB`` on
purpose, and pytest-django creates the test database through the ``default``
connection. So the default harness cannot start.

The convenient way out is to point ``default`` at ``evidenta_owner`` for tests.
It works, every suite turns green, and it proves nothing: the owner is subject to
policies only because of ``FORCE ROW LEVEL SECURITY``, and one forgotten ``FORCE``
would make the whole isolation suite pass against an unprotected table. T1 exists
to forbid exactly that shortcut.

So the harness separates the three privileges that are actually different:

  admin (superuser)   creates and drops the test database. Test infrastructure,
                      never a production credential -- which is why it comes from
                      its own environment variables and is not `evidenta_owner`
                      with CREATEDB bolted on.
  evidenta_owner      applies the bootstrap and runs migrations. Owns the tables.
  evidenta_app        runs the tests. No BYPASSRLS, owns nothing.

The bootstrap is applied by invoking ``psql``, the same way ``make bootstrap``
does in production. That is deliberate: the files use psql variables and
``\\set ON_ERROR_STOP``, and applying them any other way would mean the tests
exercise a different bootstrap path than the one that runs for real.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import psycopg
import pytest
from django.conf import settings
from django.core.management import call_command
from django.db import connections
from psycopg.conninfo import make_conninfo

from evidenta.platform.rls.context import unguarded

REPO_ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP_DIR = REPO_ROOT / "infra" / "bootstrap"

# ADR-015. The test database is created with the same collation as production:
# a suite that sorted differently from production would hide ordering bugs and
# invent ones that do not exist.
ICU_LOCALE = "ro"


def _admin_password() -> str | None:
    """The admin password, or None when it is not supplied.

    None and the empty string are different facts, and libpq treats them so: a
    password that is set but empty is sent as a password and the cluster rejects
    it, while an absent one makes libpq fall back to ``~/.pgpass``, peer or trust.
    Collapsing the two would force a credential into the environment on machines
    where it already lives in .pgpass, for no gain.
    """
    return os.environ.get("TEST_DB_ADMIN_PASSWORD") or None


def admin_dsn(dbname: str) -> str:
    """Connection string for the test admin, built by psycopg, not by hand.

    Hand-concatenating this is where the bug was: an empty password swallows the
    next token, so ``password= dbname=x`` parses as ``password='dbname=x'`` and
    dbname is never set. libpq then falls back to the user name as the database --
    silently, and when the admin user is ``postgres`` it lands on exactly the
    database you wanted, for entirely the wrong reason.

    ``make_conninfo`` quotes empty values correctly.
    """
    default = settings.DATABASES["default"]
    return make_conninfo(
        host=str(default["HOST"]),
        port=str(default["PORT"]),
        user=os.environ.get("TEST_DB_ADMIN_USER", "postgres"),
        password=_admin_password(),
        dbname=dbname,
    )


def test_database_name() -> str:
    default = settings.DATABASES["default"]
    test_settings = cast("dict[str, Any]", default.get("TEST") or {})
    configured = test_settings.get("NAME")
    return str(configured or f"test_{default['NAME']}")


def _run_bootstrap(dbname: str) -> None:
    psql = shutil.which("psql")
    if psql is None:
        pytest.exit(
            "psql is not on PATH. The bootstrap files use psql variables and "
            "\\set ON_ERROR_STOP, and the suite applies them exactly as "
            "`make bootstrap` does -- so that a broken bootstrap breaks here too, "
            "rather than only in production.",
            returncode=1,
        )

    default = settings.DATABASES["default"]
    # Each role gets its own password. Passing the application password for both
    # silently reset the owner's password to the wrong value -- invisible while
    # the two happened to be equal, which they were in every local run. CI used
    # different values and found it in the first minute.
    owner = settings.DATABASES["migration"]
    env = os.environ.copy()
    password = _admin_password()
    if password is None:
        env.pop("PGPASSWORD", None)
    else:
        env["PGPASSWORD"] = password

    for path in sorted(BOOTSTRAP_DIR.glob("0*.sql")):
        command = [
            psql,
            "--no-psqlrc",
            "--quiet",
            "-v",
            "ON_ERROR_STOP=1",
            "-v",
            f"owner_password={owner['PASSWORD']}",
            "-v",
            f"app_password={default['PASSWORD']}",
            "-h",
            str(default["HOST"]),
            "-p",
            str(default["PORT"]),
            "-U",
            os.environ.get("TEST_DB_ADMIN_USER", "postgres"),
            "-d",
            dbname,
            "-f",
            str(path),
        ]
        result = subprocess.run(command, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            pytest.exit(
                f"Bootstrap failed at {path.name}:\n{result.stderr.strip()}",
                returncode=1,
            )


@pytest.fixture(scope="session")
def django_db_setup(django_db_blocker: pytest.FixtureRequest) -> Iterator[None]:
    """Create the test database as admin, hand it to the application role."""
    dbname = test_database_name()

    with psycopg.connect(admin_dsn("postgres"), autocommit=True) as admin:
        admin.execute(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)')
        admin.execute(
            f'CREATE DATABASE "{dbname}" '
            f"LOCALE_PROVIDER icu ICU_LOCALE '{ICU_LOCALE}' TEMPLATE template0"
        )

    _run_bootstrap(dbname)

    for alias in ("default", "migration"):
        settings.DATABASES[alias]["NAME"] = dbname
        connections[alias].settings_dict["NAME"] = dbname

    # Migrations run as the owner, never as the application role (R5).
    with django_db_blocker.unblock():  # type: ignore[attr-defined]
        call_command("migrate", database="migration", run_syncdb=False, verbosity=0)

    _assert_application_role(django_db_blocker)

    yield

    for alias in ("default", "migration"):
        connections[alias].close()
    if os.environ.get("EVIDENTA_KEEP_TEST_DB") != "1":
        with psycopg.connect(admin_dsn("postgres"), autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)')


# Deliberately a function, not an autouse fixture. As autouse it ran at session
# setup, so *every* test in the repository -- including purely static ones that
# never touch a row -- depended on a reachable Postgres. That is how a static
# check ends up needing a database, and how it ends up excluded from the fast CI
# job for a reason that has nothing to do with what it checks.
#
# It still runs for every database test: django_db_setup calls it below, and
# pytest builds that fixture only when a test actually asks for the database.
def _assert_application_role(django_db_blocker: pytest.FixtureRequest) -> None:
    """Refuse to run the suite unless it runs as the application role (T1).

    Checked by querying the server, not by reading settings: settings describe
    intent, ``current_user`` describes what actually happened. A suite that
    believed its own configuration would be exactly the false assurance T1 warns
    about.
    """
    with (
        django_db_blocker.unblock(),  # type: ignore[attr-defined]
        unguarded("harness: role check"),
        connections["default"].cursor() as cursor,
    ):
        cursor.execute(
            """
            SELECT current_user,
                   rolsuper,
                   rolbypassrls,
                   (SELECT count(*) FROM pg_class c
                      JOIN pg_roles o ON o.oid = c.relowner
                     WHERE o.rolname = current_user AND c.relkind = 'r')
              FROM pg_roles WHERE rolname = current_user
            """
        )
        user, is_super, bypasses_rls, owned_tables = cursor.fetchone()

    problems = []
    if user != "evidenta_app":
        problems.append(f"connected as {user!r}, expected 'evidenta_app'")
    if is_super:
        problems.append("the role is a superuser, which bypasses every policy")
    if bypasses_rls:
        problems.append("the role has BYPASSRLS")
    if owned_tables:
        problems.append(
            f"the role owns {owned_tables} table(s); an owner is subject to policies "
            f"only while FORCE ROW LEVEL SECURITY holds"
        )

    if problems:
        pytest.exit(
            "Isolation suite refused to run:\n  - "
            + "\n  - ".join(problems)
            + "\nA suite that runs as superuser or as the table owner passes for the "
            "wrong reason and demonstrates nothing (T1, CLAUDE.md).",
            returncode=1,
        )


# --- what is guarded, and what is not ----------------------------------------
#
# The query guard refuses queries with no tenant context. pytest's own database
# bookkeeping -- creating fixtures, truncating tables after a transactional test
# -- has no tenant and legitimately never will.
#
# So the guard covers the phase that matters, the test body, and steps aside for
# setup and teardown. This is not a hole: the guard is a development aid aimed at
# accidental paths in *production* code, and the test framework is not that. A
# guard that also policed pytest's teardown would simply make transactional tests
# impossible to run, which is how a useful check gets deleted.


@pytest.hookimpl(wrapper=True)  # type: ignore[misc]
def pytest_runtest_setup(item: pytest.Item) -> Iterator[None]:
    with unguarded("pytest: fixture setup"):
        return (yield)


@pytest.hookimpl(wrapper=True)  # type: ignore[misc]
def pytest_runtest_teardown(item: pytest.Item) -> Iterator[None]:
    with unguarded("pytest: framework teardown"):
        return (yield)
