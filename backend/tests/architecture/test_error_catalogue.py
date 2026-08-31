"""Every error code the server sends has a message on the client -- C10.

    "Erorile au cod stabil, nu doar mesaj."

The rule was already followed on the server and quietly broken on the client. The
frontend catalogue listed `auth.mfa_required`, a name the server never sends, and
had no entry for `auth.invalid_mfa_code`, which it sends on every mistyped
second factor -- so a wrong code produced "A apărut o eroare neaşteptată". The
owner hit it on their first login, and the message sent them looking for a
failure that had not happened.

Written from imagination rather than from the source is how that happens, and a
stable code is worth nothing if the two halves of the contract are written
independently. This test joins them.

No database, no Node: it reads both files.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
#: Where user-facing refusal codes are raised. Two places, not one: the tenant
#: refusals live in the RLS middleware, which is what answers before
#: authentication ever runs -- and leaving it out was this test's own first bug,
#: reporting the client's `tenant.not_found` as invented.
SOURCES = (
    REPO / "backend/evidenta/platform/identity",
    REPO / "backend/evidenta/platform/rls/middleware.py",
)
CATALOGUE = REPO / "frontend/src/locales/ro.ts"

#: Where a refusal code is written, in the three shapes the server uses.
#:
#: A bare `(auth|tenant)\.[a-z_]+` match was the first attempt and over-matched:
#: `tenant.manage_roles` is a **permission** name, not an error, and the test
#: reported it as a message the client was missing. Matching the raising context
#: instead keeps the two vocabularies apart.
CODE = re.compile(
    r"""Error\(\s*["']((?:auth|tenant)\.[a-z_]+)["']"""
    r"""|code["']?\s*[:=]\s*["']((?:auth|tenant)\.[a-z_]+)["']"""
    r"""|["']((?:auth|tenant)\.[a-z_]+)["']\s*:\s*\d+"""
)


#: The client side is a flat map of code to message, so a key match is right
#: there -- and has to be a separate pattern, because the server's shapes and a
#: TypeScript object key have nothing in common.
CLIENT_CODE = re.compile(r"""["']((?:auth|tenant)\.[a-z_]+)["']\s*:""")


def codes_in(text: str) -> set[str]:
    return {group for match in CODE.findall(text) for group in match if group}


def server_codes() -> set[str]:
    codes: set[str] = set()
    for root in SOURCES:
        files = root.rglob("*.py") if root.is_dir() else [root]
        for source in files:
            if "migrations" in source.parts:
                continue
            codes |= codes_in(source.read_text(encoding="utf-8"))
    return codes


def errors_block(text: str) -> str:
    r"""Just the ``errors: { … }`` object of the resource file.

    Scanning the whole file was the second version of this test's own bug, and it
    is the mirror image of the first one: the server pattern had to stop matching
    `tenant.manage_roles` because that is a **permission**, and then the client
    pattern started matching it, because ADR-075 gave the interface a map of
    permission labels keyed by the same names. Two vocabularies, one shape.

    Sliced by counting braces rather than by a regex over the whole object: the
    messages contain braces of their own the day one carries an interpolation,
    and a lazy `errors:\s*{(.*?)}` would end at the first of them.
    """
    start = text.index("errors: {") + len("errors: {")
    depth = 1
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start:index]
    raise AssertionError("errors: { … } is not closed in " + str(CATALOGUE))


def client_codes() -> set[str]:
    return set(CLIENT_CODE.findall(errors_block(CATALOGUE.read_text(encoding="utf-8"))))


def test_both_files_are_where_the_test_thinks() -> None:
    """The control. Without it a moved file makes this pass over empty sets."""
    for root in SOURCES:
        assert root.exists(), root
    assert CATALOGUE.is_file(), CATALOGUE
    assert len(server_codes()) >= 5
    # And the slice actually found something: an `errors:` block renamed would
    # otherwise make both directions pass over an empty set.
    assert len(client_codes()) >= 5


@pytest.mark.parametrize("code", sorted(server_codes()))
def test_the_client_can_render_every_server_code(code: str) -> None:
    assert code in client_codes(), (
        f"the server can answer with {code!r} and frontend/src/locales/ro.ts has "
        f"no message for it, so the screen falls back to 'unexpected error' -- "
        f"which describes the wrong cause and sends the reader to check the "
        f"wrong thing."
    )


def test_the_client_invents_no_codes() -> None:
    """The direction that actually broke.

    `auth.mfa_required` sat in the catalogue for a while and matched nothing the
    server sends. An entry like that is not harmless: it reads as coverage, so
    the gap it hides never gets looked for.
    """
    invented = client_codes() - server_codes()
    assert not invented, (
        f"{sorted(invented)} appear in the client catalogue and are never sent "
        f"by the server. They read as coverage and hide the codes that are "
        f"actually missing."
    )
