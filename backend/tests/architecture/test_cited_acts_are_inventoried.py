"""An act cited but inventoried nowhere is invisible -- nobody looks for it.

**What this catches.** A decision or a parameter file names an act; the research
inventory records what was obtained and what was not. Both operands exist. What
was missing was the question *"do they cover each other?"* -- the same shape as
the population reconciliation in ADR-070 section 5, and the same bucket: an
unasked question.

An act on neither list cannot be looked for, because the list of what is missing
does not mention it. A recorded "not obtained" is a dated fact; an unrecorded one
is an assumption nobody can date.

**Its first run found three real holes and one false alarm** (2026-08-30). The
false alarm is instructive: `HG685` is written in one research file without a
separator, so a citation scan misses it there while catching `HG 685/2019` in the
backlog. Citation form is part of what makes an inventory checkable.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DECISIONS = ROOT / "docs" / "decisions"
BACKLOG = ROOT / "docs" / "_bootstrap"
RESEARCH = ROOT / "docs" / "_input" / "cercetare"
DATA = ROOT / "backend" / "evidenta" / "fiscal" / "parameters" / "data"

#: Two spellings for the same thing, and both have to be read or the guard cries
#: wolf: citations write `HG 685/2019`, inventories write `nr. 685 din 30.12.2019`.
SLASH = re.compile(
    r"(?:LP|L\.|Legea nr\.|Legea|HG|Hotărârea Guvernului nr\.|OMF|Ordinul MF nr\."
    r"|Ordinul Ministerului Finan[țţ]elor nr\.|OSFS|Ordinul IFPS|Ordinul CNAS nr\.)"
    r"\s*(?:nr\.\s*)?(\d{1,4})\s*/\s*(\d{4})"
)
DIN = re.compile(r"nr\.\s*(\d{1,4})(?:-[A-ZÎÂ]+)?\s+din\s+\d{1,2}\.\d{2}\.(\d{4})")

#: Cited, inventoried nowhere, and known to be so. Each entry is a hole somebody
#: has looked at, not a silenced alarm -- which is why the reason is required
#: reading and the list is expected to shrink.
PENDING = {
    "419/2023": "Legea bugetului asigurărilor sociale pe 2024 — ancorează `cnas.employer_rate`, "
    "adică un parametru încărcat stă pe un act pe care niciun fișier de cercetare nu-l descrie. "
    "Găsită de această verificare la prima rulare, 2026-08-30.",
    "302/2018": "Citată în ADR-016 pentru limba contabilității; neinventariată.",
    "59/2026": "OMF 59/2026 — redacția IALS21 din 04.05.2026, primită 2026-08-30 în lotul de surse "
    "al proprietarului; fișierul de cercetare nu e încă scris.",
}


def _acts(text: str) -> set[str]:
    found = {f"{int(m.group(1))}/{m.group(2)}" for m in SLASH.finditer(text)}
    found |= {f"{int(m.group(1))}/{m.group(2)}" for m in DIN.finditer(text)}
    return found


def _read(paths: list[Path]) -> set[str]:
    out: set[str] = set()
    for p in paths:
        out |= _acts(p.read_text(encoding="utf-8"))
    return out


def cited() -> dict[str, set[str]]:
    where: dict[str, set[str]] = {}
    sources = sorted(DECISIONS.glob("*.md")) + sorted(BACKLOG.glob("*.md"))
    sources += sorted(DATA.glob("*.toml"))
    for p in sources:
        for act in _acts(p.read_text(encoding="utf-8")):
            where.setdefault(act, set()).add(p.name)
    return where


def inventoried() -> set[str]:
    return _read(sorted(RESEARCH.glob("*.md")))


def test_every_cited_act_is_on_one_of_the_two_lists() -> None:
    """Obtained or not obtained -- but on a list either way.

    Not that the act was read. That an act named in a decision can be found in
    the inventory at all, so somebody looking for what is missing sees it.
    """
    inventory = inventoried()
    holes = {
        act: sorted(where)
        for act, where in cited().items()
        if act not in inventory and act not in PENDING
    }
    assert holes == {}, (
        "These acts are cited and appear on neither list:\n  "
        + "\n  ".join(f"{a} — {', '.join(w)}" for a, w in sorted(holes.items()))
        + "\n\nAdd the act to a research file, or to PENDING with the reason. An act"
        " nobody inventoried is one nobody will look for."
    )


def test_the_pending_list_is_not_a_graveyard() -> None:
    """An entry that got inventoried has to leave, or the list stops meaning anything.

    The failure mode of every allowlist: it grows, nobody prunes it, and it ends
    up asserting the opposite of what it was for.
    """
    inventory = inventoried()
    settled = sorted(act for act in PENDING if act in inventory)
    assert settled == [], (
        "These are in PENDING but now inventoried, so the entry is stale:\n  "
        + "\n  ".join(settled)
        + "\n\nRemove them from PENDING."
    )


def test_the_parameter_files_name_acts_the_inventory_knows() -> None:
    """The narrow case that matters most, stated separately so it cannot hide.

    A loaded fiscal parameter anchored to an act no research file describes is a
    value whose provenance stops one link short -- which is what `OD-92` is about
    on the margin side, from the other end.
    """
    inventory = inventoried()
    unknown: list[str] = []
    for p in sorted(DATA.glob("*.toml")):
        document = tomllib.loads(p.read_text(encoding="utf-8"))
        for act in document.get("act", []):
            number, year = str(act.get("act_number", "")), str(act.get("act_date", ""))[:4]
            if not number or not year:
                continue
            key = f"{int(number)}/{year}" if number.isdigit() else ""
            if key and key not in inventory and key not in PENDING:
                unknown.append(f"{p.name}: {act.get('ref')} -> {key}")
    assert unknown == [], (
        "These parameter files anchor a value in an act the inventory does not carry:\n  "
        + "\n  ".join(unknown)
    )
