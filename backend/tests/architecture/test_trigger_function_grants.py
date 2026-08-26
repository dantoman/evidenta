"""A trigger on a fresh `rls` function needs a grant nobody expects -- ADR-043 section 4.1.

`CREATE TRIGGER` checks `EXECUTE` on the function **at creation**, not when the
trigger fires, and the statement is issued as the table's owner: `evidenta_owner`,
which is `NOINHERIT` and inherits nothing from `evidenta_rls`. Every migration up
to `0041` worked because PUBLIC held `EXECUTE` implicitly. `0041` revoked it --
correctly -- and took away the support the pattern had been standing on without
anybody noticing it was there.

The failure is loud but mute: "permission denied for function", which says nothing
about `NOINHERIT` and gives the reader no reason to suspect an ADR exists. So the
check lives here and the *message* carries the reference.

Reads the files rather than the catalogue, deliberately: this must fail before
`make migrate`, not during it.
"""

from __future__ import annotations

import re

from evidenta.platform.rls.sql import SQL_ROOT

#: `CREATE TRIGGER ... EXECUTE FUNCTION rls.<name>(`
TRIGGER_USES = re.compile(
    r"CREATE\s+TRIGGER\b.*?EXECUTE\s+(?:PROCEDURE|FUNCTION)\s+rls\.(\w+)\s*\(",
    re.IGNORECASE | re.DOTALL,
)


def creates(body: str, name: str) -> bool:
    return bool(
        re.search(rf"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+rls\.{name}\s*\(", body, re.IGNORECASE)
    )


def grants_to_owner(body: str, name: str) -> bool:
    """A grant that is *emitted under* `evidenta_rls`, which is the whole point.

    A `GRANT` from a role that does not own the function is a WARNING, not an
    error -- section 2 of the same ADR. Checking that the statement exists is not
    enough; it has to sit after a `SET LOCAL ROLE evidenta_rls` and before the
    `RESET ROLE` that follows it.
    """
    pattern = re.compile(
        rf"GRANT\s+EXECUTE\s+ON\s+FUNCTION\s+rls\.{name}\s*\([^)]*\)\s*TO\s+evidenta_owner",
        re.IGNORECASE,
    )
    for match in pattern.finditer(body):
        before = body[: match.start()]
        set_role = before.upper().rfind("SET LOCAL ROLE EVIDENTA_RLS")
        if set_role == -1:
            continue
        if before.upper().rfind("RESET ROLE") < set_role:
            return True
    return False


def strip_comments(body: str) -> str:
    return "\n".join(line for line in body.splitlines() if not line.lstrip().startswith("--"))


#: `0041_rls_function_privileges` is where PUBLIC lost `EXECUTE`. Everything
#: numbered below it ran while PUBLIC still held it -- and still does on a rebuild
#: from scratch, because migrations apply in order. Ten such triggers exist and
#: are correct; the rule starts where the ground changed, not before it.
REVOKE_MIGRATION = 41


def number_of(name: str) -> int:
    return int(name.split("_", 1)[0])


def test_a_trigger_on_an_rls_function_grants_execute_to_the_owner() -> None:
    offenders: list[str] = []

    for path in sorted(SQL_ROOT.glob("*.up.sql")):
        if number_of(path.name) <= REVOKE_MIGRATION:
            continue
        body = strip_comments(path.read_text())
        for name in sorted(set(TRIGGER_USES.findall(body))):
            # Not only functions this file creates. A trigger attached to a
            # function an older migration made carries the same defect, and that
            # one is harder to see: the function looks established.
            if not grants_to_owner(body, name):
                offenders.append(f"{path.name}: rls.{name}()")

    assert offenders == [], (
        "These migrations create an `rls` function and attach a trigger to it "
        "without granting EXECUTE to `evidenta_owner`:\n  " + "\n  ".join(offenders) + "\n\n"
        "They will fail at apply time with 'permission denied for function'.\n"
        "`CREATE TRIGGER` checks EXECUTE at creation and is issued as the table "
        "owner -- `evidenta_owner` -- which is NOINHERIT and inherits nothing "
        "from `evidenta_rls`. Until 0041, PUBLIC held EXECUTE implicitly and the "
        "pattern worked by accident.\n\n"
        "Add this, emitted **under** `SET LOCAL ROLE evidenta_rls` so it takes "
        "effect (a GRANT from a non-owner is a WARNING, not an error):\n"
        "    GRANT EXECUTE ON FUNCTION rls.<f>() TO evidenta_owner;\n\n"
        "The reasoning is ADR-043 section 4.1 "
        "(docs/decisions/043-privilegiile-functiilor-rls.md)."
    )


def test_the_check_can_see_a_missing_grant() -> None:
    """A guard that matches nothing reports success, which is the failure mode.

    The three helpers are exercised on a file that is exactly the defect, so the
    assertion above cannot be quietly passing because a regex stopped matching.
    """
    defective = """
        SET LOCAL ROLE evidenta_rls;
        CREATE OR REPLACE FUNCTION rls.refuse_something() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'no'; END; $$;
        RESET ROLE;
        CREATE TRIGGER something_append_only BEFORE UPDATE ON something
            FOR EACH ROW EXECUTE FUNCTION rls.refuse_something();
    """
    assert TRIGGER_USES.findall(defective) == ["refuse_something"]
    assert creates(defective, "refuse_something")
    assert not grants_to_owner(defective, "refuse_something")

    repaired = defective.replace(
        "RESET ROLE;",
        "GRANT EXECUTE ON FUNCTION rls.refuse_something() TO evidenta_owner;\nRESET ROLE;",
        1,
    )
    assert grants_to_owner(repaired, "refuse_something")


def test_a_grant_outside_the_role_block_does_not_count() -> None:
    """The trap section 2 of the ADR measured, asserted here rather than trusted."""
    outside = """
        SET LOCAL ROLE evidenta_rls;
        CREATE FUNCTION rls.refuse_something() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'no'; END; $$;
        RESET ROLE;
        GRANT EXECUTE ON FUNCTION rls.refuse_something() TO evidenta_owner;
    """
    assert not grants_to_owner(outside, "refuse_something")
