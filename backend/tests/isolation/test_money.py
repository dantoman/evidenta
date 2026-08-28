"""The amount model and exchange rates -- Spec B section 7.

Two things are being proved, and the second is the unusual one.

The first is ordinary: `Decimal` throughout, currencies that refuse to mix, a
rate that cannot be zero, and rates readable by everyone but writable by no
tenant.

The second is that **the module refuses to round**. There is no rounding rule
registered for `accounting.money_rounding`, because DNB-08 -- two or four
decimals, half-up or half-even, rounding per line or per document -- is blocked
on the SFS integration guide (OD-24), and the guide is not in hand. So `convert`
raises. That is the intended state of this build, and it is asserted rather than
left implicit: a module that quietly picked a rule would be producing numbers
nobody can defend against the SFS validator, and the divergence would surface as
a rejected invoice months later.

The wiring is still proved end to end, by registering a rule that says in its own
name that it is not a real one.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pytest
from django.db import transaction
from django.db.utils import IntegrityError, ProgrammingError

from evidenta.accounting.currency.models import ExchangeRate, RateType
from evidenta.accounting.currency.money import (
    IMPLEMENTATIONS,
    ROUNDING_LOGIC_KEY,
    CurrencyMismatchError,
    Money,
    UnknownImplementationError,
    convert,
)
from evidenta.fiscal.registry.services.resolution import FiscalResolutionError
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

APPROVER = uuid.UUID("00000000-0000-0000-0000-0000000000b1")

#: Deliberately not a plausible name. Registering `half_up_2dp` here would put an
#: answer to DNB-08 point (b) in the repository under a name someone could later
#: mistake for a decision.
PROBE_REF = "tests.probe.not_a_real_rounding_rule"


class _ProbeRounding:
    """A stand-in, named so it cannot be mistaken for the shipped rule.

    It lives in the test file so the answer cannot arrive in production by being
    imported. The scale is an argument now, not a property: the direction at a tie
    is versioned code, the number of decimals is versioned data, and they move
    independently.
    """

    def quantize(self, value: Decimal, scale: int) -> Decimal:
        return value.quantize(Decimal(1).scaleb(-scale), rounding=ROUND_HALF_UP)


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="money")


@pytest.fixture
def probe_rule(seed: Callable[..., None]) -> Iterator[None]:
    """Register the probe in the registry table, in the code table, **and** the
    precision it rounds to.

    Three things, and the split is the design: the registry row selects the
    direction, the code table provides it, and a fiscal parameter says how many
    decimals. None of the three alone can round anything -- which is what stops a
    rule from arriving by being imported, and what lets an instruction change the
    precision without a deployment.
    """
    source_id = uuid.uuid4()
    seed(
        "INSERT INTO fiscal_parameter_source (id, act_type, act_number, act_date,"
        " official_gazette_number, official_gazette_article, published_at,"
        " effective_from, created_at)"
        " VALUES (%s, 'test', 'TEST-0/0000', DATE '2000-01-01', 'TEST 0', 'art. 0',"
        " DATE '2000-01-01', DATE '2000-01-01', now())",
        [source_id],
    )
    seed(
        "INSERT INTO fiscal_parameter (id, parameter_key, scope, value_type, value,"
        " valid_from, source_id, status, approved_by_user_id, approved_at,"
        " source_confidence, created_at, updated_at)"
        " VALUES (%s, 'accounting.amount_scale', 'global', 'integer', '2'::jsonb,"
        " DATE '2000-01-01', %s, 'active', %s, now(), 'confirmed', now(), now())",
        [uuid.uuid4(), source_id, APPROVER],
    )
    seed(
        """
        INSERT INTO fiscal_logic_version
            (id, logic_key, implementation_ref, version, valid_from, valid_to,
             regression_case_set, status, approved_by_user_id, approved_at,
             created_at, updated_at)
        VALUES (%s, %s, %s, 'probe', DATE '2000-01-01', NULL, 'corpus/probe',
                'active', %s, now(), now(), now())
        """,
        [uuid.uuid4(), ROUNDING_LOGIC_KEY, PROBE_REF, APPROVER],
    )
    IMPLEMENTATIONS[PROBE_REF] = _ProbeRounding()
    yield
    IMPLEMENTATIONS.pop(PROBE_REF, None)


# --- Money: exact, and refusing to guess --------------------------------------


def test_a_float_is_refused_rather_than_converted() -> None:
    """Not pedantry. `float` makes the same trial balance produce different
    results depending on aggregation order, and the difference shows up as a few
    bani nobody can attribute to anything.
    """
    with pytest.raises(TypeError):
        Money(19.99, "MDL")  # type: ignore[arg-type]


def test_two_currencies_do_not_add() -> None:
    """There is no right answer, and inventing one by picking a rate would be a
    conversion nobody asked for and nobody can trace back to a rate row.
    """
    with pytest.raises(CurrencyMismatchError):
        Money(Decimal("10"), "MDL") + Money(Decimal("10"), "EUR")


def test_arithmetic_is_exact_and_returns_new_values() -> None:
    a = Money(Decimal("0.1"), "MDL")
    b = Money(Decimal("0.2"), "MDL")
    assert (a + b).amount == Decimal("0.3")
    assert a.amount == Decimal("0.1")


def test_a_currency_code_is_three_upper_letters() -> None:
    with pytest.raises(ValueError):
        Money(Decimal("1"), "mdl")


# --- Conversion refuses without a registered rule -----------------------------


def test_conversion_refuses_while_the_rounding_rule_is_unsettled(
    seed: Callable[..., None], context: TenantContext
) -> None:
    """The state this build is actually in, asserted so it cannot drift silently.

    DNB-08 is blocked on the SFS guide. Until it is answered, there is no rule,
    and a system that rounded anyway would be producing numbers it cannot defend
    against the validator that decides whether an invoice is accepted.
    """
    with tenant_context(context), pytest.raises(FiscalResolutionError) as excinfo:
        convert(
            Money(Decimal("100"), "EUR"),
            functional_currency="MDL",
            exchange_rate=Decimal("19.5"),
            effective_date=date(2026, 3, 1),
        )
    assert excinfo.value.code == "fiscal.no_logic"


def test_a_registry_row_naming_an_absent_rule_is_refused(
    seed: Callable[..., None], context: TenantContext
) -> None:
    """The security property, stated as a test.

    `fiscal_logic_version` is written through privileged path P-3/P-4. If
    `implementation_ref` were fed to an import, one privileged INSERT would be
    arbitrary code execution inside the application role -- and the dependency
    guard, which reads the AST, cannot see a dynamic import at all. The registry
    selects among implementations that exist in this build; it never loads one.
    """
    seed(
        """
        INSERT INTO fiscal_logic_version
            (id, logic_key, implementation_ref, version, valid_from,
             regression_case_set, status, approved_by_user_id, approved_at,
             created_at, updated_at)
        VALUES (%s, %s, 'os.system', 'evil', DATE '2000-01-01', 'corpus/none',
                'active', %s, now(), now(), now())
        """,
        [uuid.uuid4(), ROUNDING_LOGIC_KEY, APPROVER],
    )
    with tenant_context(context), pytest.raises(UnknownImplementationError):
        convert(
            Money(Decimal("100"), "EUR"),
            functional_currency="MDL",
            exchange_rate=Decimal("19.5"),
            effective_date=date(2026, 3, 1),
        )


# --- With a rule registered, the four elements come out together --------------


def test_conversion_produces_all_four_elements(probe_rule: None, context: TenantContext) -> None:
    """Spec B section 7.1, and Law 287/2017 art. 7(2) behind it: the books are
    kept in both the national currency and the foreign one, so all four are
    stored rather than derived on read.
    """
    with tenant_context(context):
        converted = convert(
            Money(Decimal("100.005"), "EUR"),
            functional_currency="MDL",
            exchange_rate=Decimal("19.50000000"),
            effective_date=date(2026, 3, 1),
        )

    assert converted.amount_currency == Decimal("100.005")
    assert converted.currency == "EUR"
    assert converted.exchange_rate == Decimal("19.50000000")
    # 100.005 * 19.5 = 1950.0975 exactly, rounded once at the end.
    assert converted.functional_amount == Decimal("1950.10")
    assert converted.functional_currency == "MDL"


def test_rounding_happens_once_at_the_end_not_per_step(
    probe_rule: None, context: TenantContext
) -> None:
    """Spec B section 7.4 point 2. Rounding the amount first and multiplying
    after gives a different answer, and on a document with many lines the
    difference accumulates into a total that does not match the sum of its lines.
    """
    with tenant_context(context):
        converted = convert(
            Money(Decimal("0.005"), "EUR"),
            functional_currency="MDL",
            exchange_rate=Decimal("19.5"),
            effective_date=date(2026, 3, 1),
        )
    # Rounded first: 0.01 * 19.5 = 0.195 -> 0.20. Rounded once: 0.0975 -> 0.10.
    assert converted.functional_amount == Decimal("0.10")


def test_the_functional_currency_converts_at_exactly_one(
    probe_rule: None, context: TenantContext
) -> None:
    """Spec B section 1.3 stores 1 rather than NULL, so the derivation rule has
    no special case and `CHECK (exchange_rate > 0)` needs no exception.
    """
    with tenant_context(context):
        converted = convert(
            Money(Decimal("100.00"), "MDL"),
            functional_currency="MDL",
            exchange_rate=Decimal(1),
            effective_date=date(2026, 3, 1),
        )
    assert converted.functional_amount == Decimal("100.00")

    with tenant_context(context), pytest.raises(ValueError):
        convert(
            Money(Decimal("100.00"), "MDL"),
            functional_currency="MDL",
            exchange_rate=Decimal("1.01"),
            effective_date=date(2026, 3, 1),
        )


def test_a_zero_rate_is_refused(probe_rule: None, context: TenantContext) -> None:
    """A zero rate does not convert an amount, it erases it -- inside an entry
    that is immutable once posted.
    """
    with tenant_context(context), pytest.raises(ValueError):
        convert(
            Money(Decimal("100"), "EUR"),
            functional_currency="MDL",
            exchange_rate=Decimal(0),
            effective_date=date(2026, 3, 1),
        )


def test_the_rule_is_selected_by_the_period_not_by_today(
    seed: Callable[..., None], context: TenantContext
) -> None:
    """R17 and R18 reaching the money model.

    A rule valid only from 2027 does not apply to a 2026 period, even though it
    is active and is the newest. The date decides.
    """
    seed(
        """
        INSERT INTO fiscal_logic_version
            (id, logic_key, implementation_ref, version, valid_from,
             regression_case_set, status, approved_by_user_id, approved_at,
             created_at, updated_at)
        VALUES (%s, %s, %s, 'probe-2027', DATE '2027-01-01', 'corpus/probe',
                'active', %s, now(), now(), now())
        """,
        [uuid.uuid4(), ROUNDING_LOGIC_KEY, PROBE_REF, APPROVER],
    )
    IMPLEMENTATIONS[PROBE_REF] = _ProbeRounding()
    try:
        with tenant_context(context), pytest.raises(FiscalResolutionError) as excinfo:
            convert(
                Money(Decimal("100"), "EUR"),
                functional_currency="MDL",
                exchange_rate=Decimal("19.5"),
                effective_date=date(2026, 12, 31),
            )
        assert excinfo.value.code == "fiscal.no_logic"
    finally:
        IMPLEMENTATIONS.pop(PROBE_REF, None)


# --- exchange_rate: global, readable by all, writable by none -----------------


def test_every_tenant_reads_the_same_rate(
    seed: Callable[..., None], world: dict[str, uuid.UUID]
) -> None:
    seed(
        """
        INSERT INTO exchange_rate
            (id, currency, rate_date, rate, rate_type, source, created_at)
        VALUES (%s, 'EUR', DATE '2026-03-01', 19.50000000, 'bnm_official',
                'test', now())
        """,
        [uuid.uuid4()],
    )
    for tenant, user in (
        (world["tenant_a"], world["user_a"]),
        (world["tenant_b"], world["user_b"]),
    ):
        ctx = TenantContext(tenant_id=tenant, user_id=user, request_id="money")
        with tenant_context(ctx):
            row = ExchangeRate.objects.get(currency="EUR", rate_date=date(2026, 3, 1))
            assert row.rate == Decimal("19.50000000")


def test_a_tenant_cannot_write_a_rate(seed: Callable[..., None], context: TenantContext) -> None:
    """A tenant able to write a rate could change what an invoice was worth --
    for every other tenant in the installation. Writing is privileged path P-3.
    """
    with (
        tenant_context(context),
        pytest.raises((ProgrammingError, IntegrityError)),
        transaction.atomic(),
    ):
        ExchangeRate.objects.create(
            currency="EUR",
            rate_date=date(2026, 3, 2),
            rate=Decimal("1"),
            rate_type=RateType.MANUAL,
        )


def test_official_and_contractual_rates_coexist_on_one_day(seed: Callable[..., None]) -> None:
    """Why `rate_type` is in the key. Both can be correct on the same day for
    different documents; without the type, loading one would overwrite the other.
    """
    for kind in ("bnm_official", "contractual"):
        seed(
            """
            INSERT INTO exchange_rate
                (id, currency, rate_date, rate, rate_type, created_at)
            VALUES (%s, 'USD', DATE '2026-03-01', 17.5, %s, now())
            """,
            [uuid.uuid4(), kind],
        )

    with pytest.raises(Exception) as excinfo:
        seed(
            """
            INSERT INTO exchange_rate
                (id, currency, rate_date, rate, rate_type, created_at)
            VALUES (%s, 'USD', DATE '2026-03-01', 18.0, 'bnm_official', now())
            """,
            [uuid.uuid4()],
        )
    assert "exchange_rate_unique" in str(excinfo.value)


def test_a_non_positive_rate_is_refused_by_the_database(seed: Callable[..., None]) -> None:
    with pytest.raises(Exception) as excinfo:
        seed(
            """
            INSERT INTO exchange_rate
                (id, currency, rate_date, rate, rate_type, created_at)
            VALUES (%s, 'EUR', DATE '2026-03-03', 0, 'manual', now())
            """,
            [uuid.uuid4()],
        )
    assert "exchange_rate_positive" in str(excinfo.value)
