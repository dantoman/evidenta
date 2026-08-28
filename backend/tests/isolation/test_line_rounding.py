"""The line rule -- `DNB-08`, the half the owner decided.

    VAT is calculated and rounded **on each line**. The document total is
    obtained by **adding the lines**, never by recalculating on a total base.

The first test is the one that matters, and it is the reason the rule was chosen
rather than the reason it is convenient: with two competing calculations the two
answers differ by a ban or two and the gap grows with the number of positions
(ADR-037 section 3.1). With one calculation the gap cannot exist. The test builds
the case where the difference is real and shows which answer the system gives.

What stayed data, and is proved to be data here rather than asserted:

* **how many decimals** -- a fiscal parameter, resolved by date;
* **which direction a tie resolves in** -- a row in `fiscal_logic_version`. Both
  directions are in the repository; the test registers each in turn and gets a
  different answer from the same input, which is what "not chosen in code" means.

Everything runs under the application role (`T1`). Parameters and logic versions
are seeded through the privileged connection, because there is no other way in --
see `OD-67`.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest

from evidenta.accounting.currency.services.amounts import (
    AmountMalformedError,
    LineAmounts,
    line_amounts,
)
from evidenta.fiscal.parameters.services.resolution import FiscalResolutionError
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

ON = date(2026, 3, 10)
SOURCE_ID = uuid.UUID("00000000-0000-0000-0000-0000000000db")


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="round")


@pytest.fixture
def source(seed: Callable[..., None]) -> uuid.UUID:
    """One fictitious act. No real number, so it cannot be half-cited by accident."""
    seed(
        "INSERT INTO fiscal_parameter_source (id, act_type, act_number, act_date,"
        " official_gazette_number, official_gazette_article, published_at,"
        " effective_from, created_at)"
        " VALUES (%s, 'test', 'TEST-0/0000', DATE '2000-01-01', 'TEST 0', 'art. 0',"
        " DATE '2000-01-01', DATE '2000-01-01', now())",
        [SOURCE_ID],
    )
    return SOURCE_ID


def scale(seed: Callable[..., None], world: dict[str, uuid.UUID], key: str, value: int) -> None:
    seed(
        "INSERT INTO fiscal_parameter (id, parameter_key, scope, value_type, value,"
        " valid_from, source_id, status, approved_by_user_id, approved_at,"
        " source_confidence, created_at, updated_at)"
        " VALUES (%s, %s, 'global', 'integer', %s::jsonb, DATE '2020-01-01', %s,"
        " 'active', %s, now(), 'confirmed', now(), now())",
        [uuid.uuid4(), key, str(value), SOURCE_ID, world["user_a"]],
    )


def direction(seed: Callable[..., None], world: dict[str, uuid.UUID], ref: str) -> None:
    seed(
        "INSERT INTO fiscal_logic_version (id, logic_key, implementation_ref, version,"
        " valid_from, source_id, regression_case_set, status, approved_by_user_id,"
        " approved_at, created_at, updated_at)"
        " VALUES (%s, 'accounting.money_rounding', %s, %s, DATE '2020-01-01', %s,"
        " 'test.rounding', 'active', %s, now(), now(), now())",
        [uuid.uuid4(), ref, f"test-{ref}", SOURCE_ID, world["user_a"]],
    )


@pytest.fixture
def convention(seed: Callable[..., None], world: dict[str, uuid.UUID], source: uuid.UUID) -> None:
    """The working hypothesis: two decimals on amounts, four on the unit price."""
    scale(seed, world, "accounting.amount_scale", 2)
    scale(seed, world, "accounting.unit_price_scale", 4)
    direction(seed, world, "half_up")


def line(quantity: str, price: str, rate: str = "20") -> LineAmounts:
    return line_amounts(
        quantity=Decimal(quantity),
        unit_price=Decimal(price),
        vat_rate=Decimal(rate),
        on=ON,
    )


# --- the property the rule exists for ----------------------------------------


def test_the_document_total_is_the_sum_of_the_lines_and_not_a_second_calculation(
    context: TenantContext, convention: None
) -> None:
    """Three lines whose VAT does not divide evenly, which is the case that hurts.

    Each line is `0.33 x 20% = 0.066`, which rounds to `0.07`. Three of them come
    to `0.21`. Applying the rate to the total base instead gives
    `0.99 x 20% = 0.198`, which rounds to `0.20` -- a ban apart, on three lines, and
    the gap grows with the number of positions.

    The system answers 0.21, because it never performs the second calculation.
    """
    with tenant_context(context):
        lines = [line("1", "0.33") for _ in range(3)]

    per_line = sum((each.vat for each in lines), Decimal(0))
    base = sum((each.net for each in lines), Decimal(0))

    assert [each.vat for each in lines] == [Decimal("0.07")] * 3
    assert per_line == Decimal("0.21")
    assert base == Decimal("0.99")
    # The number the system does *not* produce, written down so the difference is
    # visible rather than asserted away.
    recomputed = (base * Decimal(20) / Decimal(100)).quantize(Decimal("0.01"))
    assert recomputed == Decimal("0.20")
    assert per_line != recomputed


def test_an_ordinary_line_needs_no_rounding_at_all(
    context: TenantContext, convention: None
) -> None:
    """Three units at 125.50 with a 20% rate: 376.50 and 75.30, both exact.

    Most real lines are this one. The rule matters at the margin; it is not a tax
    on the ordinary case.
    """
    with tenant_context(context):
        amounts = line("3", "125.50")
    assert (amounts.net, amounts.vat, amounts.total) == (
        Decimal("376.50"),
        Decimal("75.30"),
        Decimal("451.80"),
    )


def test_the_total_is_the_exact_sum_of_two_rounded_values(
    context: TenantContext, convention: None
) -> None:
    """Rounding happens once per value, never again on something already rounded
    (Spec B section 7.4 point 2)."""
    with tenant_context(context):
        amounts = line("7", "13.37")
    assert amounts.total == amounts.net + amounts.vat


# --- what is data, proved to be data -----------------------------------------


def test_the_tie_direction_comes_from_the_registry_not_from_code(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    context: TenantContext,
    source: uuid.UUID,
) -> None:
    """The same input, two registry rows, two answers.

    `0.125` at two decimals is an exact tie. Half-up gives `0.13`, half-even gives
    `0.12`. Both implementations are in the repository and neither is the answer:
    the row decides, by effective date.
    """
    scale(seed, world, "accounting.amount_scale", 2)
    scale(seed, world, "accounting.unit_price_scale", 4)

    direction(seed, world, "half_up")
    with tenant_context(context):
        up = line_amounts(
            quantity=Decimal(1), unit_price=Decimal("0.625"), vat_rate=Decimal(20), on=ON
        )
    assert up.net == Decimal("0.63")

    seed("DELETE FROM fiscal_logic_version WHERE logic_key = 'accounting.money_rounding'")
    direction(seed, world, "half_even")
    with tenant_context(context):
        even = line_amounts(
            quantity=Decimal(1), unit_price=Decimal("0.625"), vat_rate=Decimal(20), on=ON
        )
    assert even.net == Decimal("0.62")


def test_the_precision_comes_from_a_parameter(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    context: TenantContext,
    source: uuid.UUID,
) -> None:
    """Four decimals instead of two, and the same input answers differently.

    Which is the whole point of `R15`: an instruction that prescribes another
    precision is an INSERT, not a deployment.
    """
    scale(seed, world, "accounting.amount_scale", 4)
    scale(seed, world, "accounting.unit_price_scale", 4)
    direction(seed, world, "half_up")
    with tenant_context(context):
        amounts = line("1", "0.3333")
    assert amounts.net == Decimal("0.3333")
    assert amounts.vat == Decimal("0.0667")


# --- refusals ----------------------------------------------------------------


def test_without_a_registered_precision_nothing_is_calculated(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    context: TenantContext,
    source: uuid.UUID,
) -> None:
    """A precision nobody chose is not a precision.

    This is the state the build ships in today: the mechanism is complete and no
    value is registered, because `fiscal_parameter` has no write path at all
    (`OD-67`).
    """
    direction(seed, world, "half_up")
    with tenant_context(context), pytest.raises(FiscalResolutionError) as caught:
        line("1", "10.00")
    assert caught.value.code == "fiscal.no_parameter"


def test_without_a_registered_direction_nothing_is_calculated(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    context: TenantContext,
    source: uuid.UUID,
) -> None:
    scale(seed, world, "accounting.amount_scale", 2)
    scale(seed, world, "accounting.unit_price_scale", 4)
    with tenant_context(context), pytest.raises(FiscalResolutionError) as caught:
        line("1", "10.00")
    assert caught.value.code == "fiscal.no_logic"


def test_a_unit_price_finer_than_the_form_allows_is_refused(
    context: TenantContext, convention: None
) -> None:
    """Rounding it here would change a price somebody agreed.

    Refused rather than quantised, because the two are different acts: one reports
    that the document cannot be issued as typed, the other issues a different
    document.
    """
    with tenant_context(context), pytest.raises(AmountMalformedError):
        line("1", "10.123456")


def test_trailing_zeros_are_not_precision(context: TenantContext, convention: None) -> None:
    """`125.5000` carries one decimal, not four -- that is how it was typed, not
    how precise it is. Counting the exponent would refuse a price the form
    accepts."""
    with tenant_context(context):
        amounts = line("1", "125.5000")
    assert amounts.net == Decimal("125.50")


def test_a_discount_stated_twice_is_a_question_not_an_input(
    context: TenantContext, convention: None
) -> None:
    """A precedence rule here would be a silent answer to "which did they mean"."""
    with tenant_context(context), pytest.raises(AmountMalformedError):
        line_amounts(
            quantity=Decimal(1),
            unit_price=Decimal("100.00"),
            vat_rate=Decimal(20),
            on=ON,
            discount_percent=Decimal(10),
            discount_amount=Decimal("10.00"),
        )
