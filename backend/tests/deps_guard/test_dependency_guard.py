"""The dependency guard, and proof that every rule can fail.

A guard that only ever reports "no findings" is indistinguishable from a guard
that checks nothing -- and this one runs against a tree that satisfies the graph
today, so it would report exactly that either way.

So each rule is proved on a probe tree built for it: a handful of files written
to a temporary directory, with one import in the wrong direction. The contract
used for the probes is declared here rather than read from
infra/modules/dependencies.toml, because a self-test that read the real contract
would go quiet the moment the product's own layout changed.
"""

from __future__ import annotations

from pathlib import Path

from tests.deps_guard.audit import Contract, Finding, audit

#: The graph the probes are checked against. Deliberately smaller than the real
#: one, and deliberately not loaded from it.
PROBE_CONTRACT = Contract(
    layers=[
        {"name": "platform", "may_import": [], "rule": "DG"},
        {"name": "fiscal", "may_import": ["platform"], "rule": "D1"},
        {"name": "masterdata", "may_import": ["platform"], "rule": "DG"},
        {"name": "accounting", "may_import": ["platform", "masterdata", "fiscal"], "rule": "D2"},
        {
            "name": "operations",
            "may_import": ["platform", "masterdata", "fiscal", "accounting"],
            "rule": "DG",
        },
        {"name": "firmspace", "may_import": ["platform"], "rule": "DG"},
    ],
    forbidden=[
        {
            "rule": "D3",
            "target": "evidenta.accounting.ledger",
            "importers": ["evidenta.operations"],
        },
        {
            "rule": "D4",
            "target": "evidenta.operations.tax",
            "importers": ["evidenta.operations.payroll"],
        },
        {"rule": "D5", "target": "evidenta.firmspace", "importers": ["*"]},
    ],
    d6={"schema_layers": ["platform", "masterdata"]},
)

#: A tree that satisfies every rule, as the baseline the one-import probes are
#: added to.
COMPLIANT = {
    "platform.rls.context": "TENANT = 'tenant_id'\n",
    "fiscal.registry.selection": "def implementation_for(date): ...\n",
    "accounting.events.emit": "from evidenta.fiscal.registry import selection\n",
    "operations.sales.services": "from evidenta.accounting.events import emit\n",
}


def tree(root: Path, modules: dict[str, str]) -> Path:
    """Write a probe package and return the path the guard should walk."""
    package = root / "evidenta"
    package.mkdir(parents=True, exist_ok=True)
    (package / "__init__.py").write_text("")
    for dotted, source in modules.items():
        path = package.joinpath(*dotted.split(".")).with_suffix(".py")
        path.parent.mkdir(parents=True, exist_ok=True)
        for level in range(1, len(dotted.split("."))):
            marker = package.joinpath(*dotted.split(".")[:level]) / "__init__.py"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.touch()
        path.write_text(source)
    return package


def probe(root: Path, **extra: str) -> list[Finding]:
    return audit(tree(root, COMPLIANT | extra), PROBE_CONTRACT)


def rules(findings: list[Finding]) -> set[str]:
    return {finding.rule for finding in findings}


def test_compliant_tree_has_no_findings(tmp_path: Path) -> None:
    assert probe(tmp_path) == []


def test_detects_import_against_the_graph(tmp_path: Path) -> None:
    """platform is the floor: nothing it imports may sit above it."""
    findings = probe(
        tmp_path,
        **{"platform.rls.guard": "from evidenta.accounting.events import emit\n"},
    )
    assert "DG" in rules(findings)


def test_detects_fiscal_importing_a_business_module(tmp_path: Path) -> None:
    findings = probe(
        tmp_path,
        **{"fiscal.registry.rates": "from evidenta.accounting.events import emit\n"},
    )
    assert "D1" in rules(findings)


def test_allows_fiscal_to_import_the_platform(tmp_path: Path) -> None:
    """D1 is about business modules, and platform is not one.

    The contract said `fiscal -> nothing` for an afternoon. Nothing caught it,
    because `evidenta/fiscal/` did not exist yet; the first file placed there was
    a migration importing run_sql_file -- the mechanism C30 requires -- and the
    guard reported the graph rather than the code. It was right to.
    """
    findings = probe(
        tmp_path,
        **{"fiscal.registry.migrations": "from evidenta.platform.rls.sql import run_sql_file\n"},
    )
    assert findings == []


def test_detects_accounting_importing_operations(tmp_path: Path) -> None:
    findings = probe(
        tmp_path,
        **{"accounting.ledger.posting": "from evidenta.operations.sales import services\n"},
    )
    assert "D2" in rules(findings)


def test_detects_operations_importing_the_ledger(tmp_path: Path) -> None:
    """The graph allows operations -> accounting. D3 narrows it to events."""
    findings = probe(
        tmp_path,
        **{"operations.sales.posting": "from evidenta.accounting.ledger import posting\n"},
    )
    assert rules(findings) == {"D3"}


def test_detects_payroll_importing_tax(tmp_path: Path) -> None:
    findings = probe(
        tmp_path,
        **{"operations.payroll.calculation": "from evidenta.operations.tax import ipc\n"},
    )
    assert "D4" in rules(findings)


def test_detects_any_import_of_firmspace(tmp_path: Path) -> None:
    findings = probe(
        tmp_path,
        **{"operations.sales.screen": "from evidenta.firmspace.dashboard import panel\n"},
    )
    assert "D5" in rules(findings)


def test_detects_a_model_import_from_another_module(tmp_path: Path) -> None:
    findings = probe(
        tmp_path,
        **{"operations.sales.models": "from evidenta.operations.tax.models import VatCode\n"},
    )
    assert "D6" in rules(findings)


def test_allows_a_model_import_inside_the_same_module(tmp_path: Path) -> None:
    """D6 is about modules talking to each other, not about a module's own files."""
    findings = probe(
        tmp_path,
        **{
            "operations.sales.models": "class Invoice: ...\n",
            "operations.sales.services": "from evidenta.operations.sales.models import Invoice\n",
        },
    )
    assert findings == []


def test_allows_a_foreign_key_target_in_the_foundation_layer(tmp_path: Path) -> None:
    """Schema composition toward platform: Tenant, Company, User.

    Ten imports of exactly this shape existed when the guard was written, all of
    them foreign keys. Reading D6 to forbid them would have declared eight files
    defective for expressing a foreign key the way Django expresses one.
    """
    findings = probe(
        tmp_path,
        **{
            "platform.tenancy.models": "class Tenant: ...\n",
            "operations.sales.models": "from evidenta.platform.tenancy.models import Tenant\n",
        },
    )
    assert findings == []


def test_allows_a_foreign_key_target_in_reference_data(tmp_path: Path) -> None:
    """Article -> unit of measure. Reference data is pointed at; that is its job."""
    findings = probe(
        tmp_path,
        **{
            "masterdata.uom.models": "class UnitOfMeasure: ...\n",
            "masterdata.items.models": "from evidenta.masterdata.uom.models import UnitOfMeasure\n",
        },
    )
    assert findings == []


def test_rejects_a_foreign_key_between_two_business_modules(tmp_path: Path) -> None:
    """The exemption stops at the foundation, and this is where that is proved.

    Two business modules sharing a table through a foreign key are coupled,
    however much the import looks like schema. Without this test the exemption
    would be indistinguishable from switching D6 off.
    """
    findings = probe(
        tmp_path,
        **{
            "operations.purchases.models": "class Order: ...\n",
            "operations.sales.models": "from evidenta.operations.purchases.models import Order\n",
        },
    )
    assert "D6" in rules(findings)


def test_rejects_a_service_importing_the_foundation_models(tmp_path: Path) -> None:
    """The half of D6 that keeps its teeth: services do not read other tables."""
    findings = probe(
        tmp_path,
        **{
            "platform.tenancy.models": "class Tenant: ...\n",
            "operations.sales.services": "from evidenta.platform.tenancy.models import Tenant\n",
        },
    )
    assert "D6" in rules(findings)


def test_detects_a_package_the_contract_does_not_declare(tmp_path: Path) -> None:
    """An unknown layer is reported, never skipped -- skipping is the hole."""
    findings = probe(tmp_path, **{"crm.pipeline.models": "class Lead: ...\n"})
    assert "D0" in rules(findings)


def test_detects_a_module_that_belongs_to_no_layer(tmp_path: Path) -> None:
    """The file directly under evidenta/ -- the utils module C1 forbids."""
    findings = probe(tmp_path, **{"helpers": "def slugify(value): ...\n"})
    assert "D0" in rules(findings)


def test_resolves_relative_imports(tmp_path: Path) -> None:
    """`from ...operations import x` hides the direction from a plain grep."""
    findings = probe(
        tmp_path,
        **{"accounting.ledger.posting": "from ...operations.sales import services\n"},
    )
    assert "D2" in rules(findings)


def test_sees_an_import_inside_a_function(tmp_path: Path) -> None:
    """The deferred import is how a cycle is usually made to work at runtime."""
    findings = probe(
        tmp_path,
        **{
            "accounting.ledger.posting": (
                "def post(entry):\n"
                "    from evidenta.operations.sales import services\n"
                "    return services\n"
            )
        },
    )
    assert "D2" in rules(findings)


def test_reports_one_finding_per_import_statement(tmp_path: Path) -> None:
    """`from x import a, b, c` is one mistake, not three."""
    findings = probe(
        tmp_path,
        **{
            "accounting.ledger.posting": (
                "from evidenta.operations.sales.services import issue, cancel, reissue\n"
            )
        },
    )
    assert len(findings) == 1


def test_live_tree_is_clean() -> None:
    """The real package, against the real contract.

    The one that will fail for real one day. Everything above proves the guard
    can fail; this is the only test that says the codebase currently holds.
    """
    findings = audit()
    assert findings == [], "\n".join(str(finding) for finding in findings)
