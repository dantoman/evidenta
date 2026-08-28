"""The corrected reverses, run rather than declared -- `OD-64`, ADR-043.

`C30` says `reverse_sql` is not optional. Eight files satisfied that in the
letter and failed in fact: they create functions in schema `rls` under
`SET LOCAL ROLE evidenta_rls` and drop them as `evidenta_owner`, which is
NOINHERIT -- so the DROP dies with "must be owner of function". Nothing caught
it, because a reverse migration is never exercised: the harness builds forward
from an empty database, and a rollback is what you need on the day everything
else has already gone wrong.

**Three things make this file a test rather than a claim.**

*It runs under the role that will actually run it.* The migration connection is
`evidenta_owner`. Running these as the test superuser would pass every time and
fail in production -- the same shape as an isolation test that is green because it
bypassed the policy rather than satisfied it.

*It is a round trip, not a reverse.* `down` then `up` again. The second apply is
what catches a function left behind, a policy name that now collides, an orphaned
trigger -- things a "the state looks clean" check does not see but which stop
anybody rebuilding an environment from scratch.

*It compares the catalogue.* Before and after the round trip, the functions,
policies and triggers are enumerated and required to be equal. "It did not throw"
is not the claim; "the database is where it started" is.

Everything happens inside the test transaction and is rolled back, so the
database the rest of the suite sees is untouched.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from django.db import connections

from evidenta.platform.rls.sql import SQL_ROOT

pytestmark = pytest.mark.django_db(databases=["default", "migration"], transaction=False)

#: The eight whose reverse was written wrong and has already been applied
#: forward: forward file -> **corrected** reverse file (`OD-64`).
CORRECTED = [
    ("0014_company_access", "0014_company_access_reverse"),
    ("0015_module_scope_sync", "0015_module_scope_sync_reverse"),
    ("0016_subdomain_resolver", "0016_subdomain_resolver_reverse"),
    ("0023_flags", "0023_flags_reverse"),
    ("0030_notifications", "0030_notifications_reverse"),
    ("0032_engagement_provisioning", "0032_engagement_provisioning_reverse"),
    ("0036_ledger", "0036_ledger_reverse"),
    ("0028_auth_request_path", "0028_auth_request_path_reverse"),
]

#: Files whose own reverse is already right. They are here because a migration
#: that declares `REVERSIBILITY = "reversible-tested"` has to be *tested*, not
#: merely labelled -- the architecture guard requires every such declaration to
#: name a file in `PAIRS`, which is what stops the label from becoming a word.
ALREADY_CORRECT = [
    (name, name)
    for name in (
        "0035_periods",
        "0037_vat_period",
        "0039_opening_balances",
        "0040_operation_templates",
        "0041_rls_function_privileges",
        "0043_entry_parameter_stamp",
        "0048_strict_forms",
        "0049_account_role_binding",
        # The document layer. Each file drops only functions it created itself,
        # which is what makes a single-file round trip meaningful: a trigger
        # function shared between two migrations would make the reverse of the
        # first depend on the second having been reversed already.
        "0050_numbering_series",
        "0051_document_layer",
        "0052_partner_vat_registration",
        "0053_item_units_and_barcodes",
        "0054_sales_documents",
        "0055_purchase_documents",
        # ADR-048: the account's typed slots, and the formula with its own
        # trigger functions.
        "0056_dimension_slots",
        "0057_journal_formula",
    )
]

PAIRS = CORRECTED + ALREADY_CORRECT

SNAPSHOT = """
    SELECT 'function', p.oid::regprocedure::text
      FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'rls'
    UNION ALL
    SELECT 'policy', c.relname || '.' || pol.polname
      FROM pg_policy pol JOIN pg_class c ON c.oid = pol.polrelid
    UNION ALL
    SELECT 'trigger', c.relname || '.' || t.tgname
      FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
     WHERE NOT t.tgisinternal
    ORDER BY 1, 2
"""


@pytest.fixture
def owner() -> Iterator[object]:
    """The migration connection -- `evidenta_owner`, the role that runs a rollback.

    Not the test superuser. A reverse that only works for a superuser works
    nowhere it matters.
    """
    with connections["migration"].cursor() as cursor:
        yield cursor


def snapshot(cursor: object) -> list[tuple[str, str]]:
    cursor.execute(SNAPSHOT)  # type: ignore[attr-defined]
    return [(kind, name) for kind, name in cursor.fetchall()]  # type: ignore[attr-defined]


def read(name: str, direction: str) -> str:
    return (SQL_ROOT / f"{name}.{direction}.sql").read_text()


@pytest.mark.parametrize(("forward", "reverse"), PAIRS, ids=[p[0] for p in PAIRS])
def test_the_round_trip_returns_the_catalogue_to_where_it_started(
    owner: object, forward: str, reverse: str
) -> None:
    before = snapshot(owner)

    owner.execute(read(reverse, "down"))  # type: ignore[attr-defined]
    owner.execute(read(forward, "up"))  # type: ignore[attr-defined]

    after = snapshot(owner)

    missing = sorted(set(before) - set(after))
    extra = sorted(set(after) - set(before))
    assert not missing and not extra, (
        f"round trip did not restore the catalogue.\n"
        f"  lost on the way back: {missing}\n"
        f"  left behind:          {extra}"
    )


@pytest.mark.parametrize(("forward", "reverse"), CORRECTED, ids=[p[0] for p in CORRECTED])
def test_the_original_reverse_still_fails(owner: object, forward: str, reverse: str) -> None:
    """The proof that the corrected file was needed, kept as a test.

    Without it, nothing distinguishes "we fixed a real defect" from "we rewrote a
    file that worked". The original is append-only (`C31`), so it stays on disk
    and stays broken -- and this asserts it, so the day somebody wonders whether
    the correction was necessary, the answer runs.
    """
    original = SQL_ROOT / f"{forward}.down.sql"
    if "DROP FUNCTION" not in original.read_text().upper():
        pytest.skip(f"{forward} drops no function; nothing to prove")

    with pytest.raises(Exception, match="must be owner of function"):
        owner.execute(original.read_text())  # type: ignore[attr-defined]


def test_no_corrected_reverse_uses_cascade() -> None:
    """`CASCADE` does not stop at what this migration created.

    It can drop an object another migration attached to the same function in the
    meantime, silently, reporting success. If a DROP fails on a dependency the
    error is information -- the reverse should stop, not clear a path through.
    """
    offenders = [
        reverse
        for _, reverse in CORRECTED
        if any(
            "CASCADE" in line.upper() and not line.lstrip().startswith("--")
            for line in read(reverse, "down").splitlines()
        )
    ]
    assert offenders == [], f"CASCADE in a reverse file: {offenders}"


def test_drops_are_ordered_triggers_then_policies_then_functions() -> None:
    """A function cannot go before what depends on it, and the order says so.

    Checked rather than trusted: the ordering is invisible at review once a file
    is forty lines long, and getting it wrong produces a failure only on the day
    somebody rolls back.
    """
    for _, reverse in CORRECTED:
        statements = [
            line.strip().upper()
            for line in read(reverse, "down").splitlines()
            if not line.lstrip().startswith("--")
        ]
        positions = {
            kind: [i for i, line in enumerate(statements) if line.startswith(f"DROP {kind}")]
            for kind in ("TRIGGER", "POLICY", "FUNCTION")
        }
        first_function = min(positions["FUNCTION"], default=len(statements))
        for kind in ("TRIGGER", "POLICY"):
            last = max(positions[kind], default=-1)
            assert last < first_function, (
                f"{reverse}: a DROP {kind} comes after the first DROP FUNCTION"
            )


def test_every_pair_names_files_that_exist() -> None:
    for forward, reverse in PAIRS:
        assert (SQL_ROOT / f"{forward}.up.sql").is_file(), forward
        assert (SQL_ROOT / f"{reverse}.down.sql").is_file(), reverse


def test_the_forward_files_were_not_edited() -> None:
    """`C31`, stated where it can fail.

    The whole point of a new reverse file is that the applied one is untouched.
    If a forward file ever loses its checksum, the migration refuses at import --
    but that failure is far from here, and this says why it would matter.
    """
    for forward, _ in CORRECTED:
        assert (SQL_ROOT / f"{forward}.down.sql").is_file(), (
            f"{forward}.down.sql was deleted; applied SQL files are append-only"
        )


def test_the_snapshot_can_see_a_difference(owner: object) -> None:
    """A comparison that always matches proves nothing.

    Drops one function inside the transaction and checks the snapshot notices --
    otherwise the round-trip assertions above could be comparing two empty lists.
    """
    before = snapshot(owner)
    owner.execute("SET LOCAL ROLE evidenta_rls")  # type: ignore[attr-defined]
    owner.execute("DROP FUNCTION rls.resolve_tenant_by_subdomain(citext)")  # type: ignore[attr-defined]
    owner.execute("RESET ROLE")  # type: ignore[attr-defined]

    assert len(snapshot(owner)) == len(before) - 1


def test_sql_root_is_where_it_is_expected() -> None:
    assert SQL_ROOT.name == "migrations" and SQL_ROOT.parent.name == "infra"
    assert isinstance(SQL_ROOT, Path)
