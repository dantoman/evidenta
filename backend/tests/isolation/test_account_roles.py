"""Roles resolve to accounts, or refuse -- ADR-036 section 5.1, `R15`, `R18`.

The defect this module prevents is not visible in a balance. A handler that wrote
`5344` would post a correct-looking entry to a plausible account, and a wrong
account balances exactly as well as a right one. So the assertions here are about
refusals as much as about lookups: an unbound role stops the posting, and an
unknown role stops before that.

**Under the application role, like every test in this suite** (`T1`).

The fixture chart carries the real subaccount codes, and here that is not the
back door `OD-23` guards: the mapping *is* the plan, so a fixture with invented
codes would be testing a chart the plan forbids. What is not asserted anywhere is
the *content* of the nomenclature -- only that a role reaches whatever the
company's chart calls that code.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date

import pytest

from evidenta.accounting.coa.models import CompanyAccount
from evidenta.accounting.events.registry import ACCOUNT_ROLES
from evidenta.accounting.slots.catalogue import DEFAULTS, ROLES
from evidenta.accounting.slots.models import AccountRoleBinding
from evidenta.accounting.slots.services.binding import (
    RoleAccountMissingError,
    RoleNotBoundError,
    UnknownRoleError,
    bindings_of,
    install_default_bindings,
    resolve_role,
)
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

ON = date(2026, 3, 15)


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="roles")


@pytest.fixture
def scene(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> dict[str, uuid.UUID]:
    """A company whose chart holds every subaccount the mapping names."""
    tenant = world["tenant_a"]
    company = company_of(tenant, "1002600001001", "Alpha Roluri")
    grant_company(tenant, company, world["user_a"], world["user_a"])

    for default in DEFAULTS:
        seed(
            "INSERT INTO company_account (id, tenant_id, company_id, account_code,"
            " parent_id, origin, template_account_id, name_ro, account_class,"
            " normal_balance, allows_subaccounts, currency_tracking, quantity_tracking,"
            " required_dimensions, is_blocked, valid_from, valid_to, created_at, updated_at)"
            " VALUES (%s, %s, %s, %s, NULL, 'company', NULL, %s, 'asset', 'debit',"
            " false, false, false, '{}'::text[], false, '2020-01-01', NULL, now(), now())",
            [uuid.uuid4(), tenant, company, default.account_code, f"Cont {default.account_code}"],
        )
    return {"tenant": tenant, "company": company, "user": world["user_a"]}


# --- the catalogue -----------------------------------------------------------


def test_the_registry_now_has_a_catalogue_to_check_against() -> None:
    """`ACCOUNT_ROLES` sat empty with a comment naming the module that would fill it.

    Empty meant "do not check", which was the right default for a catalogue
    nobody had written -- and exactly the state in which a typo in a handler
    declaration became a role nothing could ever bind.
    """
    assert ROLES <= ACCOUNT_ROLES
    assert "TVA_COLECTATA" in ACCOUNT_ROLES


def test_the_vocabulary_and_the_mapping_cannot_drift() -> None:
    """One list, not two that agree until somebody edits one of them.

    The vocabulary is derived from the shipped mapping rather than retyped beside
    it. This pins the count so that a role silently disappearing from the file is
    a failure here rather than a refusal at posting, months later.
    """
    assert len(ROLES) == len(DEFAULTS) == 48
    assert len({default.account_code for default in DEFAULTS}) == 48


def test_no_account_code_is_written_in_engine_code() -> None:
    """`R15`, where it can actually fail.

    The mapping lives in a data file with its source. If somebody ever inlines a
    subaccount into the posting engine, this is the test that should have caught
    it -- so it looks where a code would be written, not where it is stored.
    """
    from pathlib import Path

    engine = Path(__file__).resolve().parents[2] / "evidenta" / "accounting" / "posting"
    offenders = []
    for path in engine.rglob("*.py"):
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#") or '"' not in stripped:
                continue
            for code in ("2211", "5344", "2252", "6112", "7112"):
                if f'"{code}"' in stripped:
                    offenders.append(f"{path.name}:{number}")
    assert offenders == [], f"account codes written into the engine: {offenders}"


# --- resolution --------------------------------------------------------------


def test_every_role_resolves_once_the_company_is_bound(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        install_default_bindings(tenant_id=scene["tenant"], company_id=scene["company"], on_date=ON)
        resolved = {role: resolve_role(scene["company"], role, ON) for role in sorted(ROLES)}

    assert len(resolved) == 48
    assert len(set(resolved.values())) == 48


def test_the_role_reaches_the_subaccount_the_plan_imposes(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Spot-checked on the two the reference documentation had inverted.

    `6111` is products and `6112` is goods; the source that said otherwise would
    have produced a balanced ledger with false financial statements, and nothing
    would have complained for months.
    """
    with tenant_context(context):
        install_default_bindings(tenant_id=scene["tenant"], company_id=scene["company"], on_date=ON)
        products = CompanyAccount.objects.get(
            id=resolve_role(scene["company"], "VENIT_PRODUSE", ON)
        )
        goods = CompanyAccount.objects.get(id=resolve_role(scene["company"], "VENIT_MARFURI", ON))
        cost_products = CompanyAccount.objects.get(
            id=resolve_role(scene["company"], "COST_PRODUSE", ON)
        )

    assert products.account_code == "6111"
    assert goods.account_code == "6112"
    assert cost_products.account_code == "7111"


def test_an_unbound_role_refuses_instead_of_guessing(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The refusal is the feature. A wrong account balances as well as a right one."""
    with tenant_context(context), pytest.raises(RoleNotBoundError) as excinfo:
        resolve_role(scene["company"], "TVA_COLECTATA", ON)

    assert excinfo.value.code == "slots.role_not_bound"


def test_an_unknown_role_is_a_typo_not_a_missing_binding(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Two different failures, and telling them apart is what saves the search.

    A role outside the catalogue cannot be configured into existence; a bound one
    that is missing can. The codes differ so the message can say which.
    """
    with tenant_context(context), pytest.raises(UnknownRoleError) as excinfo:
        resolve_role(scene["company"], "TVA_COLECTAT", ON)

    assert excinfo.value.code == "slots.role_unknown"


def test_installing_into_a_chart_missing_a_subaccount_refuses_entirely(
    context: TenantContext,
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> None:
    """All or nothing, deliberately.

    A partially bound company posts correctly until the day it meets the role
    nobody installed -- and that day is chosen by the transaction, not by
    anybody.
    """
    tenant = world["tenant_a"]
    company = company_of(tenant, "1002600001002", "Alpha Fara Plan")
    grant_company(tenant, company, world["user_a"], world["user_a"])

    with tenant_context(context), pytest.raises(RoleAccountMissingError) as excinfo:
        install_default_bindings(tenant_id=tenant, company_id=company, on_date=ON)

    assert excinfo.value.code == "slots.role_account_missing"
    with tenant_context(context):
        assert AccountRoleBinding.objects.filter(company_id=company).count() == 0


def test_installing_twice_adds_nothing(context: TenantContext, scene: dict[str, uuid.UUID]) -> None:
    """The overlap constraint would refuse it anyway; this says the service does."""
    with tenant_context(context):
        install_default_bindings(tenant_id=scene["tenant"], company_id=scene["company"], on_date=ON)
        again = install_default_bindings(
            tenant_id=scene["tenant"], company_id=scene["company"], on_date=ON
        )
        total = AccountRoleBinding.objects.filter(company_id=scene["company"]).count()

    assert again == []
    assert total == 48


def test_the_bindings_read_back_with_their_provenance(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """A binding with no source cannot be defended at an inspection."""
    with tenant_context(context):
        install_default_bindings(tenant_id=scene["tenant"], company_id=scene["company"], on_date=ON)
        rows = bindings_of(scene["company"], ON)

    assert len(rows) == 48
    assert all(row["source"] for row in rows)
    assert {row["role"] for row in rows} == ROLES


def test_another_tenant_sees_no_bindings(
    context: TenantContext, scene: dict[str, uuid.UUID], world: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        install_default_bindings(tenant_id=scene["tenant"], company_id=scene["company"], on_date=ON)

    other = TenantContext(
        tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="roles-b"
    )
    with tenant_context(other):
        assert AccountRoleBinding.objects.count() == 0
