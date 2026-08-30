"""C5 -- the allocation of indirect production costs, against SNC "Stocuri".

The act carries its own worked example (Anexa 1): three products, 120 000 lei
of constant and 80 000 lei of variable indirect costs, a table of what enters
the cost and what stays as current expenses, and the two postings the entity
makes. The cases below put that example through the handler and assert the
act's figures. What the corpus tests is whether the implementation matches
the cited text -- not whether our reading matches practice (ADR-054).

Two things the example shows. The table applies pct. 30's ratio **per
product**, with each product's own normal capacity, so the corpus posts one
fact per product -- whether the fact should carry per-product capacity is
`OD-77`, not the corpus's to decide. And the table leaves the ban a
proportional split drops on "B", where ADR-058 §2.5 puts it on the largest
share: a **known, motivated deviation** (the act does not prescribe the
residual; the owner chose determinism against the data) -- the act's two
totals are reproduced exactly, two cells differ by one ban (README, "Abateri
cunoscute, motivate").
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from evidenta.accounting.currency.money import rounding_for
from evidenta.accounting.posting.absorption import distribute
from evidenta.accounting.posting.services.production import (
    AllocationFact,
    AllocationResult,
    ProductShare,
    post_overhead_allocation,
)
from evidenta.fiscal.parameters.services.resolution import FiscalResolutionError
from evidenta.fiscal.parameters.services.scales import amount_scale
from evidenta.platform.rls.context import tenant_context
from tests.corpus.book import MDL, SNAPSHOT, Book, agree
from tests.corpus.citations import ABSORPTION, ROUNDING, case

pytestmark = pytest.mark.django_db(databases=["default", "migration", "refdata"])

JAN_1, JAN_15, JAN_31 = date(2026, 1, 1), date(2026, 1, 15), date(2026, 1, 31)

#: The three products of Anexa 1, with their codes as the act names them.
A, B, C = uuid.UUID(int=0xA), uuid.UUID(int=0xB), uuid.UUID(int=0xC)
#: Tabelul 1: (product, code, normal capacity, actual volume), in units.
TABLE_1 = (
    (A, "A", Decimal(7000), Decimal(7000)),
    (B, "B", Decimal(5000), Decimal(4000)),
    (C, "C", Decimal(8000), Decimal(6000)),
)
CONSTANT_TOTAL, VARIABLE_TOTAL = Decimal(120000), Decimal(80000)
BASE = "volumul produselor fabricate"


def product(item: uuid.UUID, base_value: str | int | Decimal, code: str) -> ProductShare:
    return ProductShare(item, Decimal(base_value), code=code)


def fact(
    *,
    variable: str | int | Decimal,
    constant: str | int | Decimal,
    normal: str | int | Decimal,
    actual: str | int | Decimal,
    products: tuple[ProductShare, ...],
    start: date = JAN_1,
    end: date = JAN_31,
) -> AllocationFact:
    return AllocationFact(
        allocation_id=uuid.uuid4(),
        period_start=start,
        period_end=end,
        variable_costs=Decimal(variable),
        constant_costs=Decimal(constant),
        normal_capacity=Decimal(normal),
        actual_volume=Decimal(actual),
        base_name=BASE,
        products=products,
    )


def allocate(book: Book, the_fact: AllocationFact) -> AllocationResult:
    return post_overhead_allocation(
        tenant_id=book.tenant,
        company_id=book.company,
        functional_currency=MDL,
        fact=the_fact,
        actor_user_id=book.user,
        request_id="corpus",
        capability_snapshot=dict(SNAPSHOT),
    )


# --- Anexa 1, row by row ---------------------------------------------------------------


@case(ABSORPTION, cites=("SNC Stocuri pct. 30", "SNC Stocuri Anexa 1", "Plan 811", "Plan 821"))
def test_anexa_1_product_a_at_normal_capacity_takes_the_constant_costs_in_full(book: Book) -> None:
    """Row "A": 7000 of 7000 -- "egal sau depăşeşte capacitatea normală ... se include
    integral în cost". Column 8 = 82 352,94; column 6 = 0, so nothing on 714."""
    with tenant_context(book.context):
        result = allocate(
            book,
            fact(
                variable="32941.18",
                constant="49411.76",
                normal=7000,
                actual=7000,
                products=(product(A, 7000, "A"),),
            ),
        )
        assert result.journal_entry_id is not None
        assert book.correspondences(result.journal_entry_id) == [
            ("811", "821", Decimal("82352.94")),
        ]
        assert book.balance("714") == 0
        agree(book)


@case(ABSORPTION, cites=("SNC Stocuri pct. 30", "SNC Stocuri Anexa 1", "Plan 714", "Plan 821"))
def test_anexa_1_product_b_below_capacity_includes_the_ratio_and_expenses_the_rest(
    book: Book,
) -> None:
    """Row "B": 4000 of 5000 -- the constant part enters "în baza cotei calculate ca
    raportul dintre volumul efectiv ... şi capacitatea normală": 28 235,30 x 4000/5000 =
    22 588,24 into the cost, and "suma rămasă ... cheltuieli curente": 5 647,06 on 714.
    Column 8 = 41 411,77."""
    with tenant_context(book.context):
        result = allocate(
            book,
            fact(
                variable="18823.53",
                constant="28235.30",
                normal=5000,
                actual=4000,
                products=(product(B, 4000, "B"),),
            ),
        )
        assert result.journal_entry_id is not None
        assert book.correspondences(result.journal_entry_id) == [
            ("811", "821", Decimal("41411.77")),
            ("714", "821", Decimal("5647.06")),
        ]
        agree(book)


@case(
    ABSORPTION,
    ROUNDING,
    cites=("SNC Stocuri pct. 30", "SNC Stocuri Anexa 1", "ADR-037 §3.3"),
)
def test_anexa_1_product_c_rounds_the_half_ban_up(book: Book) -> None:
    """Row "C": 42 352,94 x 6000/8000 = 31 764,705 exactly -- a tie at the third
    decimal. The table writes **31 764,71** (column 5) and 10 588,23 (column 6), which
    is the direction ADR-037 §3.3 chose; half-even would give 31 764,70 and the row
    would sum to 59 999,99 instead of the table's 60 000,00."""
    with tenant_context(book.context):
        result = allocate(
            book,
            fact(
                variable="28235.29",
                constant="42352.94",
                normal=8000,
                actual=6000,
                products=(product(C, 6000, "C"),),
            ),
        )
        assert result.journal_entry_id is not None
        assert book.correspondences(result.journal_entry_id) == [
            ("811", "821", Decimal("60000.00")),
            ("714", "821", Decimal("10588.23")),
        ]
        agree(book)


@case(
    ABSORPTION,
    cites=(
        "SNC Stocuri pct. 29",
        "SNC Stocuri pct. 30",
        "SNC Stocuri pct. 31",
        "SNC Stocuri Anexa 1",
        "Plan 821",
        "Plan 811",
        "Plan 714",
        "Plan clasa 8",
        "ADR-058 §2.5",
    ),
)
def test_anexa_1_in_full_reproduces_the_two_postings_the_act_writes(book: Book) -> None:
    """The whole example: 200 000 collected on 821, split over the products by the base
    the policy fixes (pct. 31, columns 4 and 7), then pct. 30 per product. The act's two
    postings: 16 235,29 "ca majorare a cheltuielilor curente şi diminuare a costurilor
    indirecte" and 183 764,71 "ca majorare a costurilor activităţilor de bază şi
    diminuare a costurilor indirecte". 821 closes at zero (Plan, clasa 8).

    Column 4 of the table sums to 120 000 with the ban from the split on "B"
    (28 235,30); `distribute` puts it on the largest share (ADR-058 §2.5), so "A"
    carries 49 411,77 and "B" 28 235,29 here. The totals are unaffected; the two cells
    are a known, motivated deviation -- the act does not prescribe the residual, the
    owner chose determinism against the data (2026-08-30) -- asserted, not tolerated.
    """
    with tenant_context(book.context):
        book.note(
            [("821", "200000.00", "0"), ("5211", "0", "200000.00")],
            on=JAN_15,
            description="Costuri indirecte de producţie facturate în luna curentă",
        )
        rule, scale = rounding_for(JAN_31), amount_scale(JAN_31)
        volumes = [actual for _, _, _, actual in TABLE_1]
        codes = [code for _, code, _, _ in TABLE_1]
        constants = distribute(CONSTANT_TOTAL, volumes, keys=codes, rule=rule, scale=scale)
        variables = distribute(VARIABLE_TOTAL, volumes, keys=codes, rule=rule, scale=scale)
        assert constants == [Decimal("49411.77"), Decimal("28235.29"), Decimal("42352.94")], (
            "coloana 4 a tabelului: 49 411,76 / 28 235,30 / 42 352,94 -- abatere cunoscută: "
            "banul rămas stă pe cota cea mai mare (ADR-058 §2.5), pe B în tabel"
        )
        assert variables == [Decimal("32941.18"), Decimal("18823.53"), Decimal("28235.29")]

        into_cost: dict[str, Decimal] = {}
        for (item, code, normal, actual), constant, variable in zip(
            TABLE_1, constants, variables, strict=True
        ):
            result = allocate(
                book,
                fact(
                    variable=variable,
                    constant=constant,
                    normal=normal,
                    actual=actual,
                    products=(product(item, actual, code),),
                ),
            )
            assert result.journal_entry_id is not None
            into_cost[code] = sum(
                (
                    amount
                    for debit, _, amount in book.correspondences(result.journal_entry_id)
                    if debit == "811"
                ),
                Decimal(0),
            )

        assert book.balance("811") == Decimal("183764.71")
        assert book.balance("714") == Decimal("16235.29")
        assert book.balance("821") == 0
        # Column 8 of the table: 82 352,94 / 41 411,77 / 60 000,00. "A" and "B" carry
        # the ban the split placed differently; "C" is the table's cell.
        assert into_cost == {
            "A": Decimal("82352.95"),
            "B": Decimal("41411.76"),
            "C": Decimal("60000.00"),
        }
        agree(book)


# --- pct. 30 and pct. 31, each on its own -----------------------------------------------


@case(ABSORPTION, cites=("SNC Stocuri pct. 31", "Plan 811", "Plan 821"))
def test_the_split_over_the_base_the_policy_fixes_adds_up_to_the_last_ban(book: Book) -> None:
    """pct. 31: "proporţional cu baza stabilită în politicile contabile" -- here the
    quantity of products made, one of the bases the point lists. At normal capacity
    everything enters the cost: 200 000 over 7000 / 4000 / 6000 units is 82 352,94 /
    47 058,82 / 70 588,24, one line per product with the product as its dimension."""
    with tenant_context(book.context):
        result = allocate(
            book,
            fact(
                variable=VARIABLE_TOTAL,
                constant=CONSTANT_TOTAL,
                normal=20000,
                actual=20000,
                products=tuple(product(item, actual, code) for item, code, _, actual in TABLE_1),
            ),
        )
        assert result.journal_entry_id is not None
        assert book.correspondences(result.journal_entry_id) == [
            ("811", "821", Decimal("82352.94")),
            ("811", "821", Decimal("47058.82")),
            ("811", "821", Decimal("70588.24")),
        ]
        assert [f.slot_1_value_id for f in book.formulas(result.journal_entry_id)] == [A, B, C]
        assert book.balance("714") == 0
        agree(book)


@case(ABSORPTION, cites=("SNC Stocuri pct. 30", "SNC Stocuri Anexa 1"))
def test_above_normal_capacity_the_constant_costs_are_capped_at_their_total(book: Book) -> None:
    """pct. 30 (2), and the footnote of the table: above normal capacity the constant
    costs "se includ integral în cost, dar nu trebuie să depăşească suma din coloana 4"."""
    with tenant_context(book.context):
        result = allocate(
            book,
            fact(
                variable=0,
                constant=CONSTANT_TOTAL,
                normal=20000,
                actual=21000,
                products=(product(A, 21000, "A"),),
            ),
        )
        assert result.journal_entry_id is not None
        assert book.correspondences(result.journal_entry_id) == [
            ("811", "821", Decimal("120000.00")),
        ]
        agree(book)


@case(ABSORPTION, cites=("SNC Stocuri pct. 30", "Plan 811"))
def test_variable_costs_enter_the_cost_in_full_whatever_the_capacity_use(book: Book) -> None:
    """pct. 30 (1): variable costs enter "în suma totală, indiferent de gradul de
    utilizare a capacităţilor de producţie" -- a quarter of the capacity used, all
    80 000 in the cost, nothing on 714."""
    with tenant_context(book.context):
        result = allocate(
            book,
            fact(
                variable=VARIABLE_TOTAL,
                constant=0,
                normal=20000,
                actual=5000,
                products=(product(A, 5000, "A"),),
            ),
        )
        assert result.journal_entry_id is not None
        assert book.correspondences(result.journal_entry_id) == [
            ("811", "821", Decimal("80000.00")),
        ]
        assert book.balance("714") == 0
        agree(book)


@case(ABSORPTION, cites=("SNC Stocuri pct. 57", "ADR-037 §3.3"))
def test_before_the_acts_are_in_force_the_allocation_is_refused_not_guessed(book: Book) -> None:
    """pct. 57: the standard is in force from 1 January 2014; the rounding direction
    (ADR-037 §3.3) from 28 October 2017. A period before either has no rule in force,
    and the registry refuses (R17, R18) rather than applying today's."""
    with tenant_context(book.context):
        with pytest.raises(FiscalResolutionError) as refusal:
            allocate(
                book,
                fact(
                    variable=VARIABLE_TOTAL,
                    constant=CONSTANT_TOTAL,
                    normal=20000,
                    actual=17000,
                    products=(product(A, 17000, "A"),),
                    start=date(2013, 12, 1),
                    end=date(2013, 12, 31),
                ),
            )
        assert refusal.value.code == "fiscal.no_logic"
        agree(book)


@case(ABSORPTION, cites=("ADR-058 §6", "SNC Stocuri pct. 57", "ADR-037 §3.3"))
def test_inside_the_gap_the_rule_is_in_force_and_the_direction_is_not_so_it_is_refused(
    book: Book,
) -> None:
    """ADR-058 §6: the absorption rule is in force from 01.01.2014 (pct. 57), the
    rounding direction from 28.10.2017; a period between the two "găseşte regula şi nu
    găseşte direcţia, iar registrul refuză" -- and nobody moves the direction's
    `valid_from` back to make it pass. Against the shipped dates, not fixture ones: if
    `platform_conventions.toml` closed the gap, this case would be the one to notice."""
    with tenant_context(book.context):
        with pytest.raises(FiscalResolutionError) as refusal:
            allocate(
                book,
                fact(
                    variable=VARIABLE_TOTAL,
                    constant=CONSTANT_TOTAL,
                    normal=20000,
                    actual=17000,
                    products=(product(A, 17000, "A"),),
                    start=date(2016, 6, 1),
                    end=date(2016, 6, 30),
                ),
            )
        assert refusal.value.code == "fiscal.no_logic"
        assert "accounting.money_rounding" in str(refusal.value)
        assert "2016-06-30" in str(refusal.value)
        agree(book)
