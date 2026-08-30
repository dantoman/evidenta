"""The corpus's own guard: no case without a citation, no citation without a passage.

Three properties, all read from files rather than from the database:

* every ``test_*`` in this package went through `case(...)` and cites at
  least one passage -- "un caz care nu poate cita nu intră";
* every citation resolves: an ``ADR-NNN §x`` to a section heading of an
  existing ADR, anything else to a ``###`` heading of the transcription file;
* every ``regression_case_set`` the shipped parameter files name is a set with
  at least one case in it -- the two values were pointing at nothing until now;
* every case ends by reconciling the three reports (`agree`), which is the
  exit criterion of F1 (ADR-054 §3).
"""

from __future__ import annotations

import importlib
import inspect
import re
import tomllib
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

from tests.corpus import citations
from tests.corpus.book import DATA
from tests.corpus.citations import CASES, TRANSCRIPTION

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
ADR = re.compile(r"^ADR-(\d{3}) §(\d+(?:\.\d+)*)$")


def corpus_modules() -> list[ModuleType]:
    return [
        importlib.import_module(f"tests.corpus.{path.stem}")
        for path in sorted(HERE.glob("test_*.py"))
        if path.name != Path(__file__).name
    ]


def case_functions() -> list[tuple[ModuleType, str, Callable[..., object]]]:
    return [
        (module, name, function)
        for module in corpus_modules()
        for name, function in inspect.getmembers(module, inspect.isfunction)
        if name.startswith("test_") and function.__module__ == module.__name__
    ]


def transcribed_titles() -> set[str]:
    text = (ROOT / TRANSCRIPTION).read_text(encoding="utf-8")
    return {line[4:].strip() for line in text.splitlines() if line.startswith("### ")}


def adr_has_section(number: str, section: str) -> bool:
    matches = list((ROOT / "docs" / "decisions").glob(f"{number}-*.md"))
    if len(matches) != 1:
        return False
    heading = re.compile(rf"^#{{2,3}} {re.escape(section)}(?:\.\s|\s|$)", re.MULTILINE)
    return heading.search(matches[0].read_text(encoding="utf-8")) is not None


def test_every_test_in_the_corpus_entered_through_case_and_cites() -> None:
    registered = {(c.module, c.name) for c in CASES}
    for module, name, function in case_functions():
        assert (module.__name__, name) in registered, (
            f"{module.__name__}.{name} nu a intrat prin `case(...)`: un caz care nu citează "
            f"nu intră în corpus"
        )
        marks = [m for m in getattr(function, "pytestmark", []) if m.name == "fiscal_regression"]
        assert marks and marks[0].kwargs["cites"], f"{name} nu poartă markerul cu citările"


def test_every_citation_resolves_to_a_transcribed_passage_or_an_adr_section() -> None:
    titles = transcribed_titles()
    assert titles, f"{TRANSCRIPTION} nu are niciun titlu `### `"
    for the_case in CASES:
        for cite in the_case.cites:
            adr = ADR.match(cite)
            if adr:
                assert adr_has_section(adr.group(1), adr.group(2)), (
                    f"{the_case.name} citează {cite!r}, care nu e o secțiune a unui ADR existent"
                )
            else:
                assert cite in titles, (
                    f"{the_case.name} citează {cite!r}, care nu e transcris în {TRANSCRIPTION}"
                )


def test_every_regression_case_set_the_registry_names_has_cases() -> None:
    named = {
        logic["regression_case_set"]
        for path in sorted(DATA.glob("*.toml"))
        for logic in tomllib.loads(path.read_text(encoding="utf-8")).get("logic", ())
    }
    assert named, "niciun fișier de parametri nu numește un set de regresie"
    populated = {name for the_case in CASES for name in the_case.sets}
    for name in sorted(named):
        assert name in populated, (
            f"`regression_case_set = {name!r}` arată spre un set fără niciun caz"
        )


def test_the_set_names_follow_the_registrys_convention() -> None:
    shape = re.compile(r"^corpus/[a-z_]+(\.[a-z_]+)*/\d+$")
    for the_case in CASES:
        for name in the_case.sets:
            assert shape.match(name), (
                f"{the_case.name}: setul {name!r} nu e corpus/<cheie>/<versiune>"
            )


def test_every_case_ends_by_reconciling_the_three_reports() -> None:
    for _, name, function in case_functions():
        assert "agree(book" in inspect.getsource(function), (
            f"{name} nu reconciliază balanța, Cartea Mare și fișa contului (`agree(book)`)"
        )


@pytest.mark.parametrize("name", [citations.ABSORPTION, citations.ROUNDING])
def test_the_two_shipped_sets_are_the_ones_the_files_name(name: str) -> None:
    named = {
        logic["regression_case_set"]
        for path in DATA.glob("*.toml")
        for logic in tomllib.loads(path.read_text(encoding="utf-8")).get("logic", ())
    }
    assert name in named
