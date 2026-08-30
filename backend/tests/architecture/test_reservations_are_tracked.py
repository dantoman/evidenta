"""A reservation with a trigger is an open decision -- ADR-066.

**What this catches.** ADR-044 section 6 carried a reservation in prose: the text
of annex 1 to Law 489/1999 had not been read, the percentages came from the CNAS
order that applies it, and it was *to be confirmed before the payroll handler was
written, because that is where the distinction becomes code*. ADR-065 **is** that
handler, cites ADR-044, and dropped the reservation -- in the very table where a
point-to-rate mapping then came out wrong.

Vigilance was not the missing part: the reservation had been written and read.
What was missing is checkable -- it lived **only in one ADR's prose**, with no row
in the open-decisions register, so nothing tracked it and its loss produced no
signal.

**Deliberately self-declared**, like ``decizie de domeniu`` and ``REVERSIBILITY``.
Nothing mechanical can tell a reservation from a cautious sentence. What can be
enforced is that a declaration, once made, is tracked -- and that the next ADR
leaning on it either repeats it or closes it by name.
"""

from __future__ import annotations

import re
from pathlib import Path

DECISIONS = Path(__file__).resolve().parents[3] / "docs" / "decisions"
REGISTER = DECISIONS / "000-open-decisions.md"

#: `REZERVĂ (`OD-nn`)` opens one; `REZERVĂ ÎNCHISĂ (`OD-nn`)` closes it here.
#: The token is mandatory: a reservation without one is the failure this guards.
RESERVATION = re.compile(r"REZERV[ĂA](\s+ÎNCHIS[ĂA])?\s*\(\s*`?(OD-\d+)`?\s*\)")

#: The `- **Legate:** ...` line, where an ADR names what it leans on.
RELATED_LINE = re.compile(r"^- \*\*Legate:\*\*(.*?)(?=^- \*\*|\n## )", re.M | re.S)

#: The `- **Data:** YYYY-MM-DD` line every ADR carries.
DATE_LINE = re.compile(r"^- \*\*Data:\*\*\s*(\d{4}-\d{2}-\d{2})", re.M)

#: The ADR that adopted the rule. Read rather than repeated: the propagation
#: check binds ADRs written **from this date on**, and hard-coding the date in two
#: places is how the two drift.
RULE = DECISIONS / "066-rezerva-e-decizie-deschisa.md"


def _adrs() -> list[Path]:
    return sorted(p for p in DECISIONS.glob("[0-9][0-9][0-9]-*.md") if p.name != REGISTER.name)


def _closed_tokens() -> set[str]:
    """Tokens the register has moved to section E."""
    text = REGISTER.read_text(encoding="utf-8")
    start = text.index("## E. Închise")
    return set(re.findall(r"OD-\d+", text[start:]))


def _open_tokens() -> set[str]:
    """Every token the register mentions outside section E."""
    text = REGISTER.read_text(encoding="utf-8")
    end = text.index("## E. Închise")
    return set(re.findall(r"OD-\d+", text[:end]))


#: Fenced blocks are stripped before scanning: ADR-066 documents the marker by
#: showing it, and a document that explains a convention must not thereby become
#: bound by it -- otherwise the rule's own ADR is its first violation.
FENCE = re.compile(r"^```.*?^```", re.M | re.S)


def _reservations(text: str) -> tuple[set[str], set[str]]:
    """(open tokens declared here, tokens declared closed here)."""
    carried: set[str] = set()
    closed: set[str] = set()
    for closing, token in RESERVATION.findall(FENCE.sub("", text)):
        (closed if closing.strip() else carried).add(token)
    return carried, closed


def test_a_declared_reservation_names_a_tracked_decision() -> None:
    """The rule itself: a reservation with a trigger has a row.

    Not that the row is well written -- that a reader following the token lands
    somewhere the project already reviews, instead of on a sentence that only
    exists inside one document.
    """
    known = _open_tokens() | _closed_tokens()
    dangling = []
    for adr in _adrs():
        carried, closed = _reservations(adr.read_text(encoding="utf-8"))
        for token in sorted(carried | closed):
            if token not in known:
                dangling.append(f"{adr.name} -> {token}")

    assert dangling == [], (
        "These reservations name a decision the register does not carry:\n  "
        + "\n  ".join(dangling)
        + "\n\nA reservation that lives only in an ADR's prose is the one that gets"
        " lost on the next transcription. Give it a row, or drop the marker."
    )


def test_an_open_reservation_is_not_pointed_at_a_closed_decision() -> None:
    """An open reservation on a closed decision is one of two mistakes.

    Either the reservation is resolved and the marker should say so, or the token
    is wrong. Both are worth failing on, because both read as "still tracked" to
    the next person and are not.
    """
    closed = _closed_tokens() - _open_tokens()
    stale = []
    for adr in _adrs():
        carried, _ = _reservations(adr.read_text(encoding="utf-8"))
        for token in sorted(carried & closed):
            stale.append(f"{adr.name} -> {token}")

    assert stale == [], (
        "These carry an OPEN reservation on a decision the register has closed:\n  "
        + "\n  ".join(stale)
        + "\n\nSay `REZERVĂ ÎNCHISĂ` and how it was closed, or fix the token."
    )


def test_a_reservation_propagates_to_whatever_leans_on_it() -> None:
    """The half that would have caught ADR-065.

    An ADR that names another in `Legate:` is leaning on it. If that one carries
    an open reservation, this one either carries it too or closes it by name --
    never neither, because "neither" is indistinguishable from having forgotten,
    which is exactly what happened.

    **Scoped to ADRs written from ADR-066's date on, deliberately.** Applied
    backwards it flagged four ADRs that reference ADR-044 without touching the
    tariffs at all -- 045 on the source of truth for parameters, 046 on the
    confidence history, 047 on parameter stamping, 048 on formulas. All four are
    real dependencies and none of them restates the reserved claim. A guard that
    nags on those gets switched off, and a switched-off guard checks nothing --
    the same argument `C29` makes for not extending mypy strict everywhere. A
    process rule binds what is written after it; where an older ADR needs the
    marker, someone adds it by judgement, as was done for ADR-044.
    """
    adopted = DATE_LINE.search(RULE.read_text(encoding="utf-8"))
    assert adopted is not None, "ADR-066 has no `- **Data:**` line to scope this check by."
    since = adopted.group(1)
    carried_by: dict[str, set[str]] = {}
    for adr in _adrs():
        carried, _ = _reservations(adr.read_text(encoding="utf-8"))
        if carried:
            carried_by[adr.name[:3]] = carried

    dropped = []
    for adr in _adrs():
        text = adr.read_text(encoding="utf-8")
        written = DATE_LINE.search(text)
        if written is None or written.group(1) < since:
            continue
        related = RELATED_LINE.search(text)
        if related is None:
            continue
        mine_open, mine_closed = _reservations(text)
        for number in re.findall(r"\((\d{3})-[^)]*\.md\)", related.group(1)):
            for token in carried_by.get(number, set()):
                if token not in mine_open and token not in mine_closed:
                    dropped.append(f"{adr.name} leans on ADR-{number} and drops {token}")

    assert dropped == [], (
        "These lean on an ADR carrying an open reservation and neither repeat nor"
        " close it:\n  "
        + "\n  ".join(dropped)
        + "\n\nCarry the `REZERVĂ` marker forward, or close it by name. A reservation"
        " that survives only by being remembered is the one that was lost."
    )


def test_the_guard_still_has_something_to_read() -> None:
    """If every marker disappears, the three tests above pass on an empty set.

    A guard whose input vanished reports success. Same failure mode
    `test_domain_decisions_cite_sources.py` names one level up, same answer.
    """
    found = any(_reservations(p.read_text(encoding="utf-8"))[0] for p in _adrs())
    assert found, (
        "No ADR declares a `REZERVĂ` any more. Either every reservation was closed "
        "-- in which case say so here -- or the marker has drifted and these tests "
        "now check nothing."
    )
