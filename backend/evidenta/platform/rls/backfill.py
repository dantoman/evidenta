"""One door for data written by a migration -- `OD-94`.

Three failures produced this, all on the same afternoon and all silent:

1. A backfill queried through the ``default`` alias while its migration held
   ``ACCESS EXCLUSIVE`` on the ``migration`` alias. Two connections, one lock, no
   error and no timeout -- it simply hung.
2. The next one ran as ``evidenta_owner``, which under ``FORCE ROW LEVEL
   SECURITY`` sees **zero rows** on a table whose policies name other roles. The
   loop iterated nothing, saved nothing, and **reported success**; the constraint
   added later in the same migration is the only reason anybody found out.
3. It split rows by key prefix, which would have mislabelled a future row.

The first is prevented by taking the connection from the schema editor and never
opening another. The second and third are what the two checks below are for.

**Why a probe rather than a declaration.** An earlier draft of this rule had the
migration *declare* the role it runs under. A declaration is a value you trust.
This measures instead: it counts what the current role sees, counts again with
the row filter suspended, and compares. Two numbers that both exist, which is the
difference between a check and an assertion (ADR-070 §1).

**Why the cardinality is passed in.** "It touched zero rows" and "there were zero
rows to touch" are the same observation, and a loop that cannot distinguish them
can never fail on the case it exists for. ``expected`` makes the caller say which
one it means -- including ``expected=0``, which is a claim like any other.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class BackfillError(RuntimeError):
    """A backfill did not do what it said it would."""


@dataclass(frozen=True, slots=True)
class Probe:
    """What the role saw, and what was actually there."""

    seen_by_role: int
    actually_there: int

    @property
    def role_is_blind(self) -> bool:
        return self.seen_by_role != self.actually_there


def _count(cursor: Any, table: str) -> int:
    cursor.execute(f'SELECT count(*) FROM "{table}"')
    row = cursor.fetchone()
    return int(row[0])


def _force(cursor: Any, table: str, on: bool) -> None:
    clause = "FORCE" if on else "NO FORCE"
    cursor.execute(f'ALTER TABLE "{table}" {clause} ROW LEVEL SECURITY')


def backfill(
    schema_editor: Any,
    table: str,
    *,
    expected: int,
    statements: str,
    reason: str,
) -> Probe:
    """Run ``statements`` against ``table``, having proved they can be seen.

    ``expected`` is the number of rows the statements are meant to change, as the
    caller understands the table. It is checked against what is actually there
    before anything is written, so a migration whose premise is wrong fails
    before it changes data rather than after.

    Returns the :class:`Probe` so a caller can record what the role could see.
    Suspending the row filter is contained: it happens inside the migration's own
    transaction, so it rolls back with everything else and the table leaves as it
    entered (`OD-94`, the default form; the permanent policy is the exception and
    needs its own reason and register row).
    """
    if not reason.strip():
        raise BackfillError("a backfill states why it suspends the row filter")

    connection = schema_editor.connection
    with connection.cursor() as cursor:
        seen = _count(cursor, table)
        _force(cursor, table, on=False)
        try:
            actually = _count(cursor, table)
            probe = Probe(seen_by_role=seen, actually_there=actually)

            if actually != expected:
                raise BackfillError(
                    f"{table}: expected {expected} rows, the table holds {actually}. "
                    f"A backfill states its cardinality so that 'touched nothing' and "
                    f"'there was nothing to touch' stop being the same result "
                    f"(OD-94). Reason given: {reason}"
                )
            cursor.execute(statements)
        finally:
            _force(cursor, table, on=True)

    return probe
