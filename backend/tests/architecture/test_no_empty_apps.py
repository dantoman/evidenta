"""CLAUDE.md section 4, given a guard -- ADR-028.

    "Nu se creează app-uri Django goale pentru module din faze viitoare.
     «Modelat în F0» înseamnă că structura din faza curentă nu face imposibil
     modulul viitor, nu că app-ul există acum."

The rule had no mechanical check. An app created for a future phase would pass
every suite: the dependency guard reports `D0` only for a package whose layer is
undeclared, and `masterdata/warehouses` would sit inside a declared one.

This is not a proof that the rule is honoured -- "does this app carry its
weight" is a judgement. It is a proof that the exact shape the rule forbids
cannot appear without somebody noticing: a package registered as an application
that defines nothing.

No database. It reads the app registry and the file tree, so it runs in the fast
CI job.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from django.apps import apps

#: A module whose presence means the app does something. `models.py` is not in
#: the list on its own -- an app can legitimately hold only models (`uom` does)
#: and that is covered by the model count instead.
DOING_SOMETHING = (
    "services",
    "views.py",
    "urls.py",
    "tasks.py",
    "privileged.py",
    "middleware.py",
    "messages.py",
    "money.py",
    "subdomain.py",
    "cookie.py",
    "sql.py",
    "context.py",
    "guard.py",
)


def declares_something(models: list[object], root: Path) -> bool:
    """Whether an app defines anything at all.

    Extracted so the rule has a probe that can fail. A guard nobody has seen
    refuse is a guard nobody knows the shape of -- the same discipline the model
    guard and the dependency guard follow.
    """
    if models:
        return True
    return any((root / name).exists() for name in DOING_SOMETHING)


def own_apps() -> list[object]:
    return [config for config in apps.get_app_configs() if config.name.startswith("evidenta.")]


def test_the_project_has_apps_to_check() -> None:
    """The control.

    Without it, a change that stopped the registry from reporting our apps would
    make the test below pass over an empty list -- green, and checking nothing.
    """
    assert len(own_apps()) >= 10


@pytest.mark.parametrize("config", own_apps(), ids=lambda c: str(c.label))
def test_an_installed_app_defines_something(config: object) -> None:
    models = list(config.get_models())  # type: ignore[attr-defined]
    root = Path(str(config.path))  # type: ignore[attr-defined]
    assert declares_something(models, root), (
        f"{config.label} defines no model and no service, view, task or "  # type: ignore[attr-defined]
        f"middleware module. CLAUDE.md section 4 forbids an app created for a "
        f"module of a future phase: 'modelled in F0' means the current structure "
        f"does not make the future module impossible, not that the app exists "
        f"now. See ADR-028."
    )


def test_the_rule_refuses_an_empty_app(tmp_path: Path) -> None:
    """The probe. An app package with nothing in it but the scaffolding.

    This is exactly the shape ADR-028 forbids: `masterdata/warehouses` created in
    F0 for a module the map places in F4, holding one model class and waiting.
    Here it holds not even that.
    """
    (tmp_path / "__init__.py").touch()
    (tmp_path / "apps.py").touch()
    (tmp_path / "migrations").mkdir()
    assert not declares_something([], tmp_path)


def test_an_app_with_only_models_is_accepted(tmp_path: Path) -> None:
    """`uom` is real and holds only models. The rule is about apps that define
    nothing, not about apps that define only data.
    """
    assert declares_something([object()], tmp_path)
