"""The chart of accounts -- F1.1, Spec B section 2.

**No real account appears in this file.** The content of the SNC chart is `OD-23`
and needs the order that approves it, cited; a fixture that invented plausible
codes would be that content arriving through the back door, and the first person
to read it would take it for the real thing. So the template here uses codes no
published chart uses (`T1`, `T11`, `T2`) and names that say they are a fixture.

What is tested is the structure: two levels, instantiation, what a company may do
to its own chart, and the two things that must be impossible -- writing to the
global template, and deleting an account.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from django.db import connection, transaction
from django.db.utils import ProgrammingError

from evidenta.accounting.coa.errors import (
    AccountCodeTakenError,
    ChartAlreadyInstantiatedError,
    CompanyNotVisibleError,
    InvalidValidityWindowError,
    ParentAccountClosedError,
    SubaccountsNotAllowedError,
    SystemAccountImmutableError,
    TemplateNotPublishedError,
    UnknownDimensionError,
)
from evidenta.accounting.coa.models import (
    AccountClass,
    AccountOrigin,
    CoaTemplate,
    CompanyAccount,
    CompanyChart,
    NormalBalance,
    TemplateStatus,
)
from evidenta.accounting.coa.services.accounts import (
    close_account,
    create_subaccount,
    postable_accounts,
    rename_account,
    set_blocked,
)
from evidenta.accounting.coa.services.instantiation import instantiate_chart
from evidenta.platform.audit.models import AuditEvent
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])


def seed_template(
    seed: Callable[..., None],
    code: str = "TEST",
    version: str = "1",
    *,
    status: str = TemplateStatus.PUBLISHED,
    valid_from: str = "2020-01-01",
    valid_to: str | None = None,
) -> uuid.UUID:
    template_id = uuid.uuid4()
    seed(
        "INSERT INTO coa_template (id, code, version, valid_from, valid_to,"
        " source_act, source_reference, published_at, status, created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, %s, 'Fixture, not a normative act', 'n/a',"
        " '2019-12-01', %s, now(), now())",
        [template_id, code, version, valid_from, valid_to, status],
    )
    return template_id


def seed_account(seed: Callable[..., None], template_id: uuid.UUID, **kwargs: Any) -> uuid.UUID:
    row: dict[str, Any] = {
        "account_code": "T1",
        "parent_code": None,
        "name_ro": "Cont de fixture, nivel unu",
        "account_class": AccountClass.ASSET,
        "normal_balance": NormalBalance.DEBIT,
        "is_system": True,
        "allows_subaccounts": True,
        "currency_tracking": False,
        "quantity_tracking": False,
        "required_dimensions": [],
        "valid_from": date(2020, 1, 1),
        "valid_to": None,
    }
    row.update(kwargs)
    # What the account requires it also carries (ADR-048): the plan may not demand
    # an axis it does not declare, and the CHECK says so for a fixture too.
    slots = [*row["required_dimensions"], None, None, None, None][:4]
    account_id = uuid.uuid4()
    seed(
        "INSERT INTO coa_template_account (id, template_id, account_code, parent_code,"
        " name_ro, account_class, normal_balance, is_system, allows_subaccounts,"
        " currency_tracking, quantity_tracking, required_dimensions, valid_from,"
        " valid_to, slot_1_dimension, slot_2_dimension, slot_3_dimension,"
        " slot_4_dimension, created_at)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())",
        [account_id, template_id, *row.values(), *slots],
    )
    return account_id


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="coa")


@pytest.fixture
def company(
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> uuid.UUID:
    company_id = company_of(world["tenant_a"], "1002600000101", "Alpha Contabil")
    grant_company(world["tenant_a"], company_id, world["user_a"], world["user_a"])
    return company_id


@pytest.fixture
def template(seed: Callable[..., None]) -> uuid.UUID:
    """Three accounts, with the child inserted *before* its parent.

    Deliberate: inside a template the hierarchy is a code, and the published act
    does not promise parents come first. A loader that relied on insertion order
    would pass a fixture written the tidy way and fail on the real thing.
    """
    template_id = seed_template(seed)
    seed_account(
        seed,
        template_id,
        account_code="T11",
        parent_code="T1",
        name_ro="Subcont de fixture",
        allows_subaccounts=False,
        required_dimensions=["partner"],
    )
    seed_account(seed, template_id, account_code="T1")
    seed_account(
        seed,
        template_id,
        account_code="T2",
        name_ro="Cont de fixture, venituri",
        account_class=AccountClass.INCOME,
        normal_balance=NormalBalance.CREDIT,
        allows_subaccounts=True,
    )
    return template_id


# --- the two levels ---------------------------------------------------------


def test_the_template_is_readable_by_every_tenant(
    world: dict[str, uuid.UUID], template: uuid.UUID
) -> None:
    """Global reference data: the same published chart for everyone.

    Same shape as `counterparty_registry` and `fiscal_parameter` -- one law, one
    row, no tenant column.
    """
    for tenant_key, user_key in (("tenant_a", "user_a"), ("tenant_b", "user_b")):
        ctx = TenantContext(tenant_id=world[tenant_key], user_id=world[user_key], request_id="coa")
        with tenant_context(ctx):
            assert CoaTemplate.objects.filter(id=template).exists()


def test_a_tenant_cannot_write_to_the_template(context: TenantContext) -> None:
    """A tenant that could publish a chart version would publish it for everyone.

    The refusal is a missing privilege, not a missing policy: `0001_roles.sql`
    grants INSERT implicitly on every table the owner creates, so without the
    explicit REVOKE the only thing stopping this would be the absence of an
    INSERT policy -- and a later migration adding one for another reason would
    have opened writes silently (`OD-47`).
    """
    with (
        tenant_context(context),
        pytest.raises(ProgrammingError, match="permission denied"),
        transaction.atomic(),
    ):
        CoaTemplate.objects.create(
            code="X", version="1", valid_from=date(2020, 1, 1), source_act="none"
        )


def test_two_published_versions_may_not_overlap(seed: Callable[..., None]) -> None:
    """One published chart in force on a date, or the question has two answers.

    In the service this would be a check the bulk loader walks past; here it is
    not.
    """
    seed_template(seed, code="OVL", version="1", valid_from="2020-01-01", valid_to="2024-01-01")

    with pytest.raises(Exception) as excinfo:
        seed_template(seed, code="OVL", version="2", valid_from="2023-01-01")
    assert "coa_template_no_overlap" in str(excinfo.value)


def test_a_draft_may_overlap_a_published_version(seed: Callable[..., None]) -> None:
    """Preparing next year's chart necessarily overlaps this year's.

    The constraint is partial for that reason. Blocking it would push the
    preparation of every legislative change outside the system.
    """
    seed_template(seed, code="DRF", version="1", valid_from="2020-01-01")
    seed_template(seed, code="DRF", version="2", valid_from="2021-01-01", status="draft")


# --- instantiation ----------------------------------------------------------


def test_instantiation_copies_every_account_and_resolves_parents(
    context: TenantContext, company: uuid.UUID, template: uuid.UUID
) -> None:
    with tenant_context(context):
        chart = instantiate_chart(company, template)

        accounts = {a.account_code: a for a in CompanyAccount.objects.filter(company_id=company)}
        assert set(accounts) == {"T1", "T11", "T2"}
        assert all(a.origin == AccountOrigin.SYSTEM for a in accounts.values())
        assert all(a.template_account_id is not None for a in accounts.values())

        # Resolved despite the child being inserted first.
        assert accounts["T11"].parent_id == accounts["T1"].id
        assert accounts["T1"].parent_id is None

        # Copied, not read through: what the account *was* has to survive a later
        # template version reclassifying it.
        assert accounts["T2"].account_class == AccountClass.INCOME
        assert accounts["T2"].normal_balance == NormalBalance.CREDIT
        assert accounts["T11"].required_dimensions == ["partner"]

        assert chart.template_id == template
        assert chart.last_propagation_at is None


def test_a_non_system_template_account_becomes_a_renameable_one(
    context: TenantContext, company: uuid.UUID, seed: Callable[..., None]
) -> None:
    """``is_system`` on the template is where ``origin`` comes from.

    The two columns are one fact written in two places -- section 2.2 puts the
    flag on the template account, section 2.4 contrasts the same two kinds on the
    company side. Wiring them is what keeps the flag from being a column nobody
    reads, which is a rule promised and not enforced.

    The link back to the template survives, so propagation still finds the row.
    """
    template_id = seed_template(seed, code="SUGG")
    seed_account(seed, template_id, account_code="S1", is_system=False)

    with tenant_context(context):
        instantiate_chart(company, template_id)

        row = account(company, "S1")
        assert row.origin == AccountOrigin.COMPANY
        assert row.template_account_id is not None
        assert rename_account(row.id, "Redenumit de companie").name_ro == "Redenumit de companie"


def test_a_company_has_exactly_one_chart(
    context: TenantContext, company: uuid.UUID, template: uuid.UUID
) -> None:
    with tenant_context(context):
        instantiate_chart(company, template)
        with pytest.raises(ChartAlreadyInstantiatedError) as excinfo:
            instantiate_chart(company, template)
    assert excinfo.value.code == "coa.chart_already_instantiated"


def test_a_draft_template_is_not_instantiated(
    context: TenantContext, company: uuid.UUID, seed: Callable[..., None]
) -> None:
    draft = seed_template(seed, code="DRAFT", status=TemplateStatus.DRAFT)
    seed_account(seed, draft)

    with tenant_context(context), pytest.raises(TemplateNotPublishedError) as excinfo:
        instantiate_chart(company, draft)
    assert excinfo.value.code == "coa.template_not_published"


def test_a_company_of_another_tenant_is_not_visible(
    context: TenantContext,
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    template: uuid.UUID,
) -> None:
    """Naming a company id is not reaching it.

    The refusal is `not visible`, not `forbidden` -- IZ-04. A distinct answer here
    would confirm that the id exists in some other tenant.
    """
    foreign = company_of(world["tenant_b"], "1002600000102", "Beta Contabil")

    with tenant_context(context), pytest.raises(CompanyNotVisibleError) as excinfo:
        instantiate_chart(foreign, template)
    assert excinfo.value.code == "coa.company_not_visible"

    with tenant_context(context):
        assert not CompanyChart.objects.filter(company_id=foreign).exists()


def test_one_tenants_chart_is_invisible_to_another(
    context: TenantContext,
    world: dict[str, uuid.UUID],
    company: uuid.UUID,
    template: uuid.UUID,
) -> None:
    with tenant_context(context):
        instantiate_chart(company, template)
        assert CompanyAccount.objects.count() == 3

    other = TenantContext(tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="coa")
    with tenant_context(other):
        assert CompanyAccount.objects.count() == 0
        assert CompanyChart.objects.count() == 0


# --- what the company may do to its own chart -------------------------------


@pytest.fixture
def chart(context: TenantContext, company: uuid.UUID, template: uuid.UUID) -> uuid.UUID:
    with tenant_context(context):
        instantiate_chart(company, template)
    return company


def account(company_id: uuid.UUID, code: str) -> CompanyAccount:
    return CompanyAccount.objects.get(company_id=company_id, account_code=code)


def test_a_subaccount_inherits_class_and_normal_balance(
    context: TenantContext, chart: uuid.UUID
) -> None:
    """Not passed by the caller, so it cannot be passed wrongly.

    A subaccount rolls up into its parent; one classified differently would make
    the roll-up mean nothing.
    """
    with tenant_context(context):
        parent = account(chart, "T2")
        child = create_subaccount(parent.id, "T2-A", "Subcont propriu", date(2026, 1, 1))

        assert child.origin == AccountOrigin.COMPANY
        assert child.template_account_id is None
        assert child.account_class == AccountClass.INCOME
        assert child.normal_balance == NormalBalance.CREDIT
        assert child.parent_id == parent.id
        # Nesting deeper is a decision, not a default.
        assert child.allows_subaccounts is False


def test_a_subaccount_is_refused_under_an_account_that_forbids_them(
    context: TenantContext, chart: uuid.UUID
) -> None:
    with tenant_context(context):
        parent = account(chart, "T11")
        with pytest.raises(SubaccountsNotAllowedError) as excinfo:
            create_subaccount(parent.id, "T11-A", "Nu se poate", date(2026, 1, 1))
    assert excinfo.value.code == "coa.subaccounts_not_allowed"


def test_a_code_is_unique_within_the_company(context: TenantContext, chart: uuid.UUID) -> None:
    with tenant_context(context):
        parent = account(chart, "T1")
        with pytest.raises(AccountCodeTakenError) as excinfo:
            create_subaccount(parent.id, "T2", "Cod deja folosit", date(2026, 1, 1))
    assert excinfo.value.code == "coa.account_code_taken"


def test_a_subaccount_cannot_start_after_its_parent_closed(
    context: TenantContext, chart: uuid.UUID
) -> None:
    with tenant_context(context):
        parent = close_account(account(chart, "T1").id, date(2026, 1, 1))
        with pytest.raises(ParentAccountClosedError) as excinfo:
            create_subaccount(parent.id, "T1-A", "Prea tarziu", date(2026, 6, 1))
    assert excinfo.value.code == "coa.parent_account_closed"


def test_a_dimension_outside_the_vocabulary_is_refused(
    context: TenantContext, chart: uuid.UUID
) -> None:
    """ADR-029 closed the list. A name outside it names no column.

    The account would exist and every posting to it would be refused, with the
    cause looked for in the posting.
    """
    with tenant_context(context):
        parent = account(chart, "T1")
        with pytest.raises(UnknownDimensionError) as excinfo:
            create_subaccount(
                parent.id,
                "T1-B",
                "Dimensiune inventata",
                date(2026, 1, 1),
                required_dimensions=["vehicle"],
            )
    assert excinfo.value.code == "coa.unknown_dimension"


def test_the_five_generic_slots_are_accepted(context: TenantContext, chart: uuid.UUID) -> None:
    with tenant_context(context):
        parent = account(chart, "T1")
        child = create_subaccount(
            parent.id,
            "T1-C",
            "Slot generic",
            date(2026, 1, 1),
            required_dimensions=["dim_1", "partner"],
            # Required is a subset of carried (ADR-048), so the declaration
            # comes with it.
            dimension_slots=["dim_1", "partner"],
        )
        assert child.required_dimensions == ["dim_1", "partner"]
        assert child.declared_slots() == ("dim_1", "partner")


def test_a_system_account_is_not_renamed_locally(context: TenantContext, chart: uuid.UUID) -> None:
    """The name comes from the act. Renaming it locally makes one company's
    trial balance unreadable against everybody else's -- and would force the
    propagation policy (`OD-03`) to decide whether a central rename wins.
    """
    with tenant_context(context), pytest.raises(SystemAccountImmutableError) as excinfo:
        rename_account(account(chart, "T1").id, "Alt nume")
    assert excinfo.value.code == "coa.system_account_immutable"


def test_a_company_subaccount_is_renamed(context: TenantContext, chart: uuid.UUID) -> None:
    with tenant_context(context):
        child = create_subaccount(account(chart, "T1").id, "T1-D", "Nume vechi", date(2026, 1, 1))
        renamed = rename_account(child.id, "Nume nou")
        assert renamed.name_ro == "Nume nou"


def test_a_system_account_may_still_be_blocked(context: TenantContext, chart: uuid.UUID) -> None:
    """Blocking is the company's decision about its own bookkeeping.

    It says nothing about what the account is, which is why it is allowed where
    renaming is not.
    """
    with tenant_context(context):
        blocked = set_blocked(account(chart, "T1").id, True)
        assert blocked.is_blocked is True
        assert set_blocked(blocked.id, False).is_blocked is False


def test_closing_before_the_account_started_is_refused(
    context: TenantContext, chart: uuid.UUID
) -> None:
    with tenant_context(context), pytest.raises(InvalidValidityWindowError) as excinfo:
        close_account(account(chart, "T1").id, date(2019, 1, 1))
    assert excinfo.value.code == "coa.invalid_validity_window"


# --- nothing is ever deleted ------------------------------------------------


def test_the_application_role_cannot_delete_an_account(
    context: TenantContext, chart: uuid.UUID
) -> None:
    """The barrier that survives the importer.

    A journal line references an account with no foreign key (R21), and the
    ledger is append-only -- so a deleted account makes its own history
    unreadable. The service offers no delete, which stops the ordinary path; this
    stops the 1C importer and any data migration, which are the paths that
    actually mangle a chart.
    """
    with tenant_context(context):
        target = account(chart, "T1").id
        with (
            pytest.raises(ProgrammingError, match="permission denied"),
            transaction.atomic(),
            connection.cursor() as cursor,
        ):
            cursor.execute("DELETE FROM company_account WHERE id = %s", [target])

        assert CompanyAccount.objects.filter(id=target).exists()


def test_the_application_role_cannot_delete_a_chart(
    context: TenantContext, chart: uuid.UUID
) -> None:
    with tenant_context(context):
        with (
            pytest.raises(ProgrammingError, match="permission denied"),
            transaction.atomic(),
            connection.cursor() as cursor,
        ):
            cursor.execute("DELETE FROM company_chart WHERE company_id = %s", [chart])

        assert CompanyChart.objects.filter(company_id=chart).exists()


# --- the chart as the posting engine will read it ---------------------------


def test_postable_accounts_answer_for_a_date_and_never_for_today(
    context: TenantContext, chart: uuid.UUID
) -> None:
    """The date is a parameter, and the clock is never read.

    A resolver that could fall back to "today" would answer a recalculation of a
    closed period with this year's chart -- silently, and looking correct. R18.
    """
    with tenant_context(context):
        close_account(account(chart, "T2").id, date(2026, 1, 1))
        set_blocked(account(chart, "T11").id, True)

        before = [a.account_code for a in postable_accounts(chart, date(2025, 6, 1))]
        after = [a.account_code for a in postable_accounts(chart, date(2026, 6, 1))]

        assert before == ["T1", "T2"]
        # T2 stopped being valid; T11 is blocked in both.
        assert after == ["T1"]


def test_the_window_is_half_open(context: TenantContext, chart: uuid.UUID) -> None:
    """``[valid_from, valid_to)``. The last day is the day before ``valid_to``.

    Written down because the two halves of the product must not drift: the same
    window decides which fiscal parameter applies, and an inclusive end in one of
    them would differ on exactly one day a year.
    """
    with tenant_context(context):
        close_account(account(chart, "T2").id, date(2026, 1, 1))

        assert "T2" in [a.account_code for a in postable_accounts(chart, date(2025, 12, 31))]
        assert "T2" not in [a.account_code for a in postable_accounts(chart, date(2026, 1, 1))]


# --- who changed the chart --------------------------------------------------


def test_blocking_an_account_leaves_an_attributable_trace(
    context: TenantContext, chart: uuid.UUID
) -> None:
    """The question asked months later, when a report changed shape.

    Row timestamps say the row changed. They do not say who changed it, or what
    it was before -- and "the trial balance used to have this line" is answered by
    the second half, not the first.
    """
    with tenant_context(context):
        target = account(chart, "T1")
        set_blocked(target.id, True)

        events = AuditEvent.objects.filter(entity_id=target.id, action="coa.account_blocked")
        assert events.count() == 1
        event = events.get()
        assert event.old_value == {"is_blocked": False}
        assert event.new_value == {"is_blocked": True}
        assert event.actor_user_id == context.user_id


def test_instantiation_records_which_version_was_chosen(
    context: TenantContext, company: uuid.UUID, template: uuid.UUID
) -> None:
    """Which published version a company was built on decides how every later
    posting reads. Inferring it from row timestamps is not the same as recording
    it.
    """
    with tenant_context(context):
        instantiate_chart(company, template)

        event = AuditEvent.objects.get(action="coa.chart_instantiated")
        assert event.new_value == {
            "template_id": str(template),
            "template": "TEST/1",
            "accounts": 3,
        }
