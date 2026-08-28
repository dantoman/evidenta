"""The account declares what it carries -- ADR-048, the dimension half.

Every assertion here is about the **declaration**, never about which account
should carry what: the content is the owner's accounting decision, and every
fixture below uses codes no chart uses (`FIXTURE-*`).

**Under the application role, like every test in this suite** (T1). The rules
that matter most are the ones the database enforces -- contiguity, distinctness,
a requirement inside the declared set -- because the loader and the 1C importer
write past the service. Each of those is exercised by an UPDATE that bypasses
the service and is refused by the CHECK.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from django.db import IntegrityError, connection, transaction

from evidenta.accounting.coa.dimensions import DIMENSION_KEYS, SLOT_COUNT, SLOT_FIELDS
from evidenta.accounting.coa.errors import (
    DuplicateDimensionSlotError,
    RequiredDimensionNotCarriedError,
    TemplateDeclarationNarrowedError,
    TooManyDimensionSlotsError,
    UnknownDimensionError,
)
from evidenta.accounting.coa.models import CoaTemplateAccount, CompanyAccount
from evidenta.accounting.coa.services.accounts import create_subaccount, declare_dimension_slots
from evidenta.accounting.coa.services.chart import chart_version_of
from evidenta.accounting.coa.services.instantiation import instantiate_chart
from evidenta.platform.audit.models import AuditEvent
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.isolation.test_coa import seed_template

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

ON = date(2026, 3, 1)


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="slots")


@pytest.fixture
def company(
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> uuid.UUID:
    company_id = company_of(world["tenant_a"], "1002600000801", "Alpha Sloturi")
    grant_company(world["tenant_a"], company_id, world["user_a"], world["user_a"])
    return company_id


def own_account(
    seed: Callable[..., None], tenant: uuid.UUID, company: uuid.UUID, code: str = "FIXTURE-P"
) -> uuid.UUID:
    """A company-origin account that permits subaccounts, declaring nothing."""
    account_id = uuid.uuid4()
    seed(
        "INSERT INTO company_account (id, tenant_id, company_id, account_code,"
        " parent_id, origin, template_account_id, name_ro, account_class,"
        " normal_balance, allows_subaccounts, currency_tracking, quantity_tracking,"
        " required_dimensions, is_blocked, valid_from, valid_to, created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, NULL, 'company', NULL, %s, 'asset', 'debit',"
        " true, false, false, '{}'::text[], false, '2020-01-01', NULL, now(), now())",
        [account_id, tenant, company, code, f"Cont de fixture {code}"],
    )
    return account_id


# --- the vocabulary and the columns -----------------------------------------


def test_the_slot_columns_are_the_ones_the_vocabulary_names() -> None:
    """Written out on both models; tied to `SLOT_FIELDS` here rather than generated.

    Adding a fifth slot to one table and not the other, or renaming one, is a
    failure here and not a formula whose fourth value lands nowhere.
    """
    for model in (CoaTemplateAccount, CompanyAccount):
        names = {field.name for field in model._meta.get_fields()}
        assert set(SLOT_FIELDS) <= names, model.__name__
    assert SLOT_COUNT == 4 == len(SLOT_FIELDS)


# --- the service -------------------------------------------------------------


def test_a_subaccount_is_created_with_its_declaration(
    context: TenantContext, seed: Callable[..., None], company: uuid.UUID
) -> None:
    parent = own_account(seed, context.tenant_id, company)
    with tenant_context(context):
        account = create_subaccount(
            parent,
            "FIXTURE-P1",
            "Subcont cu sloturi",
            ON,
            dimension_slots=["partner", "contract"],
            required_dimensions=["partner"],
        )
        stored = CompanyAccount.objects.get(id=account.id)

    assert stored.declared_slots() == ("partner", "contract")
    assert stored.slot_3_dimension is None and stored.slot_4_dimension is None
    assert stored.required_dimensions == ["partner"]


def test_declaring_replaces_the_whole_declaration_and_is_audited(
    context: TenantContext, seed: Callable[..., None], company: uuid.UUID
) -> None:
    account = own_account(seed, context.tenant_id, company)
    with tenant_context(context):
        declare_dimension_slots(account, ["partner", "dim_1", "project"])
        declare_dimension_slots(account, ["dim_1"])
        stored = CompanyAccount.objects.get(id=account)
        audit = list(
            AuditEvent.objects.filter(
                action="coa.dimension_slots_declared", entity_id=account
            ).order_by("occurred_at")
        )

    assert stored.declared_slots() == ("dim_1",)
    assert len(audit) == 2
    assert audit[1].old_value == {"slots": ["partner", "dim_1", "project"], "required": []}
    assert audit[1].new_value == {"slots": ["dim_1"], "required": []}


def test_a_requirement_is_kept_across_a_redeclaration_that_still_carries_it(
    context: TenantContext, seed: Callable[..., None], company: uuid.UUID
) -> None:
    account = own_account(seed, context.tenant_id, company)
    with tenant_context(context):
        declare_dimension_slots(account, ["partner"], ["partner"])
        declare_dimension_slots(account, ["item", "partner"])
        stored = CompanyAccount.objects.get(id=account)
    assert stored.declared_slots() == ("item", "partner")
    assert stored.required_dimensions == ["partner"]


@pytest.mark.parametrize(
    ("slots", "required", "error"),
    [
        (["partner", "filiala"], None, UnknownDimensionError),
        (["partner", "item", "project", "contract", "asset"], None, TooManyDimensionSlotsError),
        (["partner", "partner"], None, DuplicateDimensionSlotError),
        (["partner"], ["item"], RequiredDimensionNotCarriedError),
        ([], ["partner"], RequiredDimensionNotCarriedError),
    ],
)
def test_the_service_refuses_a_declaration_the_database_would_refuse(
    context: TenantContext,
    seed: Callable[..., None],
    company: uuid.UUID,
    slots: list[str],
    required: list[str] | None,
    error: type[Exception],
) -> None:
    """Each with a code (C10); the CHECKs below are the barrier for everyone else."""
    account = own_account(seed, context.tenant_id, company)
    with tenant_context(context), pytest.raises(error):
        declare_dimension_slots(account, slots, required)


# --- the database --------------------------------------------------------------


def _update(account: uuid.UUID, **columns: Any) -> None:
    """Straight past the service, the way a data migration would go."""
    CompanyAccount.objects.filter(id=account).update(**columns)


def test_the_database_refuses_a_requirement_outside_the_slots(
    context: TenantContext, seed: Callable[..., None], company: uuid.UUID
) -> None:
    account = own_account(seed, context.tenant_id, company)
    with (
        tenant_context(context),
        pytest.raises(IntegrityError, match="company_account_required_within_slots"),
        transaction.atomic(),
    ):
        _update(account, required_dimensions=["partner"])


def test_the_database_refuses_a_hole_between_slots(
    context: TenantContext, seed: Callable[..., None], company: uuid.UUID
) -> None:
    account = own_account(seed, context.tenant_id, company)
    with (
        tenant_context(context),
        pytest.raises(IntegrityError, match="company_account_slot_2_contiguous"),
        transaction.atomic(),
    ):
        _update(account, slot_2_dimension="partner")


def test_the_database_refuses_one_dimension_in_two_positions(
    context: TenantContext, seed: Callable[..., None], company: uuid.UUID
) -> None:
    account = own_account(seed, context.tenant_id, company)
    with (
        tenant_context(context),
        pytest.raises(IntegrityError, match="company_account_slot_1_2_distinct"),
        transaction.atomic(),
    ):
        _update(account, slot_1_dimension="partner", slot_2_dimension="partner")


def test_the_database_refuses_a_slot_outside_the_vocabulary(
    context: TenantContext, seed: Callable[..., None], company: uuid.UUID
) -> None:
    account = own_account(seed, context.tenant_id, company)
    with (
        tenant_context(context),
        pytest.raises(IntegrityError, match="company_account_slot_1_known"),
        transaction.atomic(),
    ):
        _update(account, slot_1_dimension="filiala")


def test_slot_columns_are_byte_ordered_codes(context: TenantContext) -> None:
    """C34: a slot holds a key from the vocabulary, not a name a person reads."""
    with tenant_context(context), connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT c.relname, a.attname, coll.collname
              FROM pg_attribute a
              JOIN pg_class c ON c.oid = a.attrelid
              JOIN pg_collation coll ON coll.oid = a.attcollation
             WHERE c.relname IN ('company_account', 'coa_template_account')
               AND a.attname LIKE 'slot\\_%\\_dimension'
            """
        )
        rows = cursor.fetchall()
    assert len(rows) == 2 * SLOT_COUNT
    assert {row[2] for row in rows} == {"C"}


# --- the template and the company -----------------------------------------------


def test_instantiation_copies_the_plans_declaration(
    context: TenantContext,
    seed: Callable[..., None],
    company: uuid.UUID,
) -> None:
    """The template's slots arrive on the company account like every other column."""
    template = seed_template(seed)
    seed(
        "INSERT INTO coa_template_account (id, template_id, account_code, parent_code,"
        " name_ro, account_class, normal_balance, is_system, allows_subaccounts,"
        " currency_tracking, quantity_tracking, required_dimensions,"
        " slot_1_dimension, slot_2_dimension, valid_from, created_at)"
        " VALUES (%s, %s, 'FIXTURE-T', NULL, 'Cont sablon', 'asset', 'debit', true, true,"
        " false, false, '{partner}'::text[], 'partner', 'contract', '2020-01-01', now())",
        [uuid.uuid4(), template],
    )
    with tenant_context(context):
        instantiate_chart(company, template)
        account = CompanyAccount.objects.get(company_id=company, account_code="FIXTURE-T")
        version = chart_version_of(company)

    assert account.declared_slots() == ("partner", "contract")
    assert account.required_dimensions == ["partner"]
    assert version is not None and version.template_id == template


def test_a_company_may_extend_a_system_account_but_not_narrow_it(
    context: TenantContext, seed: Callable[..., None], company: uuid.UUID
) -> None:
    """ADR-036 section 6.3: the company adds its analytics on top of the plan's."""
    template = seed_template(seed)
    seed(
        "INSERT INTO coa_template_account (id, template_id, account_code, parent_code,"
        " name_ro, account_class, normal_balance, is_system, allows_subaccounts,"
        " currency_tracking, quantity_tracking, required_dimensions,"
        " slot_1_dimension, valid_from, created_at)"
        " VALUES (%s, %s, 'FIXTURE-S', NULL, 'Cont de sistem', 'asset', 'debit', true, false,"
        " false, false, '{partner}'::text[], 'partner', '2020-01-01', now())",
        [uuid.uuid4(), template],
    )
    with tenant_context(context):
        instantiate_chart(company, template)
        account = CompanyAccount.objects.get(company_id=company, account_code="FIXTURE-S")

        extended = declare_dimension_slots(account.id, ["partner", "dim_2"], ["partner"])
        assert extended.declared_slots() == ("partner", "dim_2")

        with pytest.raises(TemplateDeclarationNarrowedError):
            declare_dimension_slots(account.id, ["dim_2"], [])
        with pytest.raises(TemplateDeclarationNarrowedError):
            declare_dimension_slots(account.id, ["partner", "dim_2"], [])


def test_nothing_in_the_shipped_chart_declares_anything(
    context: TenantContext, seed: Callable[..., None], company: uuid.UUID
) -> None:
    """Delivered with the declarations empty -- the instruction's own words.

    Which accounts carry which dimensions is the owner's decision. This pins the
    data file: a declaration that appears there arrives through the loader, with
    the act beside it, and this test is edited in the same commit.
    """
    import csv
    from pathlib import Path

    data = Path(__file__).resolve().parents[2] / "evidenta/accounting/coa/data/snc_2020.csv"
    with data.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows, data
    assert all(not row.get("dimension_slots") for row in rows)
    assert all(not row.get("required_dimensions") for row in rows)
    assert set(DIMENSION_KEYS) >= {"partner", "dim_1"}
