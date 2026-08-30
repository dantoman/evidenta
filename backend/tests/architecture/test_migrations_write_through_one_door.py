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

#: Migrations that wrote data before the door existed. **Not a list of migrations
#: to fix** -- nothing applied and committed gets rewritten (`OD-98`). Each is a
#: *state* whose correctness is asserted separately and permanently, which is why
#: the list is expected to stay short rather than to empty.
BEFORE_THE_DOOR = {
    "0007_margin_is_sourced.py": "fiscal_parameters/0007 predates the helper: its backfill ran as "
    "the owner with the row filter suspended and counted nothing. The state it was supposed to "
    "leave -- no margin without a source, no absent margin without a reason, and the moved dates "
    "kept rather than dropped -- is asserted in tests/isolation/test_pre_door_migration_state.py "
    "(OD-98).",
    "0003_roles.py": "platform/identity/0003_roles syncs the permission catalogue through "
    "`update_or_create` and counts nothing. Found by this guard, not by the hand-written scan that "
    "preceded it. The state -- the table equals PERMISSIONS, key for key and scope for scope -- is "
    "asserted in tests/isolation/test_pre_door_migration_state.py (OD-98).",
}


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


def test_a_migration_that_writes_data_goes_through_the_helper() -> None:
    """The door is the point; enforcing rules behind an optional door is advice."""
    offenders = []
    for path in _migrations():
        source = path.read_text(encoding="utf-8")
        if path.name in BEFORE_THE_DOOR:
            continue
        if _writes_data(ast.parse(source), source) and "backfill(" not in source:
            offenders.append(str(path.relative_to(BACKEND)))

    assert offenders == [], (
        "These migrations write data without going through "
        "`evidenta.platform.rls.backfill.backfill`:\n  "
        + "\n  ".join(offenders)
        + "\n\nThe helper states the expected cardinality and measures what the role "
        "can see. Behind an optional door it enforces neither (OD-94)."
    )


def test_the_pre_door_list_names_a_real_migration_and_a_reason() -> None:
    """An allowlist whose entries have drifted asserts the opposite of its purpose."""
    names = {p.name for p in _migrations()}
    stale = sorted(n for n in BEFORE_THE_DOOR if n not in names)
    assert stale == [], f"BEFORE_THE_DOOR names migrations that no longer exist: {stale}"
    silent = sorted(n for n, why in BEFORE_THE_DOOR.items() if not why.strip())
    assert silent == [], f"these have no reason recorded: {silent}"


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
        if path.name in BEFORE_THE_DOOR or path.name in WRITES_WITHOUT_A_CONSTRAINT:
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
