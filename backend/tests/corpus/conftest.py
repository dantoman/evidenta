"""The corpus's one fixture: a book on the Plan's codes, with the 2026 exercise open.

Under the application role, like the isolation suite it borrows its seeders
from (`T1`): the corpus proves what the engine posts, and a superuser would
prove what the database would let anyone post. ``world``, ``seed``,
``company_of`` and ``grant_company`` are re-exported from
``tests/isolation/conftest.py`` for the reason ``tests/volume/conftest.py``
gives: one harness, not two drifting apart.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator

import psycopg
import pytest
from django.conf import settings

from evidenta.accounting.periods.services.opening import open_fiscal_year
from evidenta.accounting.slots.models import AccountRoleBinding
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.conftest import admin_dsn
from tests.corpus.book import (
    ACCOUNTS,
    ROLE_BINDINGS,
    YEAR_END,
    YEAR_START,
    Book,
    load_shipped_conventions,
    plan_account,
)
from tests.isolation.conftest import (  # noqa: F401 -- borrowed, as tests/volume does
    SEEDED_TABLES,
    clean_seeded_tables,
    company_of,
    grant_company,
    seed,
    world,
)
from tests.isolation.test_manual_entry import seed_template as seed_numbering

#: What the shipped loader and activator commit, in the harness's own order.
REFERENCE_TABLES = tuple(
    table
    for table in SEEDED_TABLES
    if table
    in {
        "fiscal_logic_version",
        "fiscal_parameter_confidence_event",
        "fiscal_parameter",
        "fiscal_parameter_source",
        "normative_act_publication",
        "official_publication",
        "normative_act",
        "privileged_access_log",
    }
)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_teardown(item: pytest.Item) -> Iterator[None]:
    """Take back the reference rows the subprocess committed -- after the rollback.

    `book` loads the shipped files through the shipped commands, in a
    subprocess, so the rows are committed and outlive the test's transaction.
    `seed` cleans them before the next test that uses it, but a test elsewhere
    (the loader's own suite) starts from what it finds. Fixture teardown is too
    early: the test's transaction still holds FK locks on `fiscal_parameter`
    through the stamps it wrote, and the delete would wait on them. This wrapper
    runs after every finalizer, including pytest-django's rollback.
    """
    yield
    if item.get_closest_marker("fiscal_regression") is None:
        return
    with psycopg.connect(
        admin_dsn(str(settings.DATABASES["default"]["NAME"])), autocommit=True
    ) as admin:
        admin.execute("SET lock_timeout = '5s'")
        clean_seeded_tables(admin, REFERENCE_TABLES)


@pytest.fixture
def book(
    seed: Callable[..., None],  # noqa: F811 -- the borrowed fixtures, found by name
    world: dict[str, uuid.UUID],  # noqa: F811
    company_of: Callable[..., uuid.UUID],  # noqa: F811
    grant_company: Callable[..., uuid.UUID],  # noqa: F811
) -> Book:
    tenant, user = world["tenant_a"], world["user_a"]
    company = company_of(tenant, "1002600000910", "Alpha Corpus")
    grant_company(tenant, company, user, user)
    seed_numbering(seed, tenant, company)
    load_shipped_conventions(user)
    accounts = {
        code: plan_account(
            seed, tenant, company, code, name, slots=("item",) if code == "811" else ()
        )
        for code, name in ACCOUNTS.items()
    }
    context = TenantContext(tenant_id=tenant, user_id=user, request_id="corpus")
    with tenant_context(context):
        year = open_fiscal_year(company, "2026", YEAR_START, YEAR_END)
        for role, code in ROLE_BINDINGS.items():
            AccountRoleBinding.objects.create(
                tenant_id=tenant,
                company_id=company,
                role=role,
                account_id=accounts[code],
                valid_from=YEAR_START,
                source="corpus",
            )
    return Book(
        tenant=tenant, company=company, user=user, year=year, context=context, accounts=accounts
    )
