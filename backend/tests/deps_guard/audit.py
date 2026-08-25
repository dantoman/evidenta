"""Suite 3 -- the dependency guard.

CLAUDE.md section 3 states the module graph and calls it acyclic. Stated is all
it was: nothing read it, so the first import in the wrong direction would have
been found by a human noticing, or not at all. A cycle is cheap to prevent and
expensive to remove -- every module added after it pays for it.

The guard walks ``backend/evidenta`` with the ast module, resolves every internal
import, and compares the direction against the contract in

    infra/modules/dependencies.toml

Reading the contract rather than hard-coding it is the same choice the model
guard made: a guard whose expectations live in its own source gets edited to make
the suite pass, which is the failure mode the contract exists to prevent.

Static, deliberately. Importing the modules to inspect their dependencies would
need Django configured, a database reachable, and every module importable at
once -- and would miss the import that only runs inside a function.
"""

from __future__ import annotations

import ast
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACT = REPO_ROOT / "infra" / "modules" / "dependencies.toml"
PACKAGE_ROOT = REPO_ROOT / "backend" / "evidenta"

#: The distribution package everything internal lives under. An import that does
#: not start with this is somebody else's code and not this guard's business.
ROOT = "evidenta"

#: The module that holds a Django app's tables. D6 is about this file: two
#: modules that talk through each other's models are one module with a seam.
MODELS = "models"


@dataclass(frozen=True)
class Finding:
    rule: str
    module: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.rule}] {self.module}: {self.detail}"


def _load(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


class Contract:
    """The declared shape of the module graph.

    Loads from the contract file by default, and accepts explicit data instead --
    the second form is what the guard's own self-tests use, so that proving a rule
    can fire never depends on what the product happens to have built.
    """

    def __init__(
        self,
        layers: list[dict[str, Any]] | None = None,
        forbidden: list[dict[str, Any]] | None = None,
        d6: dict[str, Any] | None = None,
    ) -> None:
        if layers is None and forbidden is None and d6 is None:
            data = _load(CONTRACT)
            layers = data.get("layer", [])
            forbidden = data.get("forbidden", [])
            d6 = data.get("d6", {})

        self.layers: dict[str, dict[str, Any]] = {entry["name"]: entry for entry in (layers or [])}
        self.forbidden: list[dict[str, Any]] = forbidden or []
        self.schema_layers: list[str] = list((d6 or {}).get("schema_layers", []))

    def declares(self, package: str) -> bool:
        return package in self.layers

    def may_import(self, importer: str, imported: str) -> bool:
        if importer == imported:
            return True
        return imported in self.layers[importer].get("may_import", [])

    def rule_for(self, layer: str) -> str:
        return str(self.layers[layer].get("rule", "DG"))

    def composes_schema(self, importer: str, imported: str) -> bool:
        """Whether one module may name another module's model class at all (D6).

        Both halves are load-bearing. Drop the first and a service reaches into
        another module's tables; drop the second and two business modules end up
        sharing a table through a foreign key, which is the coupling the rule is
        about. The layers that may be composed against are contract data, so
        widening them is an edit to the contract -- which is an ADR.
        """
        return _is_models_module(importer) and _layer_of(imported) in self.schema_layers


def module_name(path: Path, package_root: Path) -> str:
    """Dotted name of the module a file defines.

    ``__init__.py`` names its package, not a submodule inside it -- which is what
    makes relative imports resolve one level differently there.
    """
    relative = path.relative_to(package_root.parent).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _package_of(dotted: str, is_package: bool) -> str:
    """The package a relative import inside this module counts from."""
    if is_package:
        return dotted
    return dotted.rsplit(".", 1)[0] if "." in dotted else ""


def imports_of(source: str, dotted: str, is_package: bool) -> list[tuple[str, int]]:
    """Every internal import target in one file, most specific form first.

    ``from x.y import z`` yields both ``x.y`` and ``x.y.z``: the first carries the
    direction, the second is what D6 needs -- ``from platform.identity import
    models`` and ``from platform.identity.models import User`` are the same fact
    written two ways, and a guard that saw only one of them would be trivially
    avoidable.
    """
    tree = ast.parse(source)
    targets: list[tuple[str, int]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                package = _package_of(dotted, is_package).split(".")
                trimmed = package[: len(package) - (node.level - 1)] if package != [""] else []
                base = ".".join([*trimmed, base]) if base else ".".join(trimmed)
            if not base:
                continue
            targets.append((base, node.lineno))
            targets.extend((f"{base}.{alias.name}", node.lineno) for alias in node.names)

    return [(target, line) for target, line in targets if target.split(".")[0] == ROOT]


def _layer_of(dotted: str) -> str:
    """The layer package a dotted name belongs to, or "" for none.

    A module sitting directly under ``evidenta/`` belongs to no layer, and the
    empty string is declared by no contract -- so it is reported rather than
    waved through. C1 forbids exactly that file: the one that belongs nowhere.
    """
    parts = dotted.split(".")
    return parts[1] if len(parts) > 1 else ""


def _module_of(dotted: str) -> str:
    """``evidenta.<layer>.<app>`` -- the unit D6 speaks about."""
    return ".".join(dotted.split(".")[:3])


def _is_models_module(dotted: str) -> bool:
    """``evidenta.<layer>.<app>.models``, whether that is a file or a package."""
    parts = dotted.split(".")
    return len(parts) > 3 and parts[3] == MODELS


def _matches(dotted: str, prefix: str) -> bool:
    return prefix == "*" or dotted == prefix or dotted.startswith(f"{prefix}.")


def audit(package_root: Path | None = None, contract: Contract | None = None) -> list[Finding]:
    """Every dependency violation under ``package_root``, in file order."""
    root = package_root or PACKAGE_ROOT
    rules = contract or Contract()
    findings: list[Finding] = []
    undeclared: set[str] = set()

    for path in sorted(root.rglob("*.py")):
        dotted = module_name(path, root)

        # The distribution package itself declares nothing and holds no code.
        if dotted == ROOT:
            continue

        importer_layer = _layer_of(dotted)
        if not rules.declares(importer_layer):
            if importer_layer not in undeclared:
                undeclared.add(importer_layer)
                findings.append(
                    Finding(
                        "D0",
                        dotted,
                        f"'{ROOT}.{importer_layer}' is not declared in {CONTRACT.name}, "
                        f"so no direction applies to it",
                    )
                )
            continue

        is_package = path.name == "__init__.py"
        for target, line in imports_of(path.read_text(), dotted, is_package):
            findings.extend(_check(rules, dotted, importer_layer, target, line))

    return _first_per_location(findings)


def _first_per_location(findings: list[Finding]) -> list[Finding]:
    """One finding per rule per import statement.

    ``from x.models import A, B`` is one mistake written once; reporting it three
    times -- for the module and for each name -- turns a short list into a wall,
    and a wall is what stops being read.
    """
    seen: set[tuple[str, str]] = set()
    kept: list[Finding] = []
    for finding in findings:
        key = (finding.rule, finding.module)
        if key not in seen:
            seen.add(key)
            kept.append(finding)
    return kept


def _check(
    rules: Contract, dotted: str, importer_layer: str, target: str, line: int
) -> list[Finding]:
    findings: list[Finding] = []
    target_layer = _layer_of(target)

    if not rules.declares(target_layer):
        return [
            Finding(
                "D0",
                f"{dotted}:{line}",
                f"imports {target}, whose package is not declared in {CONTRACT.name}",
            )
        ]

    if not rules.may_import(importer_layer, target_layer):
        allowed = rules.layers[importer_layer].get("may_import") or "nothing"
        findings.append(
            Finding(
                rules.rule_for(importer_layer),
                f"{dotted}:{line}",
                f"{importer_layer} imports {target_layer} ({target}); the contract "
                f"allows {importer_layer} -> {allowed}",
            )
        )

    for entry in rules.forbidden:
        if not _matches(target, entry["target"]):
            continue
        if any(_matches(dotted, importer) for importer in entry["importers"]):
            findings.append(
                Finding(
                    str(entry["rule"]),
                    f"{dotted}:{line}",
                    f"imports {target}, forbidden from {entry['target']}",
                )
            )

    if (
        _is_models_module(target)
        and _module_of(target) != _module_of(dotted)
        and not rules.composes_schema(dotted, target)
    ):
        findings.append(
            Finding(
                "D6",
                f"{dotted}:{line}",
                f"imports {target} directly; modules talk through events, public "
                f"services or read models, never through each other's models",
            )
        )

    return findings


def main() -> int:
    findings = audit()
    for finding in findings:
        print(finding)
    if findings:
        print(f"\n{len(findings)} violation(s). The graph is in {CONTRACT}.")
        return 1
    print("Dependency contract: no violations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
