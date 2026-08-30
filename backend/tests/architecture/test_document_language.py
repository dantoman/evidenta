"""The precondition C38 leans on -- ADR-033.

    "Generarea unui document legal deschide explicit contextul lingvistic
     românesc. Limba activă a cererii sau a task-ului nu se moștenește."

Nothing generates a document yet, so this test cannot prove the rule is kept. It
proves the ground it stands on has not moved, which is the part that would move
silently.

Measured on Django 5.2.17 before the rule was written, and the numbers are the
argument:

* ``formats.date_format(date(2026, 3, 7))`` renders ``7 Martie 2026`` under an
  active ``ro``, ``7 марта 2026`` plus the Russian era suffix under ``ru``, and
  ``March 7, 2026`` under ``en`` -- where the decimal separator also flips to a
  dot. A date on an invoice is formatted by whoever activated a language last.
* ``translation.activate("ru")`` leaves ``ru`` active in that thread after the
  unit of work that set it ends -- there is no automatic restoration to
  ``LANGUAGE_CODE``. A reused worker carries it into the next task, which is why
  the rule names Celery explicitly.
* A fresh thread starts at ``LANGUAGE_CODE``, which is ``ro`` today. That is the
  only reason the risk is not live yet, and it is exactly what this test pins.

So: the server activates no language, and the fallback is Romanian. The day
either changes -- a Russian interface served from Django, notifications in the
recipient's language -- the document pipeline needs its own guard first: render
with ``ru`` active, assert the output is Romanian. This test is where that
requirement is written down, and it fails until somebody reads it.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings

REPO = Path(__file__).resolve().parents[3]
SOURCES = (REPO / "backend/evidenta", REPO / "backend/config")

#: Every way the active language becomes request or task state. Not a style
#: preference: each one of these makes the language of a generated document
#: depend on who asked for it.
ACTIVATIONS = re.compile(r"LocaleMiddleware|translation\.activate\(|\bactivate\(\s*['\"]")


def python_files() -> list[Path]:
    return sorted(p for root in SOURCES for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def test_the_fallback_language_is_romanian() -> None:
    """The whole rule rests on this one line of settings."""
    assert settings.LANGUAGE_CODE == "ro"


def test_the_server_activates_no_language() -> None:
    offenders = [
        f"{path.relative_to(REPO)}:{number}: {line.strip()}"
        for path in python_files()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if ACTIVATIONS.search(line)
    ]
    assert not offenders, (
        "Server-side language activation appeared -- ADR-033 and C38.\n"
        + "\n".join(offenders)
        + "\n\nBefore this is allowed, the document pipeline needs the guard the ADR "
        "names: render a document with `ru` active and assert the output is Romanian. "
        "Add that test, then narrow this one to the call sites it covers."
    )


def test_a_register_export_is_romanian_whatever_language_is_active() -> None:
    """The guard the ADR named for the day a pipeline exists. It exists now: the
    CSV export of F1.8 (C20). Rendered with `ru` active, the bytes are the same
    as with `ro` -- the formatter reads no language, and the pipeline's own
    `override("ro")` would keep it so if one day it did.

    `translation.override`, not `activate`, on purpose: the test above forbids
    server-side activation, and this one has to leave no language behind it.
    """
    from datetime import date
    from decimal import Decimal
    from uuid import uuid4

    from django.utils import translation

    from evidenta.accounting.ledger.services.export import trial_balance_csv
    from evidenta.accounting.ledger.services.trial_balance import TrialBalance, TrialBalanceRow

    balance = TrialBalance(
        start_date=date(2026, 3, 7),
        end_date=date(2026, 3, 31),
        rows=(
            TrialBalanceRow(
                account_id=uuid4(),
                account_code="FIXTURE-A",
                name_ro="Cont de fixture cu diacritice: ăîșț",
                opening=Decimal("1234.5678"),
                debit=Decimal("0.0050"),
                credit=Decimal("10"),
                closing=Decimal("1224.5728"),
            ),
        ),
    )

    with translation.override("ro"):
        romanian = trial_balance_csv(balance)
    with translation.override("ru"):
        under_russian = trial_balance_csv(balance)
    with translation.override("en"):
        under_english = trial_balance_csv(balance)

    assert romanian == under_russian == under_english
    text = romanian.decode("utf-8-sig")
    assert "1234,57" in text and "0,01" in text and "ăîșț" in text
    assert "1234.57" not in text
