"""A `.down.sql` that drops an `rls` function must do it as the owner -- ADR-043.

`C30` says `reverse_sql` is not optional. Eight committed files satisfy that in
the letter and fail in fact: they create functions under `SET LOCAL ROLE
evidenta_rls` and drop them as `evidenta_owner`, which is `NOINHERIT` -- so
membership of `evidenta_rls` grants nothing without `SET ROLE`, and the DROP dies
with "must be owner of function". Confirmed by running `migrate ledger zero`, not
by reading.

Nothing could have caught it. Reverse migrations are never exercised: the test
harness builds forward from an empty database, CI does the same, and a rollback
is the thing you need on the day everything else has already gone wrong.

The eight are enumerated below rather than repaired. `C31` makes an applied SQL
file append-only, so the correction is a new file and a new migration -- a task
with an ADR behind it, not an edit. **The list may only shrink.** A file that
leaves it must have been superseded, and one that joins it should not exist: this
test refuses any *new* reverse file with the defect.

No database. It reads the tree, so it runs in the fast CI job.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

MIGRATIONS = Path(__file__).resolve().parents[3] / "infra" / "migrations"

#: Files whose DROPs run as the wrong role. Each was applied before the defect was
#: understood, and `C31` forbids editing an applied file. Removing a name here
#: means a superseding file exists -- never that this one was edited.
KNOWN_IRREVERSIBLE = frozenset(
    {
        "0014_company_access.down.sql",
        "0015_module_scope_sync.down.sql",
        "0016_subdomain_resolver.down.sql",
        "0023_flags.down.sql",
        "0028_auth_request_path.down.sql",
        "0030_notifications.down.sql",
        "0032_engagement_provisioning.down.sql",
        "0036_ledger.down.sql",
    }
)

DROPS_RLS_FUNCTION = re.compile(r"DROP\s+FUNCTION[^;]*?\brls\.", re.IGNORECASE | re.DOTALL)
SETS_ROLE = re.compile(r"SET\s+LOCAL\s+ROLE\s+evidenta_rls", re.IGNORECASE)


def offenders() -> set[str]:
    found = set()
    for path in sorted(MIGRATIONS.glob("*.down.sql")):
        text = path.read_text()
        if DROPS_RLS_FUNCTION.search(text) and not SETS_ROLE.search(text):
            found.add(path.name)
    return found


def test_no_new_reverse_file_drops_an_rls_function_as_the_owner() -> None:
    """The guard proper: the defect may not spread.

    A reverse file that does not roll back is worse than a missing one -- the
    missing one is refused at review, this one passes and waits.
    """
    new = offenders() - KNOWN_IRREVERSIBLE
    assert new == set(), (
        f"{sorted(new)} drop a function in schema `rls` without `SET LOCAL ROLE "
        f"evidenta_rls`. `evidenta_owner` is NOINHERIT, so the DROP fails with "
        f'"must be owner of function" and the migration cannot be rolled back.'
    )


def test_the_known_list_does_not_outlive_its_files() -> None:
    """A list that keeps a name after the file stops offending is the same rot as
    a blocker nobody clears: it grows in one direction and stops meaning anything.
    """
    stale = KNOWN_IRREVERSIBLE - offenders()
    assert stale == set(), (
        f"{sorted(stale)} no longer drop an `rls` function unguarded -- remove "
        f"them from KNOWN_IRREVERSIBLE in the same change that fixed them."
    )


def test_every_forward_file_has_a_reverse() -> None:
    """C30, stated where it can fail rather than only in CLAUDE.md."""
    missing = [
        path.name
        for path in sorted(MIGRATIONS.glob("*.up.sql"))
        if not path.with_name(path.name.replace(".up.sql", ".down.sql")).exists()
    ]
    assert missing == [], f"no reverse file for: {missing}"


@pytest.mark.parametrize("name", sorted(KNOWN_IRREVERSIBLE))
def test_the_known_files_are_still_there(name: str) -> None:
    """`C31`: an applied SQL file is never deleted or renamed. If one of these
    vanishes, the exception list is describing a tree that no longer exists."""
    assert (MIGRATIONS / name).is_file()


# --- the two guards that stop the class recurring -----------------------------


DECLARATIONS = frozenset({"reversible-tested", "irreversible"})

#: Tables where getting reversibility wrong is not an inconvenience. A reverse
#: that silently half-succeeds here leaves posted accounting behind a policy that
#: is no longer attached -- and `R10` means there is no UPDATE to repair it with.
LEDGER_TABLES = ("journal_entry", "journal_line", "period")

RUN_SQL_FILE = re.compile(r'run_sql_file\(\s*\n?\s*"([^"]+)"')
DOWN_NAME = re.compile(r'down_name="([^"]+)"')

BACKEND = Path(__file__).resolve().parents[2] / "evidenta"


def migration_modules() -> list[Path]:
    return sorted(BACKEND.rglob("migrations/0*.py"))


def sql_names(text: str) -> list[str]:
    return RUN_SQL_FILE.findall(text)


def test_every_declared_reverse_name_has_its_file() -> None:
    """The naming convention needs its own guard.

    A typo in `down_name` surfaces only when somebody actually rolls back --
    which is the worst possible moment, because a rollback is what you reach for
    when everything else has already gone wrong. `run_sql_file` raises at import
    for a missing file, but only for the migrations Django loads; this checks
    every one of them at once, without a database.
    """
    missing = []
    for module in migration_modules():
        for name in DOWN_NAME.findall(module.read_text()):
            if not (MIGRATIONS / f"{name}.down.sql").is_file():
                missing.append(f"{module.name} -> {name}.down.sql")
    assert missing == [], f"declared reverse files that do not exist: {missing}"


def test_declared_reverses_are_the_ones_actually_round_tripped() -> None:
    """A label is worth what verifies it.

    Importing the round-trip list rather than repeating it: two lists of pairs
    that drift apart would let a migration claim a tested reverse that nothing
    runs -- which is the same defect as the one this whole task is about, wearing
    a different hat.
    """
    from tests.schema_guard.test_reverse_sql import PAIRS

    tested = {forward for forward, _ in PAIRS}
    claimed = set()
    for module in migration_modules():
        text = module.read_text()
        if 'REVERSIBILITY = "reversible-tested"' in text:
            claimed.update(sql_names(text))

    untested = sorted(claimed - tested)
    assert untested == [], (
        f"declared `reversible-tested` but not in the round-trip list: {untested}"
    )


def test_a_migration_touching_the_ledger_declares_which_it_is() -> None:
    """No silent middle -- the rule the owner asked for.

    Reversibility is a property somebody has to have thought about, and the two
    honest answers are both acceptable. What is not acceptable is neither: a
    migration that says nothing leaves the next person to guess, and the guess
    that costs is "it will probably roll back fine".
    """
    undeclared = []
    for module in migration_modules():
        text = module.read_text()
        touches = any(
            re.search(rf"\b{table}\b", (MIGRATIONS / f"{name}.up.sql").read_text())
            for name in sql_names(text)
            if (MIGRATIONS / f"{name}.up.sql").is_file()
            for table in LEDGER_TABLES
        )
        if not touches:
            continue
        declared = re.search(r'REVERSIBILITY = "([^"]+)"', text)
        if declared is None or declared.group(1) not in DECLARATIONS:
            undeclared.append(str(module.relative_to(BACKEND.parent)))

    assert undeclared == [], (
        f"these touch {', '.join(LEDGER_TABLES)} and declare no REVERSIBILITY: "
        f"{undeclared}. Say `reversible-tested` (and add the round trip) or "
        f"`irreversible` (and let Django raise). Never neither, never a noop."
    )
