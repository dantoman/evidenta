"""Allocation of indirect production costs -- F1.4.4, case C5 of ADR-036 section 11.

The second handler in the order the owner fixed. Its purpose in that order: to
show that a rule **with a calculation of its own** works with **open data** --
the formula is the act's (pct. 30) and versioned; the base of the split is the
entity's (pct. 31, "for example"), an open nomenclature that arrives as values
and is never enumerated in code.

**The act, and what follows it** (SNC "Stocuri" pct. 29-31; Planul general de
conturi, cap. III, 811 and 821 -- `c5-costuri-indirecte-conturi.md`):

* two steps, both obligatory (pct. 29): first between the cost of the products
  and the current expenses, then across the types of products;
* variable indirect costs go into cost in full (pct. 30(1)); constant ones by
  normal capacity, the remainder being current expenses (pct. 30(2)) -- the
  rule lives in `posting.absorption`, selected by date (R17);
* the base of step 2 is whatever the accounting policy fixes (pct. 31);
* the accounts: the credit of 821 is settled "în corespondenţă cu debitul
  conturilor: 714, 811, 812" -- the absorbed part to 811 (the basic activity's
  cost), the unabsorbed remainder to 714 (other operating expenses). Roles:
  `COSTURI_INDIRECTE_PRODUCTIE`, `PRODUCTIE_DE_BAZA`,
  `COSTURI_INDIRECTE_NEREPARTIZATE`.

**Per product, as a dimension.** Each product's share is its own formula,
`Dt 811 / Ct 821`, carrying the product as the `item` dimension on the debit
side -- if the company's 811 declares that slot (ADR-048: the plan says what an
account carries). An 811 that declares no `item` gets the same formulas without
the analytic, which is the entity's configuration, not the handler's concern.

**The handler is pure of the ledger.** The fact -- the period's variable and
constant totals, the normal capacity, the actual volume, the base name and the
base value per product -- is the caller's, stated explicitly. The handler reads
the fiscal registry for the scale, the rounding direction and the absorption
rule in force on the period's last day, and stamps the scale (ADR-047).

**What this makes true for the closing:** after the allocation 821 is at zero,
which is the class-8 invariant `period.month_closed` checks (ADR-056). C5 is what
makes a production month closable.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction

from evidenta.accounting.currency.money import rounding_for
from evidenta.accounting.events.registry import (
    HANDLERS,
    EventType,
    HandlerVersion,
    register,
)
from evidenta.accounting.events.services.emission import emit
from evidenta.accounting.events.services.lifecycle import mark_failed, mark_posted
from evidenta.accounting.ledger.services.writing import ParameterStamp, entry_id_of_event
from evidenta.accounting.posting.absorption import absorption_for, distribute
from evidenta.accounting.posting.formula import DimensionValue, Formula, RoleFormula, bind_roles
from evidenta.accounting.posting.invariants import Origin, PostingRefusedError
from evidenta.accounting.posting.resolution import selected_treatment
from evidenta.accounting.posting.services.formulas import post_formulas
from evidenta.fiscal.parameters.services.resolution import resolve_parameter
from evidenta.fiscal.parameters.services.scales import AMOUNT_SCALE_KEY, amount_scale
from evidenta.platform.api.errors import ApiError
from evidenta.platform.numbering.services.allocation import NumberingError

EVENT_TYPE = "production.overhead_allocated"
HANDLER_REF = "production.overhead_allocation.v1"

#: The source of the fact is the production activity, and the vocabulary says
#: so (`SourceModule.PRODUCTION`) even though no production module exists yet:
#: `manual` would say somebody typed the split, and nobody did.
SOURCE_MODULE = "production"
SOURCE_DOCUMENT_TYPE = "overhead_allocation"

ROLE_INDIRECT = "COSTURI_INDIRECTE_PRODUCTIE"
ROLE_BASIC = "PRODUCTIE_DE_BAZA"
ROLE_UNABSORBED = "COSTURI_INDIRECTE_NEREPARTIZATE"

ITEM_DIMENSION = "item"

PAYLOAD_FIELDS = (
    "allocation_id",
    "period_start",
    "period_end",
    "variable_costs",
    "constant_costs",
    "normal_capacity",
    "actual_volume",
    "base_name",
    "products",
)


class AllocationPayloadError(PostingRefusedError):
    """The fact is not one the rule can compute from. A caller bug, refused
    before any event exists."""

    code = "posting.overhead_payload_malformed"
    status = 400


class AllocationBaseEmptyError(PostingRefusedError):
    """The base of step 2 sums to nothing, so nothing can be proportional to it.

    The base is the entity's (pct. 31), and an empty one is not a choice of base
    -- it is the absence of one. Refused, not spread evenly: "evenly" would be a
    base nobody fixed.
    """

    code = "posting.overhead_base_empty"
    status = 400


@dataclass(frozen=True, slots=True)
class ProductShare:
    item_id: uuid.UUID
    base_value: Decimal
    #: The product's own code, as the caller states it -- the tie-breaker of the
    #: split's residual (`absorption.distribute`). A datum, unlike the position in
    #: this tuple; when the caller has none, the item's identifier stands in, which
    #: is still the product and not its place in the list.
    code: str | None = None

    @property
    def key(self) -> str:
        return self.code if self.code is not None else str(self.item_id)


@dataclass(frozen=True, slots=True)
class AllocationFact:
    """The period's indirect production costs, as the caller states them."""

    allocation_id: uuid.UUID
    period_start: date
    period_end: date
    variable_costs: Decimal
    constant_costs: Decimal
    normal_capacity: Decimal
    actual_volume: Decimal
    #: The base fixed in the accounting policy -- a name from the entity's own
    #: nomenclature, recorded on the event and never validated against a list.
    base_name: str
    products: tuple[ProductShare, ...]

    def as_payload(self) -> dict[str, Any]:
        return {
            "allocation_id": str(self.allocation_id),
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "variable_costs": str(self.variable_costs),
            "constant_costs": str(self.constant_costs),
            "normal_capacity": str(self.normal_capacity),
            "actual_volume": str(self.actual_volume),
            "base_name": self.base_name,
            "products": [
                {"item_id": str(p.item_id), "base_value": str(p.base_value), "code": p.code}
                for p in self.products
            ],
        }


@dataclass(frozen=True, slots=True)
class AllocationResult:
    accounting_event_id: uuid.UUID
    journal_entry_id: uuid.UUID | None
    formulas: int
    posted_now: bool


# --- the handler ---------------------------------------------------------------------


def _decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool | float):
        raise AllocationPayloadError(f"{field} is {value!r}; amounts travel exactly")
    try:
        return Decimal(value) if isinstance(value, int | Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise AllocationPayloadError(f"{field} is {value!r}, not a number") from None


def allocate_overheads(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    accounting_date: date,
    functional_currency: str,
    payload: Mapping[str, Any],
) -> tuple[RoleFormula, ...]:
    """pct. 29's two steps, from the payload, as role formulas.

    Step 1 (pct. 30): the variable total and the absorbed part of the constant
    total enter the cost; the unabsorbed remainder is `Dt 714 / Ct 821`. Step 2
    (pct. 31): what enters the cost is split over the products by their base
    values, one `Dt 811 / Ct 821` per product with the product as `item`.
    """
    del tenant_id, company_id
    variable = _decimal(payload.get("variable_costs"), "variable_costs")
    constant = _decimal(payload.get("constant_costs"), "constant_costs")
    normal = _decimal(payload.get("normal_capacity"), "normal_capacity")
    actual = _decimal(payload.get("actual_volume"), "actual_volume")
    if variable < 0 or constant < 0 or actual < 0:
        raise AllocationPayloadError("costs and volumes are not negative")
    if normal <= 0:
        raise AllocationPayloadError("normal_capacity is a positive volume (pct. 30)")
    raw_products = payload.get("products")
    if not isinstance(raw_products, list) or not raw_products:
        raise AllocationPayloadError("products is a non-empty list of {item_id, base_value}")
    products: list[tuple[uuid.UUID, Decimal, str]] = []
    for number, item in enumerate(raw_products, start=1):
        if not isinstance(item, Mapping):
            raise AllocationPayloadError(f"product {number} is not an object")
        try:
            item_id = uuid.UUID(str(item.get("item_id")))
        except (ValueError, TypeError):
            raise AllocationPayloadError(
                f"product {number}: item_id is not an identifier"
            ) from None
        base = _decimal(item.get("base_value"), f"product {number}: base_value")
        if base < 0:
            raise AllocationPayloadError(f"product {number}: base_value is negative")
        code = item.get("code")
        if code is not None and not isinstance(code, str):
            raise AllocationPayloadError(f"product {number}: code is not text")
        products.append((item_id, base, code if code else str(item_id)))
    if sum((base for _, base, _ in products), Decimal(0)) <= 0:
        raise AllocationBaseEmptyError(
            f"the base {payload.get('base_name')!r} sums to zero over {len(products)} products"
        )

    rule = rounding_for(accounting_date)
    scale = amount_scale(accounting_date)
    absorbed = absorption_for(accounting_date).absorb(
        variable=variable,
        constant=constant,
        normal_capacity=normal,
        actual_volume=actual,
        rule=rule,
        scale=scale,
    )

    def formula(
        debit: str, credit: str, amount: Decimal, text: str, item: uuid.UUID | None
    ) -> RoleFormula:
        return RoleFormula(
            debit_role=debit,
            credit_role=credit,
            amount=amount,
            currency=functional_currency,
            amount_currency=amount,
            exchange_rate=Decimal(1),
            rate_date=accounting_date,
            document_date=accounting_date,
            dimensions=(DimensionValue(ITEM_DIMENSION, item),) if item is not None else (),
            description=text,
        )

    out: list[RoleFormula] = []
    into_cost = absorbed.into_cost
    if into_cost > 0:
        shares = distribute(
            into_cost,
            [base for _, base, _ in products],
            keys=[key for _, _, key in products],
            rule=rule,
            scale=scale,
        )
        for (item_id, _, _), share in zip(products, shares, strict=True):
            if share != 0:
                out.append(
                    formula(
                        ROLE_BASIC,
                        ROLE_INDIRECT,
                        share,
                        "Repartizarea costurilor indirecte de producție",
                        item_id,
                    )
                )
    if absorbed.remainder > 0:
        out.append(
            formula(
                ROLE_UNABSORBED,
                ROLE_INDIRECT,
                absorbed.remainder,
                "Costuri indirecte constante nerepartizate — sub capacitatea normală",
                None,
            )
        )
    return tuple(out)


HANDLERS[HANDLER_REF] = allocate_overheads

register(
    EventType(
        name=EVENT_TYPE,
        payload_fields=PAYLOAD_FIELDS,
        account_roles=(ROLE_INDIRECT, ROLE_BASIC, ROLE_UNABSORBED),
        handlers=(HandlerVersion(implementation_ref=HANDLER_REF, valid_from=date.min),),
        description=(
            "The period's indirect production costs allocated: into the cost of the "
            "products by the base the policy fixes, the unabsorbed remainder to expenses."
        ),
    )
)


# --- the service ----------------------------------------------------------------------


def _check(fact: AllocationFact) -> None:
    for name, value in (
        ("variable_costs", fact.variable_costs),
        ("constant_costs", fact.constant_costs),
        ("normal_capacity", fact.normal_capacity),
        ("actual_volume", fact.actual_volume),
    ):
        if not isinstance(value, Decimal):
            raise AllocationPayloadError(f"{name} must be Decimal, never float")
    if fact.period_end < fact.period_start:
        raise AllocationPayloadError("the period ends before it starts")
    if not fact.base_name.strip():
        raise AllocationPayloadError(
            "base_name is empty; the base is the one the accounting policy fixes (pct. 31), "
            "and an allocation that does not say which one cannot be reviewed"
        )
    if not fact.products:
        raise AllocationPayloadError("no products to allocate over")


def post_overhead_allocation(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    functional_currency: str,
    fact: AllocationFact,
    actor_user_id: uuid.UUID,
    request_id: str,
    capability_snapshot: dict[str, Any],
    occurred_at: datetime | None = None,
) -> AllocationResult:
    """Record the allocation as an event and post what it produces.

    The handler runs on the fact **before** the event exists, as `services.manual`
    does: everything it refuses is a caller's bug, and an event recorded for a
    fact the rule cannot compute from would sit in the queue looking like work.
    """
    _check(fact)
    accounting_date = fact.period_end
    payload = fact.as_payload()
    treatment = selected_treatment(EVENT_TYPE, accounting_date, capability_snapshot)
    produced = treatment.handler(
        tenant_id=tenant_id,
        company_id=company_id,
        accounting_date=accounting_date,
        functional_currency=functional_currency,
        payload=payload,
    )
    if not all(isinstance(item, RoleFormula) for item in produced):
        raise AllocationPayloadError(
            f"the treatment registered for {EVENT_TYPE} returned something other than role formulas"
        )
    role_formulas: Sequence[RoleFormula] = tuple(produced)

    event, created = emit(
        tenant_id=tenant_id,
        company_id=company_id,
        event_type=EVENT_TYPE,
        source_module=SOURCE_MODULE,
        source_document_type=SOURCE_DOCUMENT_TYPE,
        source_document_id=fact.allocation_id,
        occurred_at=occurred_at or datetime.now(UTC),
        accounting_date=accounting_date,
        idempotency_key=f"{EVENT_TYPE}:{fact.allocation_id}",
        payload=payload,
        capability_snapshot=capability_snapshot,
        actor_user_id=actor_user_id,
        request_id=request_id,
    )
    if not created:
        settled = entry_id_of_event(event.id)
        if settled is not None or event.status == "posted":
            return AllocationResult(event.id, settled, 0, posted_now=False)

    if not role_formulas:
        mark_posted(event.id)
        return AllocationResult(event.id, None, 0, posted_now=True)

    try:
        with transaction.atomic():
            bound: Sequence[Formula] = bind_roles(company_id, accounting_date, role_formulas)
            scale_row = resolve_parameter(AMOUNT_SCALE_KEY, accounting_date)
            stamp = ParameterStamp(
                parameter_id=uuid.UUID(str(scale_row.pk)),
                parameter_key=AMOUNT_SCALE_KEY,
                effective_date=accounting_date,
                confidence=scale_row.source_confidence,
                resolved_at=datetime.now(UTC),
            )
            result = post_formulas(
                tenant_id=tenant_id,
                company_id=company_id,
                accounting_date=accounting_date,
                functional_currency=functional_currency,
                accounting_event_id=event.id,
                origin=Origin(
                    module=SOURCE_MODULE,
                    document_type=SOURCE_DOCUMENT_TYPE,
                    document_id=fact.allocation_id,
                ),
                rule_ref=treatment.ref,
                description=(
                    f"Repartizarea costurilor indirecte de producție, "
                    f"{fact.period_start:%d.%m.%Y} - {fact.period_end:%d.%m.%Y}, "
                    f"baza: {fact.base_name}"
                ),
                request_id=request_id,
                actor_user_id=actor_user_id,
                formulas=bound,
                parameter_stamps=(stamp,),
            )
    except (ApiError, NumberingError) as refusal:
        mark_failed(event.id, code=refusal.code, detail={"event_type": EVENT_TYPE})
        raise
    mark_posted(event.id)
    return AllocationResult(event.id, result.journal_entry_id, result.formulas, posted_now=True)
