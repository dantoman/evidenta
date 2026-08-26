"""Domain decisions have to cite an act. A suspect list, not a proof.

**What this catches, and why it is worth catching.** Three decisions so far were
not resolved but *dissolved*: their framing rested on a wrong definition, and
reading the primary text made the question disappear rather than answering it.
All three had the same shape -- the decision was formed over a summary rather than
over the act. `OD-66` was read through a CNAS order instead of the annex to the
law that actually carries the tariffs; `C3` assumed a choice that point 15
prescribes; `C5` assumed handler variants for a formula the standard fixes whole.

A guard cannot ask "is this framed wrong". It can ask the mechanical question that
was true in every case: **does this decision cite a primary text, or only a
summary?** An ADR that settles a domain position with no normative citation is a
candidate for dissolution -- not necessarily wrong, but unreviewed.

**Deliberately not a proof.** It produces a list a human reads. The bar it
enforces is only the one nobody can argue with: a decision that declares itself a
domain decision and cites nothing at all.
"""

from __future__ import annotations

import re
from pathlib import Path

DECISIONS = Path(__file__).resolve().parents[3] / "docs" / "decisions"
REGISTER = DECISIONS / "000-open-decisions.md"
INDEX = DECISIONS / "README.md"

#: The marker an ADR puts in its Status line to declare itself a domain position.
#: Self-declared on purpose: nothing mechanical can tell a domain decision from a
#: technical one, and a heuristic that guessed would either nag on every tooling
#: ADR or miss the ones that matter. What is mechanical is forcing the
#: declaration at the moment it matters -- see the second test.
DOMAIN_MARKER = "decizie de domeniu"

#: What counts as citing a primary text. Deliberately broad: the failure being
#: prevented is *no* citation, and a narrow pattern would produce false alarms
#: that get the whole check switched off.
CITATION = re.compile(
    r"Legea nr\.|Ordinul (?:MF |Ministerului Finan)|Hotărârea Guvernului nr\.|HG nr\."
    r"|Codul fiscal|Monitorul Oficial|\bSNC\b|art\.\s?\d",
)


def _adrs() -> list[Path]:
    return sorted(p for p in DECISIONS.glob("[0-9][0-9][0-9]-*.md") if p.name != REGISTER.name)


def _section_d_decisions() -> set[str]:
    """Open decisions that the register itself says need a source or the accountant."""
    text = REGISTER.read_text(encoding="utf-8")
    start = text.index("## D. Decizii care necesită surse externe")
    end = text.index("\n## ", start + 1)
    return set(re.findall(r"OD-\d+", text[start:end]))


def test_a_domain_decision_cites_at_least_one_act() -> None:
    """The bar nobody can argue with: declared a domain position, cites nothing.

    Every dissolved decision so far was formed over a summary. This does not prove
    the citation was read correctly -- `OD-66` cited a real order and was still
    framed wrong -- only that the decision reached for a primary text at all.
    """
    silent = [
        p.name
        for p in _adrs()
        if DOMAIN_MARKER in p.read_text(encoding="utf-8")
        and not CITATION.search(p.read_text(encoding="utf-8"))
    ]
    assert not silent, (
        "These ADRs declare themselves domain decisions and cite no normative act:\n  "
        + "\n  ".join(silent)
        + "\n\nA domain position settled over a summary is a candidate for dissolution."
        " Cite the act, or drop the marker if the decision is technical."
    )


def test_an_adr_closing_a_source_dependent_decision_declares_itself() -> None:
    """Section D says outright that these need a citable source or the accountant.

    So an ADR that closes one is a domain decision by the register's own words,
    and has to say so -- which is what puts it under the first test. This is the
    mechanical half: the classification is forced exactly where getting it wrong
    is most expensive.
    """
    section_d = _section_d_decisions()
    index = INDEX.read_text(encoding="utf-8")
    rows = re.findall(r"^\| \[(\d{3})\]\(([^)]+)\) \|.*\| ([^|]*) \|$", index, re.M)

    undeclared = []
    for number, filename, closes in rows:
        if not set(re.findall(r"OD-\d+", closes)) & section_d:
            continue
        adr = DECISIONS / filename
        if adr.exists() and DOMAIN_MARKER not in adr.read_text(encoding="utf-8"):
            undeclared.append(f"ADR-{number} ({filename}) closes {closes.strip()}")

    assert not undeclared, (
        "These ADRs close a decision the register places in section D -- needing an\n"
        "external source or the practising accountant -- without declaring themselves\n"
        f"domain decisions (marker: {DOMAIN_MARKER!r}):\n  " + "\n  ".join(undeclared)
    )


def test_the_marker_and_the_register_have_not_drifted_apart() -> None:
    """If section D disappears or is renamed, the second test silently passes.

    A guard whose input vanished reports success, which is the failure mode this
    whole file exists to notice one level up.
    """
    assert _section_d_decisions(), (
        "Section D of the register is empty or its heading changed. "
        "test_an_adr_closing_a_source_dependent_decision_declares_itself now checks "
        "nothing and will keep passing."
    )
