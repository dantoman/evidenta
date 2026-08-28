"""The formula as the unit of posting -- ADR-048, the engine half.

What is asserted is **shape**, never treatment: which side keeps which
dimension, what folds into what, that two lines come out of every formula, and
that the header says what the posting stood on. No account code from any chart
appears (`FIXTURE-*`), no role is bound to a real subaccount, and no rule of
correspondence is implied -- the formulas below are test material, marked as such
by their accounts.

**Under the application role, like every test in this suite** (T1). The reads
the engine makes -- the chart, the period, the numbering template, the bindings
-- go through the same policies a request does.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import psycopg
import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction

from evidenta.accounting.ledger.models import (
    EntryStatus,
    JournalEntry,
    JournalFormula,
    JournalLine,
)
from evidenta.accounting.ledger.services.reversal import reverse_entry
from evidenta.accounting.ledger.services.writing import (
    FormulaToWrite,
    LineToWrite,
    TooManyFormulaSlotsError,
    post_entry,
)
from evidenta.accounting.posting.dimensions import MissingRequiredDimensionError
from evidenta.accounting.posting.formula import (
    DimensionValue,
    Formula,
    FormulaMalformedError,
    FormulaSlotsExceededError,
    NoFormulasError,
    RoleFormula,
    bind_roles,
    merge,
    place,
)
from evidenta.accounting.posting.invariants import AccountNotPostableError, Origin
from evidenta.accounting.posting.services.formulas import post_formulas
from evidenta.accounting.posting.services.manual import post_manual_entry
from evidenta.accounting.slots.catalogue import ROLES
from evidenta.accounting.slots.models import AccountRoleBinding
from evidenta.accounting.slots.services.binding import RoleNotBoundError
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.isolation.test_ledger import seed_event, seed_period
from tests.isolation.test_manual_entry import seed_template as seed_numbering

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

POSTING = date(2026, 1, 15)
MDL = "MDL"
RULE = "fixture.formula.v1"

SNAPSHOT: dict[str, Any] = {"version": 1, "on": POSTING.isoformat(), "activated": [], "usable": []}


# --- the world ---------------------------------------------------------------


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="formula")


def seed_account(
    seed: Callable[..., None],
    tenant: uuid.UUID,
    company: uuid.UUID,
    code: str,
    *,
    slots: Sequence[str] = (),
    requires: Sequence[str] = (),
) -> uuid.UUID:
    """One account of the company's own, declaring `slots`, demanding `requires`."""
    account_id = uuid.uuid4()
    padded: list[str | None] = [*slots, None, None, None, None][:4]
    seed(
        "INSERT INTO company_account (id, tenant_id, company_id, account_code,"
        " parent_id, origin, template_account_id, name_ro, account_class,"
        " normal_balance, allows_subaccounts, currency_tracking, quantity_tracking,"
        " required_dimensions, slot_1_dimension, slot_2_dimension, slot_3_dimension,"
        " slot_4_dimension, is_blocked, valid_from, valid_to, created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, NULL, 'company', NULL, %s, 'asset', 'debit',"
        " false, false, false, %s::text[], %s, %s, %s, %s, false, '2020-01-01', NULL,"
        " now(), now())",
        [account_id, tenant, company, code, f"Cont de fixture {code}", list(requires), *padded],
    )
    return account_id


@pytest.fixture
def scene(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> dict[str, Any]:
    """One company, one open month, a numbering template, and four accounts.

    ``receivable`` carries partner and contract and demands partner; ``revenue``
    carries item; ``vat`` and ``cost`` carry nothing. Fixture declarations, not
    the plan's -- the plan's are the owner's to make.
    """
    tenant = world["tenant_a"]
    company = company_of(tenant, "1002600000901", "Alpha Formule")
    grant_company(tenant, company, world["user_a"], world["user_a"])
    _, period = seed_period(seed, tenant, company)
    seed_numbering(seed, tenant, company)
    return {
        "tenant": tenant,
        "company": company,
        "user": world["user_a"],
        "period": period,
        "receivable": seed_account(
            seed, tenant, company, "FIXTURE-R", slots=("partner", "contract"), requires=("partner",)
        ),
        "revenue": seed_account(seed, tenant, company, "FIXTURE-V", slots=("item",)),
        "vat": seed_account(seed, tenant, company, "FIXTURE-T"),
        "cost": seed_account(seed, tenant, company, "FIXTURE-C"),
        "partner": uuid.uuid4(),
        "contract": uuid.uuid4(),
        "item": uuid.uuid4(),
    }


def formula(
    debit: uuid.UUID,
    credit: uuid.UUID,
    amount: str,
    *,
    dimensions: Sequence[DimensionValue] = (),
    vat_rate: str | None = None,
    currency: str = MDL,
    rate: str = "1",
    amount_currency: str | None = None,
    **extra: Any,
) -> Formula:
    return Formula(
        debit_account_id=debit,
        credit_account_id=credit,
        amount=Decimal(amount),
        currency=currency,
        amount_currency=Decimal(amount_currency or amount),
        exchange_rate=Decimal(rate),
        rate_date=POSTING,
        document_date=POSTING,
        dimensions=tuple(dimensions),
        vat_rate=Decimal(vat_rate) if vat_rate is not None else None,
        **extra,
    )


def post(
    scene: dict[str, Any], formulas: Sequence[Formula], seed: Callable[..., None]
) -> uuid.UUID:
    event = seed_event(seed, scene["tenant"], scene["company"], scene["user"])
    result = post_formulas(
        tenant_id=scene["tenant"],
        company_id=scene["company"],
        accounting_date=POSTING,
        functional_currency=MDL,
        accounting_event_id=event,
        origin=Origin(module="manual", document_type="fixture", document_id=uuid.uuid4()),
        rule_ref=RULE,
        description="Formule de fixture",
        request_id="formula",
        actor_user_id=scene["user"],
        formulas=formulas,
    )
    assert result.lines == 2 * result.formulas
    return result.journal_entry_id


# --- n formulas, 2n lines, one header ------------------------------------------


def test_every_formula_becomes_two_lines_and_the_header_says_what_it_stood_on(
    context: TenantContext, scene: dict[str, Any], seed: Callable[..., None]
) -> None:
    """A delivery and its VAT: two correspondences, four lines, one entry.

    The number is not fixed anywhere -- the same call with one formula or three
    posts one entry of two or six lines, which is the property ADR-048 asks for.
    """
    partner = DimensionValue("partner", scene["partner"])
    with tenant_context(context):
        entry_id = post(
            scene,
            [
                formula(scene["receivable"], scene["revenue"], "100", dimensions=[partner]),
                formula(
                    scene["receivable"], scene["vat"], "20", dimensions=[partner], vat_rate="20"
                ),
            ],
            seed,
        )
        entry = JournalEntry.objects.get(id=entry_id)
        formulas = list(
            JournalFormula.objects.filter(journal_entry_id=entry_id).order_by("formula_number")
        )
        lines = list(JournalLine.objects.filter(journal_entry_id=entry_id).order_by("line_number"))

    assert entry.status == EntryStatus.POSTED
    assert entry.rule_ref == RULE
    assert entry.fiscal_effective_date == POSTING
    assert entry.chart_template_id is None  # fixture accounts, no template
    assert entry.total_debit == entry.total_credit == Decimal("120.0000")

    assert [f.formula_number for f in formulas] == [1, 2]
    assert [f.amount for f in formulas] == [Decimal("100.0000"), Decimal("20.0000")]
    assert formulas[1].vat_rate == Decimal("20.0000") and formulas[0].vat_rate is None

    assert [(line.line_number, line.debit, line.credit) for line in lines] == [
        (1, Decimal("100.0000"), Decimal(0)),
        (2, Decimal(0), Decimal("100.0000")),
        (3, Decimal("20.0000"), Decimal(0)),
        (4, Decimal(0), Decimal("20.0000")),
    ]
    assert [line.account_id for line in lines] == [
        scene["receivable"],
        scene["revenue"],
        scene["receivable"],
        scene["vat"],
    ]


def test_the_chart_version_is_stamped_when_the_company_has_one(
    context: TenantContext, scene: dict[str, Any], seed: Callable[..., None]
) -> None:
    """The one stamp that cannot be re-derived after propagation (`OD-03`)."""
    from tests.isolation.test_coa import seed_template

    template = seed_template(seed, code="FIXTURE", version="9")
    seed(
        "INSERT INTO company_chart (id, tenant_id, company_id, template_id, instantiated_at,"
        " last_propagation_at) VALUES (%s, %s, %s, %s, now(), NULL)",
        [uuid.uuid4(), scene["tenant"], scene["company"], template],
    )
    partner = DimensionValue("partner", scene["partner"])
    with tenant_context(context):
        entry_id = post(
            scene, [formula(scene["receivable"], scene["vat"], "5", dimensions=[partner])], seed
        )
        entry = JournalEntry.objects.get(id=entry_id)
    assert entry.chart_template_id == template


# --- placement: each side keeps what its account declares -----------------------


def test_each_side_keeps_the_dimensions_its_account_declares(
    context: TenantContext, scene: dict[str, Any], seed: Callable[..., None]
) -> None:
    """The handler describes the fact; the chart says what the entity keeps.

    `receivable` carries partner and contract, `revenue` carries item, nobody
    carries warehouse. So the debit line has the first two, the credit line the
    third, the warehouse value lands nowhere -- and the stored formula holds the
    union, debit side's order first.
    """
    dims = [
        DimensionValue("warehouse", uuid.uuid4()),
        DimensionValue("item", scene["item"]),
        DimensionValue("contract", scene["contract"]),
        DimensionValue("partner", scene["partner"]),
    ]
    with tenant_context(context):
        entry_id = post(
            scene, [formula(scene["receivable"], scene["revenue"], "100", dimensions=dims)], seed
        )
        stored = JournalFormula.objects.get(journal_entry_id=entry_id)
        debit, credit = JournalLine.objects.filter(journal_entry_id=entry_id).order_by(
            "line_number"
        )

    assert (stored.slot_1_dimension, stored.slot_1_value_id) == ("partner", scene["partner"])
    assert (stored.slot_2_dimension, stored.slot_2_value_id) == ("contract", scene["contract"])
    assert (stored.slot_3_dimension, stored.slot_3_value_id) == ("item", scene["item"])
    assert stored.slot_4_dimension is None and stored.slot_4_value_id is None

    assert (debit.partner_id, debit.contract_id, debit.item_id) == (
        scene["partner"],
        scene["contract"],
        None,
    )
    assert (credit.partner_id, credit.contract_id, credit.item_id) == (None, None, scene["item"])
    assert debit.warehouse_id is None and credit.warehouse_id is None


def test_a_required_dimension_missing_on_its_side_is_refused(
    context: TenantContext, scene: dict[str, Any], seed: Callable[..., None]
) -> None:
    """`receivable` demands partner. A formula that names item only has nothing
    for the debit side, and the refusal is the account's rule, not the formula's.
    """
    with (
        tenant_context(context),
        pytest.raises(MissingRequiredDimensionError) as excinfo,
    ):
        post(
            scene,
            [
                formula(
                    scene["receivable"],
                    scene["revenue"],
                    "100",
                    dimensions=[DimensionValue("item", scene["item"])],
                )
            ],
            seed,
        )
    assert excinfo.value.code == "posting.missing_required_dimension"
    with tenant_context(context):
        assert not JournalEntry.objects.filter(company_id=scene["company"]).exists()


def test_more_than_four_carried_dimensions_between_the_two_sides_is_refused(
    context: TenantContext, scene: dict[str, Any], seed: Callable[..., None]
) -> None:
    """The visible, countable limit -- the row has four slots."""
    wide = seed_account(
        seed,
        scene["tenant"],
        scene["company"],
        "FIXTURE-W",
        slots=("project", "department", "cost_center", "employee"),
    )
    dims = [
        DimensionValue(name, uuid.uuid4())
        for name in ("project", "department", "cost_center", "employee", "item")
    ]
    with tenant_context(context), pytest.raises(FormulaSlotsExceededError) as excinfo:
        post(scene, [formula(wide, scene["revenue"], "1", dimensions=dims)], seed)
    assert excinfo.value.code == "posting.formula_slots_exceeded"


# --- merging ---------------------------------------------------------------------


def test_identical_correspondences_fold_into_one_and_distinct_ones_do_not(
    context: TenantContext, scene: dict[str, Any], seed: Callable[..., None]
) -> None:
    """Three document lines, one customer, two items.

    Revenue carries item, so the two items stay two formulas; the receivable
    side sees one partner three times and the VAT formulas -- no dimension either
    side keeps -- fold into one. What folds is decided by the declarations, which
    is the point: the same handler output merges differently at a company whose
    revenue account does not carry item.
    """
    partner = DimensionValue("partner", scene["partner"])
    item_a, item_b = DimensionValue("item", scene["item"]), DimensionValue("item", uuid.uuid4())
    with tenant_context(context):
        entry_id = post(
            scene,
            [
                formula(scene["receivable"], scene["revenue"], "10", dimensions=[partner, item_a]),
                formula(
                    scene["receivable"], scene["vat"], "2", dimensions=[partner], vat_rate="20"
                ),
                formula(scene["receivable"], scene["revenue"], "30", dimensions=[partner, item_a]),
                formula(
                    scene["receivable"], scene["vat"], "6", dimensions=[partner], vat_rate="20"
                ),
                formula(scene["receivable"], scene["revenue"], "5", dimensions=[partner, item_b]),
                formula(
                    scene["receivable"], scene["vat"], "1", dimensions=[partner], vat_rate="20"
                ),
            ],
            seed,
        )
        stored = list(
            JournalFormula.objects.filter(journal_entry_id=entry_id).order_by("formula_number")
        )
        entry = JournalEntry.objects.get(id=entry_id)
        lines = JournalLine.objects.filter(journal_entry_id=entry_id).count()

    assert [(f.credit_account_id, f.amount, f.slot_2_value_id) for f in stored] == [
        (scene["revenue"], Decimal("40.0000"), scene["item"]),
        (scene["vat"], Decimal("9.0000"), None),
        (scene["revenue"], Decimal("5.0000"), item_b.value_id),
    ]
    assert entry.total_debit == Decimal("54.0000")
    assert lines == 6


def test_merge_keeps_a_description_only_when_every_folded_formula_agrees() -> None:
    a = uuid.uuid4()
    b = uuid.uuid4()
    same = merge(
        place(
            [formula(a, b, "1", description="x"), formula(a, b, "2", description="x")],
            {},
            functional_currency=MDL,
        )
    )
    differ = merge(
        place(
            [formula(a, b, "1", description="x"), formula(a, b, "2", description="y")],
            {},
            functional_currency=MDL,
        )
    )
    assert len(same) == 1 and same[0].formula.description == "x"
    assert len(differ) == 1 and differ[0].formula.description is None
    assert differ[0].formula.amount == Decimal(3)


def test_the_merge_key_is_a_constraint_of_the_register(
    context: TenantContext, scene: dict[str, Any], seed: Callable[..., None]
) -> None:
    """Not a habit of one writer. Two formulas of one entry agreeing on the whole
    key -- NULLs included, which is what `nulls_distinct=False` is for -- are
    refused by the database, whoever writes them.
    """
    with tenant_context(context):
        event = seed_event(seed, scene["tenant"], scene["company"], scene["user"])
        entry = JournalEntry.objects.create(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            entry_number="NC-MERGE",
            accounting_date=POSTING,
            period_id=scene["period"],
            accounting_event_id=event,
            description="Probe",
            request_id="formula",
        )
        common = dict(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            accounting_date=POSTING,
            journal_entry=entry,
            debit_account_id=scene["receivable"],
            credit_account_id=scene["vat"],
            amount=Decimal(1),
            currency=MDL,
            amount_currency=Decimal(1),
            exchange_rate=Decimal(1),
            rate_date=POSTING,
            document_date=POSTING,
        )
        JournalFormula.objects.create(formula_number=1, **common)
        with (
            pytest.raises(IntegrityError, match="journal_formula_merge_key"),
            transaction.atomic(),
        ):
            JournalFormula.objects.create(formula_number=2, **common)


# --- shape refusals, before any read ---------------------------------------------


@pytest.mark.parametrize(
    "broken",
    [
        lambda s: formula(s["receivable"], s["receivable"], "1"),
        lambda s: formula(s["receivable"], s["vat"], "0"),
        lambda s: formula(s["receivable"], s["vat"], "-1"),
        lambda s: formula(s["receivable"], s["vat"], "1", rate="2"),
        lambda s: formula(s["receivable"], s["vat"], "1", amount_currency="2"),
        lambda s: formula(
            s["receivable"], s["vat"], "1", dimensions=[DimensionValue("filiala", uuid.uuid4())]
        ),
        lambda s: formula(
            s["receivable"],
            s["vat"],
            "1",
            dimensions=[
                DimensionValue("partner", uuid.uuid4()),
                DimensionValue("partner", uuid.uuid4()),
            ],
        ),
        lambda s: formula(s["receivable"], s["vat"], "1", quantity=Decimal(1)),
        lambda s: formula(s["receivable"], s["vat"], "1", vat_rate_key="vat.standard"),
        lambda s: formula(s["receivable"], s["vat"], "1", vat_rate="-20"),
    ],
    ids=[
        "same-account",
        "zero",
        "negative",
        "functional-at-rate-2",
        "functional-own-amount-differs",
        "unknown-dimension",
        "dimension-twice",
        "quantity-without-unit",
        "vat-key-without-rate",
        "negative-vat-rate",
    ],
)
def test_a_formula_that_is_not_a_correspondence_is_refused(
    context: TenantContext,
    scene: dict[str, Any],
    seed: Callable[..., None],
    broken: Callable[[dict[str, Any]], Formula],
) -> None:
    with tenant_context(context), pytest.raises(FormulaMalformedError) as excinfo:
        post(scene, [broken(scene)], seed)
    assert excinfo.value.code == "posting.formula_malformed"


def test_a_posting_with_no_formulas_is_refused(
    context: TenantContext, scene: dict[str, Any], seed: Callable[..., None]
) -> None:
    with tenant_context(context), pytest.raises(NoFormulasError):
        post(scene, [], seed)


def test_an_account_not_in_the_chart_is_refused_by_invariant_four(
    context: TenantContext, scene: dict[str, Any], seed: Callable[..., None]
) -> None:
    """Placement declares nothing for an unknown account; the invariant names it."""
    with tenant_context(context), pytest.raises(AccountNotPostableError):
        post(
            scene,
            [
                formula(
                    scene["receivable"],
                    uuid.uuid4(),
                    "1",
                    dimensions=[DimensionValue("partner", scene["partner"])],
                )
            ],
            seed,
        )


def test_a_foreign_currency_formula_is_carried_as_given(
    context: TenantContext, scene: dict[str, Any], seed: Callable[..., None]
) -> None:
    """Nothing here converts (`DNB-08`): the handler says 100 EUR at 19.5 is
    1950 MDL, and both lines carry all four numbers as given."""
    partner = DimensionValue("partner", scene["partner"])
    with tenant_context(context):
        entry_id = post(
            scene,
            [
                formula(
                    scene["receivable"],
                    scene["vat"],
                    "1950",
                    currency="EUR",
                    rate="19.5",
                    amount_currency="100",
                    dimensions=[partner],
                )
            ],
            seed,
        )
        lines = list(JournalLine.objects.filter(journal_entry_id=entry_id).order_by("line_number"))
    assert [(line.currency, line.amount_currency, line.exchange_rate) for line in lines] == [
        ("EUR", Decimal("100.0000"), Decimal("19.50000000")),
        ("EUR", Decimal("100.0000"), Decimal("19.50000000")),
    ]
    assert lines[0].debit == Decimal("1950.0000") == lines[1].credit


# --- the ledger's own barriers -----------------------------------------------------


def _line(account: uuid.UUID, *, debit: str = "0", credit: str = "0") -> LineToWrite:
    return LineToWrite(
        account_id=account,
        debit=Decimal(debit),
        credit=Decimal(credit),
        currency=MDL,
        amount_currency=Decimal(debit) + Decimal(credit),
        exchange_rate=Decimal(1),
        accounting_date=POSTING,
        document_date=POSTING,
        rate_date=POSTING,
    )


def _formula_to_write(debit: uuid.UUID, credit: uuid.UUID, amount: str) -> FormulaToWrite:
    return FormulaToWrite(
        debit_account_id=debit,
        credit_account_id=credit,
        amount=Decimal(amount),
        currency=MDL,
        amount_currency=Decimal(amount),
        exchange_rate=Decimal(1),
        rate_date=POSTING,
        document_date=POSTING,
    )


def test_formulas_and_lines_must_say_the_same_amount_at_commit(
    context: TenantContext, scene: dict[str, Any], seed: Callable[..., None]
) -> None:
    """The writer that skips the engine meets this: lines of 100, formulas of 90.

    Deferred, like the balance check, so it is forced with SET CONSTRAINTS
    IMMEDIATE the way `test_ledger` does -- inside the savepoint, because the
    refusal aborts the transaction.
    """
    event = seed_event(seed, scene["tenant"], scene["company"], scene["user"])
    with (
        tenant_context(context),
        pytest.raises(
            IntegrityError, match=r"formulas sum to 90\.0000 but its lines debit 100\.0000"
        ),
        transaction.atomic(),
    ):
        post_entry(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            entry_number="NC-SKEW",
            accounting_date=POSTING,
            period_id=scene["period"],
            accounting_event_id=event,
            description="Formule care nu spun ce spun liniile",
            request_id="formula",
            lines=[_line(scene["vat"], debit="100"), _line(scene["cost"], credit="100")],
            formulas=[_formula_to_write(scene["vat"], scene["cost"], "90")],
            rule_ref=RULE,
            fiscal_effective_date=POSTING,
            chart_template_id=None,
        )
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_an_entry_without_formulas_is_still_a_legitimate_shape(
    context: TenantContext, scene: dict[str, Any], seed: Callable[..., None]
) -> None:
    """The manual note writes lines only, and the commit check lets it through."""
    event = seed_event(seed, scene["tenant"], scene["company"], scene["user"])
    with tenant_context(context), transaction.atomic():
        entry_id = post_entry(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            entry_number="NC-LINES",
            accounting_date=POSTING,
            period_id=scene["period"],
            accounting_event_id=event,
            description="Doar linii",
            request_id="formula",
            lines=[_line(scene["vat"], debit="100"), _line(scene["cost"], credit="100")],
            rule_ref=RULE,
            fiscal_effective_date=POSTING,
            chart_template_id=None,
        )
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        assert JournalFormula.objects.filter(journal_entry_id=entry_id).count() == 0


def test_the_writer_refuses_a_fifth_slot(
    context: TenantContext, scene: dict[str, Any], seed: Callable[..., None]
) -> None:
    event = seed_event(seed, scene["tenant"], scene["company"], scene["user"])
    too_many = FormulaToWrite(
        debit_account_id=scene["vat"],
        credit_account_id=scene["cost"],
        amount=Decimal(1),
        currency=MDL,
        amount_currency=Decimal(1),
        exchange_rate=Decimal(1),
        rate_date=POSTING,
        document_date=POSTING,
        slots=tuple(
            (name, uuid.uuid4()) for name in ("partner", "item", "project", "contract", "asset")
        ),
    )
    with tenant_context(context), pytest.raises(TooManyFormulaSlotsError):
        post_entry(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            entry_number="NC-FIVE",
            accounting_date=POSTING,
            period_id=scene["period"],
            accounting_event_id=event,
            description="Cinci sloturi",
            request_id="formula",
            lines=[_line(scene["vat"], debit="1"), _line(scene["cost"], credit="1")],
            formulas=[too_many],
            rule_ref=RULE,
            fiscal_effective_date=POSTING,
            chart_template_id=None,
        )


# --- R10: posted is immutable ----------------------------------------------------


def seed_posted(scene: dict[str, Any], seed: Callable[..., None]) -> tuple[uuid.UUID, int]:
    """A posted entry with one formula, written by the privileged path.

    Seeded rather than posted through the ORM: rows the ORM writes live in the
    test transaction, so an UPDATE from another connection never finds them and a
    FOR EACH ROW trigger never fires. A trigger test on ORM rows passes with or
    without the trigger (ADR-047 section 5).
    """
    entry_id = uuid.uuid4()
    event = seed_event(seed, scene["tenant"], scene["company"], scene["user"])
    seed(
        "INSERT INTO journal_entry (id, tenant_id, company_id, entry_number,"
        " accounting_date, period_id, entry_type, accounting_event_id, status,"
        " posted_at, posted_by_user_id, description, total_debit, total_credit,"
        " request_id, rule_ref, chart_template_id, fiscal_effective_date, created_at, updated_at)"
        " VALUES (%s, %s, %s, 'NC-SEED', %s, %s, 'standard', %s, 'posted', now(), %s,"
        " 'Semanata', 1, 1, 'formula', %s, NULL, %s, now(), now())",
        [
            entry_id,
            scene["tenant"],
            scene["company"],
            POSTING,
            scene["period"],
            event,
            scene["user"],
            RULE,
            POSTING,
        ],
    )
    seed(
        "INSERT INTO journal_formula (tenant_id, company_id, accounting_date, journal_entry_id,"
        " formula_number, debit_account_id, credit_account_id, amount, currency, amount_currency,"
        " exchange_rate, rate_date, document_date)"
        " VALUES (%s, %s, %s, %s, 1, %s, %s, 1, 'MDL', 1, 1, %s, %s) RETURNING id",
        [
            scene["tenant"],
            scene["company"],
            POSTING,
            entry_id,
            scene["vat"],
            scene["cost"],
            POSTING,
            POSTING,
        ],
    )
    return entry_id, 1


def test_a_formula_of_a_posted_entry_cannot_be_changed_or_removed(
    context: TenantContext, scene: dict[str, Any], seed: Callable[..., None]
) -> None:
    """Two barriers: the application role holds no UPDATE or DELETE, and the
    trigger refuses everyone else -- proved on seeded rows, from the privileged
    connection, which is the one a data migration would use."""
    entry_id, _ = seed_posted(scene, seed)

    with tenant_context(context):
        with pytest.raises(DatabaseError, match="permission denied"), transaction.atomic():
            JournalFormula.objects.filter(journal_entry_id=entry_id).update(amount=Decimal(2))
        with pytest.raises(DatabaseError, match="permission denied"), transaction.atomic():
            JournalFormula.objects.filter(journal_entry_id=entry_id).delete()

    with pytest.raises(psycopg.errors.RaiseException, match="immutable"):
        seed("UPDATE journal_formula SET amount = 2 WHERE journal_entry_id = %s", [entry_id])
    with pytest.raises(psycopg.errors.RaiseException, match="immutable"):
        seed("DELETE FROM journal_formula WHERE journal_entry_id = %s", [entry_id])


def test_what_a_posted_entry_stood_on_cannot_be_rewritten(
    context: TenantContext, scene: dict[str, Any], seed: Callable[..., None]
) -> None:
    """`0036`'s trigger lists the columns it guards and cannot be edited (C31);
    the three stamps get their own, and the message names the ADR."""
    entry_id, _ = seed_posted(scene, seed)
    for column, value in (
        ("rule_ref", "fixture.other.v2"),
        ("fiscal_effective_date", date(2026, 2, 1)),
    ):
        with pytest.raises(psycopg.errors.RaiseException, match="ADR-048"):
            seed(f"UPDATE journal_entry SET {column} = %s WHERE id = %s", [value, entry_id])


# --- the reversal ------------------------------------------------------------------


def test_a_reversal_mirrors_the_formulas_and_copies_the_stamps(
    context: TenantContext, scene: dict[str, Any], seed: Callable[..., None]
) -> None:
    """Accounts swapped, everything else carried; the chart and the fiscal date
    are the original's (a reversal recomputes nothing), the rule is its own."""
    partner = DimensionValue("partner", scene["partner"])
    with tenant_context(context):
        original_id = post(
            scene,
            [
                formula(scene["receivable"], scene["revenue"], "100", dimensions=[partner]),
                formula(
                    scene["receivable"], scene["vat"], "20", dimensions=[partner], vat_rate="20"
                ),
            ],
            seed,
        )
        event = seed_event(seed, scene["tenant"], scene["company"], scene["user"])
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL DEFERRED")
        reversal = reverse_entry(
            original_id,
            accounting_event_id=event,
            period_id=scene["period"],
            accounting_date=date(2026, 1, 20),
            entry_number="NC-STORNO",
            request_id="formula",
            rule_ref="fixture.formula_reversed.v1",
        )
        mirrored = list(
            JournalFormula.objects.filter(journal_entry_id=reversal.id).order_by("formula_number")
        )

    assert reversal.rule_ref == "fixture.formula_reversed.v1"
    assert reversal.fiscal_effective_date == POSTING
    assert reversal.chart_template_id is None
    assert [(f.debit_account_id, f.credit_account_id, f.amount) for f in mirrored] == [
        (scene["revenue"], scene["receivable"], Decimal("100.0000")),
        (scene["vat"], scene["receivable"], Decimal("20.0000")),
    ]
    assert mirrored[0].slot_1_value_id == scene["partner"]
    assert mirrored[1].vat_rate == Decimal("20.0000")


# --- roles ---------------------------------------------------------------------------


def test_roles_bind_to_the_companys_accounts_at_the_posting_date(
    context: TenantContext, scene: dict[str, Any], seed: Callable[..., None]
) -> None:
    """A handler writes roles; the company's bindings say which accounts. The
    role names are the catalogue's -- the vocabulary is code -- and what they
    bind to here is a fixture account, not the subaccount the plan imposes."""
    debit_role, credit_role = sorted(ROLES)[:2]
    with tenant_context(context):
        for role, account in ((debit_role, scene["receivable"]), (credit_role, scene["vat"])):
            AccountRoleBinding.objects.create(
                tenant_id=scene["tenant"],
                company_id=scene["company"],
                role=role,
                account_id=account,
                valid_from=date(2026, 1, 1),
                source="fixture",
            )
        (bound,) = bind_roles(
            scene["company"],
            POSTING,
            [
                RoleFormula(
                    debit_role=debit_role,
                    credit_role=credit_role,
                    amount=Decimal(7),
                    currency=MDL,
                    amount_currency=Decimal(7),
                    exchange_rate=Decimal(1),
                    rate_date=POSTING,
                    document_date=POSTING,
                )
            ],
        )
        assert (bound.debit_account_id, bound.credit_account_id) == (
            scene["receivable"],
            scene["vat"],
        )

        unbound = sorted(ROLES)[2]
        with pytest.raises(RoleNotBoundError):
            bind_roles(
                scene["company"],
                POSTING,
                [
                    RoleFormula(
                        debit_role=debit_role,
                        credit_role=unbound,
                        amount=Decimal(1),
                        currency=MDL,
                        amount_currency=Decimal(1),
                        exchange_rate=Decimal(1),
                        rate_date=POSTING,
                        document_date=POSTING,
                    )
                ],
            )


# --- the manual note stamps too -------------------------------------------------------


def test_a_manual_note_stamps_the_treatment_that_posted_it(
    context: TenantContext, scene: dict[str, Any]
) -> None:
    """The same header, whichever door the entry came through."""
    payload = {
        "description": "Nota manuala cu stampile",
        "lines": [
            {"account_id": str(scene["vat"]), "debit": "10", "credit": "0"},
            {"account_id": str(scene["cost"]), "debit": "0", "credit": "10"},
        ],
    }
    with tenant_context(context):
        result = post_manual_entry(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            accounting_date=POSTING,
            functional_currency=MDL,
            note_id=uuid.uuid4(),
            payload=payload,
            idempotency_key="manual-stamps",
            actor_user_id=scene["user"],
            request_id="formula",
            capability_snapshot=SNAPSHOT,
            occurred_at=datetime.now(UTC),
        )
        entry = JournalEntry.objects.get(id=result.journal_entry_id)
    assert entry.rule_ref == "manual.journal_entry.v1"
    assert entry.fiscal_effective_date == POSTING


# --- isolation -------------------------------------------------------------------------


def test_formulas_of_another_tenant_are_invisible(
    context: TenantContext,
    scene: dict[str, Any],
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
) -> None:
    partner = DimensionValue("partner", scene["partner"])
    with tenant_context(context):
        entry_id = post(
            scene, [formula(scene["receivable"], scene["vat"], "1", dimensions=[partner])], seed
        )
        assert JournalFormula.objects.filter(journal_entry_id=entry_id).count() == 1

    other = TenantContext(
        tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="formula"
    )
    with tenant_context(other):
        assert JournalFormula.objects.filter(journal_entry_id=entry_id).count() == 0
        assert JournalFormula.objects.count() == 0
