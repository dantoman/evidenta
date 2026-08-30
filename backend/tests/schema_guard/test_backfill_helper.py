"""The backfill helper has to fail on the two cases it exists for -- `OD-94`.

A guard that cannot fail on its own case is not a guard, and this one guards
against exactly that: a loop that iterated nothing and reported success. So the
tests below build the failing conditions on a real table with real policies,
rather than asserting the helper's shape.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from django.db import connections

from evidenta.platform.rls.backfill import BackfillError, backfill

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

TABLE = "probe_backfill"


class _Editor:
    """The two lines of `schema_editor` this helper uses."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection


@pytest.fixture
def editor() -> Iterator[_Editor]:
    """A table under FORCE whose only policy names a role we are not.

    That is the shape that produced the silent failure: `evidenta_owner` owns the
    table, FORCE applies to owners too, and no policy names it -- so every SELECT
    returns nothing and no error.
    """
    connection = connections["migration"]
    with connection.cursor() as cursor:
        cursor.execute(
            f"CREATE TABLE {TABLE} (id serial PRIMARY KEY, marked boolean DEFAULT false)"
        )
        cursor.execute(f"INSERT INTO {TABLE} DEFAULT VALUES")
        cursor.execute(f"INSERT INTO {TABLE} DEFAULT VALUES")
        cursor.execute(f"INSERT INTO {TABLE} DEFAULT VALUES")
        cursor.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY")
        cursor.execute(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY")
        cursor.execute(
            f"CREATE POLICY {TABLE}_app ON {TABLE} FOR SELECT TO evidenta_app USING (true)"
        )
    yield _Editor(connection)


def test_the_role_probe_sees_the_blindness_that_produced_the_silent_failure(
    editor: _Editor,
) -> None:
    """Three rows exist; the role running the migration sees none of them.

    This is the measurement the first backfill did not make. Nothing errors --
    that is the whole difficulty -- so the only way to know is to count twice.
    """
    probe = backfill(
        editor,
        TABLE,
        expected=3,
        statements=f"UPDATE {TABLE} SET marked = true",
        reason="test: the role has no policy on this table",
    )
    assert probe.seen_by_role == 0
    assert probe.actually_there == 3
    assert probe.role_is_blind


def test_a_wrong_cardinality_fails_before_anything_is_written(editor: _Editor) -> None:
    """The premise is checked before the data changes, not after.

    A migration whose idea of the table is wrong should stop while the table is
    still the one it described.
    """
    with pytest.raises(BackfillError) as refused:
        backfill(
            editor,
            TABLE,
            expected=2,
            statements=f"UPDATE {TABLE} SET marked = true",
            reason="test: deliberately wrong count",
        )
    assert "expected 2" in str(refused.value)

    with editor.connection.cursor() as cursor:
        cursor.execute(f"ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY")
        cursor.execute(f"SELECT count(*) FROM {TABLE} WHERE marked")
        assert cursor.fetchone()[0] == 0, "the refusal must happen before the write"


def test_expected_zero_is_a_claim_and_is_checked(editor: _Editor) -> None:
    """`expected=0` is the case the whole helper exists for.

    "It touched nothing" and "there was nothing to touch" are the same
    observation; passing zero says which one is meant, and is wrong here.
    """
    with pytest.raises(BackfillError):
        backfill(
            editor,
            TABLE,
            expected=0,
            statements=f"UPDATE {TABLE} SET marked = true",
            reason="test: claims an empty table that is not empty",
        )


def test_the_row_filter_is_restored_even_when_the_backfill_refuses(editor: _Editor) -> None:
    """A refusal must not leave the table with its filter suspended."""
    with pytest.raises(BackfillError):
        backfill(
            editor,
            TABLE,
            expected=99,
            statements=f"UPDATE {TABLE} SET marked = true",
            reason="test: wrong on purpose",
        )
    with editor.connection.cursor() as cursor:
        cursor.execute("SELECT relforcerowsecurity FROM pg_class WHERE relname = %s", [TABLE])
        assert cursor.fetchone()[0] is True


def test_a_backfill_without_a_reason_is_refused(editor: _Editor) -> None:
    """Suspending the row filter is a thing somebody has to justify in writing."""
    with pytest.raises(BackfillError):
        backfill(editor, TABLE, expected=3, statements="SELECT 1", reason="   ")
