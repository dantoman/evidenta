"""Data written by a migration goes through the helper -- `OD-94`, `P0`.

The helper enforces the cardinality claim and the role probe. Enforcing them
*in the helper* is worth nothing while the helper is optional: a migration can
say ``RunSQL("UPDATE …")`` and skip both. **An optional helper is advice with
extra steps** -- the same shape as a memory that was written as guidance and
therefore read as guidance, and then failed to prevent the thing three times in
one session.

**Detection is exact rather than heuristic, and that is deliberate.** The file is
parsed, not grepped: only strings actually handed to ``RunSQL`` are read as SQL,
and only functions actually handed to ``RunPython`` are read as code. A docstring
that discusses "the UPDATEs" is prose and stays prose -- which matters, because
this repository's migrations explain themselves at length and a grep would drown
in them.

**Two rules, one door**, and the second is the reason `P2` could be written at
all: once data reaches the table only through ``backfill()``, "this migration
writes data" stops being a judgement call and becomes a fact about the call
graph.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
DML = re.compile(r"\b(INSERT\s+INTO|UPDATE\s+[\"\w]+\s+SET|DELETE\s+FROM)\b", re.I | re.S)
ORM_WRITE = re.compile(
    r"\.(save|create|bulk_create|update|delete|get_or_create|update_or_create)\b"
)

#: Where the permanent assertions live. A member of the generated set below has
#: to be named here, or the state it produced is claimed by nobody.
STATE_ASSERTIONS = BACKEND / "tests" / "isolation" / "test_pre_door_migration_state.py"


def _migrations() -> list[Path]:
    return sorted(p for p in BACKEND.glob("evidenta/**/migrations/*.py") if p.name != "__init__.py")


def _writes_data(tree: ast.AST, source: str) -> bool:
    """True when this migration actually hands a write to Django, not when it mentions one."""
    functions = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    constants = {
        target.id: node.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
        for target in node.targets
        if isinstance(target, ast.Name) and isinstance(node.value.value, str)
    }

    for call in (n for n in ast.walk(tree) if isinstance(n, ast.Call)):
        name = getattr(call.func, "attr", None)
        if name == "RunSQL":
            for arg in call.args:
                text = (
                    arg.value
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                    else constants.get(getattr(arg, "id", ""), "")
                )
                if text and DML.search(text):
                    return True
        elif name == "RunPython":
            for arg in call.args:
                target = functions.get(getattr(arg, "id", ""))
                if target is not None and ORM_WRITE.search(ast.unparse(target)):
                    return True
    return False


def unproven_state() -> dict[str, str]:
    """Migrations that write data outside the door -- **generated, never listed**.

    `OD-99`. Four times in two days a hand-written enumeration came back
    incomplete and a mechanical one found the rest: annex 3's identifiers, the
    citation inventory's three holes, HG 697/2014, and the second migration this
    very guard found after a grep had missed it. So the set a rule applies to is
    enumerated by the mechanism that enforces the rule.

    A maintained list drifts. A generated one cannot -- and the difference is not
    tidiness: every one of those four was a list somebody believed was complete.
    """
    found: dict[str, str] = {}
    for path in _migrations():
        source = path.read_text(encoding="utf-8")
        if _writes_data(ast.parse(source), source) and "backfill(" not in source:
            found[path.name] = str(path.relative_to(BACKEND))
    return found


def test_whatever_writes_outside_the_door_has_a_permanent_state_assertion() -> None:
    """The door's escape hatch costs a test, not a line in a list.

    An allowlist entry is a name somebody typed; it silences the alarm and proves
    nothing about the rows. An assertion about the resulting **state** runs on
    every build, and the state is the fact -- the migration is only the means
    (`OD-98`).

    So membership is generated, and each member has to be claimed by name in the
    assertions file. Adding a new direct write is still possible; it is just not
    free, and what it costs is the thing that would have caught it.
    """
    assertions = STATE_ASSERTIONS.read_text(encoding="utf-8")
    uncovered = sorted(
        f"{name} ({where})"
        for name, where in unproven_state().items()
        if name.split("_", 1)[0] not in assertions and name.removesuffix(".py") not in assertions
    )
    assert uncovered == [], (
        "These write data outside `backfill()` and no permanent assertion claims "
        "the state they produced:\n  "
        + "\n  ".join(uncovered)
        + f"\n\nEither route the write through the door, or assert the resulting state "
        f"in {STATE_ASSERTIONS.name}. A name in a list silences the alarm; an "
        f"assertion about the rows is what would have caught the failure."
    )


#: A migration that writes data and adds no constraint, with the reason it does
#: not. Same shape as `BEFORE_THE_DOOR`: an entry is a judgement somebody made,
#: not an alarm somebody silenced.
WRITES_WITHOUT_A_CONSTRAINT: dict[str, str] = {}


def _adds_a_constraint(tree: ast.AST) -> bool:
    for call in (n for n in ast.walk(tree) if isinstance(n, ast.Call)):
        if getattr(call.func, "attr", None) in {"AddConstraint", "AddIndex"}:
            return True
    return False


def test_a_migration_that_writes_data_also_constrains_it() -> None:
    """`OD-94` rule (c), and it is an exact test now rather than a heuristic one.

    **The estimate that said otherwise had expired before it was written down.**
    The previous session recorded that a guard here would have to guess what
    "writes data" means in an arbitrary migration, and that a heuristic guard on a
    rare rule gets switched off. That was true of the world before the helper --
    and the helper landed in the same commit as the estimate. After one door,
    "this migration writes data" is a fact about the call graph, and the guess
    disappears.

    **Why the rule matters more than it looks.** In `fiscal_parameters/0007` the
    constraint is the only reason anybody discovered the backfill had written
    nothing: it failed on rows the backfill was supposed to have fixed. Split
    across two migrations, the first would have gone green. That was ordering
    luck, and this makes it ordering design.
    """
    offenders = []
    for path in _migrations():
        source = path.read_text(encoding="utf-8")
        if path.name in WRITES_WITHOUT_A_CONSTRAINT:
            continue
        tree = ast.parse(source)
        if "backfill(" in source and not _adds_a_constraint(tree):
            offenders.append(str(path.relative_to(BACKEND)))

    assert offenders == [], (
        "These write data and add nothing that would notice if the write were "
        "wrong:\n  "
        + "\n  ".join(offenders)
        + "\n\nPut the constraint in the same migration, after the write, or record "
        "the migration in WRITES_WITHOUT_A_CONSTRAINT with the reason. A backfill "
        "verified by a constraint in a later migration is verified by nothing: the "
        "first one goes green either way (OD-94 rule c)."
    )
